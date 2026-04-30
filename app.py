import streamlit as st
import pandas as pd
import json
import ee
import requests
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from fpdf import FPDF
import folium
from streamlit_folium import folium_static
from google.oauth2 import service_account
from googleapiclient.discovery import build

# --- 1. CONFIGURACIÓN E IDENTIDAD ---
st.set_page_config(page_title="BioCore Intelligence Console", layout="wide")
T_TOKEN = st.secrets["telegram"]["token"]
T_ID = st.secrets["telegram"]["chat_id"]
DIRECTORA = "Loreto Campos Carrasco"

def clean(text):
    return text.encode('latin-1', 'replace').decode('latin-1')

# --- 2. BASE DE DATOS DE PROYECTOS (Expandible) ---
CLIENTES = {
 "Auditoría Laguna Señoraza": {
    "coords": [[-72.715,-37.275],[-72.715,-37.285],[-72.690,-37.285],[-72.690,-37.270]], 
    "tipo": "HUMEDAL",
    "sheet_id": "1x6yAXNNlea3e43rijJu0aqcRpe4oP3BEnzgSgLuG1vU"
 },
 "Auditoría Pascua Lama": {
    "coords": [[-70.033,-29.316],[-70.016,-29.316],[-70.016,-29.333],[-70.033,-29.333]], 
    "tipo": "MINERIA",
    "sheet_id": "1x6yAXNNlea3e43rijJu0aqcRpe4oP3BEnzgSgLuG1vU"
 }
}

# --- 3. SERVICIOS (GEE & GOOGLE SHEETS) ---
@st.cache_resource
def iniciar_servicios():
    try:
        creds_info = json.loads(st.secrets["gee"]["json"])
        creds = service_account.Credentials.from_service_account_info(
            creds_info, scopes=['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/earthengine']
        )
        try: ee.Initialize(credentials=creds)
        except: pass
        return build('sheets', 'v4', credentials=creds)
    except Exception as e:
        st.error(f"Error de conexión: {e}"); return None

service = iniciar_servicios()

# --- 4. GESTIÓN DE PESTAÑAS ---
def asegurar_pestaña(service, spreadsheet_id, nombre):
    try:
        meta = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
        existentes = [s.get("properties", {}).get("title") for s in meta.get('sheets', [])]
        if nombre not in existentes:
            solicitud = {'requests': [{'addSheet': {'properties': {'title': nombre}}}]}
            service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body=solicitud).execute()
            headers = [["Fecha", "Vigor (SAVI)", "Humedad (NDWI)", "Radar VV", "Precip mm", "Temp C", "Fuego"]]
            service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id, range=f"'{nombre}'!A1",
                valueInputOption="USER_ENTERED", body={'values': headers}
            ).execute()
    except Exception as e: st.error(f"Error Sheets: {e}")

# --- 5. LÓGICA DE ESCANEO PRO (INTEGRADA) ---
def escanear_multimodal(coords, tipo):
    p = ee.Geometry.Polygon(coords)
    # S2, S1 y TerraClimate
    s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED').filterBounds(p).sort('system:time_start', False).first()
    s1 = ee.ImageCollection('COPERNICUS/S1_GRD').filterBounds(p).filter(ee.Filter.eq('instrumentMode', 'IW')).sort('system:time_start', False).first()
    clima = ee.ImageCollection("IDAHO_EPSCOR/TERRACLIMATE").filterBounds(p).sort('system:time_start', False).first()
    
    # Cálculos con protección .getInfo()
    idx = s2.expression('((B8-B4)/(B8+B4+0.5))*1.5', {'B8':s2.select('B8'),'B4':s2.select('B4')})\
          .addBands(s2.normalizedDifference(['B3','B8']).rename('nd'))\
          .reduceRegion(ee.Reducer.mean(), p, 30).getInfo()
    
    radar = s1.select('VV').reduceRegion(ee.Reducer.mean(), p, 10).getInfo().get('VV', 0) if s1 else 0
    precip = clima.reduceRegion(ee.Reducer.mean(), p, 4638).getInfo().get('pr', 0) if clima else 0
    temp = clima.reduceRegion(ee.Reducer.mean(), p, 4638).getInfo().get('tmmx', 0) * 0.1 if clima else 0
    
    return {
        "fecha": datetime.now().strftime('%d/%m/%Y'),
        "savi": round(idx.get('constant', 0), 2),
        "ndwi": round(idx.get('nd', 0), 2),
        "radar": round(radar, 2),
        "precip": round(precip, 1),
        "temp": round(temp, 1)
    }

# --- 6. INTERFAZ ---
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/satellite.png", width=60)
    st.title("BioCore Admin")
    menu = st.radio("Módulos:", ["🛰️ Monitor Pro", "📊 Historial 20 Años", "🔥 Incendios"])
    st.divider()
    st.caption(f"Directora: {DIRECTORA}")

if service:
    sel = st.selectbox("🎯 Proyecto Activo:", list(CLIENTES.keys()))
    info = CLIENTES[sel]

    if menu == "🛰️ Monitor Pro":
        col1, col2 = st.columns([2, 1])
        with col1:
            avg_lat = sum(p[1] for p in info['coords']) / len(info['coords'])
            avg_lon = sum(p[0] for p in info['coords']) / len(info['coords'])
            m = folium.Map(location=[avg_lat, avg_lon], zoom_start=14)
            folium.TileLayer('https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}', attr='Google', name='Sat').add_to(m)
            folium.Polygon(locations=[[p[1], p[0]] for p in info['coords']], color='#2ecc71', fill=True, opacity=0.3).add_to(m)
            folium_static(m)

        with col2:
            if st.button("🚀 INICIAR ESCANEO MULTIMODAL"):
                with st.spinner("Integrando Óptico + Radar + Clima..."):
                    asegurar_pestaña(service, info['sheet_id'], sel)
                    data = escanear_multimodal(info['coords'], info['tipo'])
                    
                    # Guardar en Sheets
                    fila = [[data['fecha'], data['savi'], data['ndwi'], data['radar'], data['precip'], data['temp'], "NO"]]
                    service.spreadsheets().values().append(
                        spreadsheetId=info['sheet_id'], range=f"'{sel}'!A2", 
                        valueInputOption="USER_ENTERED", body={'values': fila}
                    ).execute()
                    
                    st.metric("Vigor (SAVI)", data['savi'])
                    st.metric("Lluvia (pr)", f"{data['precip']} mm")
                    st.metric("Radar (VV)", data['radar'])
                    
                    # Notificar a Telegram con el reporte
                    pdf = FPDF()
                    pdf.add_page(); pdf.set_font("helvetica","B",16)
                    pdf.cell(0, 15, clean(f"BIOCORE REPORT: {sel}"), ln=1, align="C")
                    pdf.set_font("helvetica","",12)
                    pdf.multi_cell(0, 10, clean(f"Fecha: {data['fecha']}\nSAVI: {data['savi']}\nClima: {data['precip']}mm / {data['temp']}C"))
                    pdf_bytes = pdf.output(dest='S').encode('latin-1')
                    requests.post(f"https://api.telegram.org/bot{T_TOKEN}/sendDocument", 
                                  data={"chat_id": T_ID, "caption": f"✅ Scan Ok: {sel}"}, 
                                  files={"document": ("Reporte_BioCore.pdf", pdf_bytes)})
                    st.toast("Reporte enviado al celular de la Directora.")

    elif menu == "📊 Historial 20 Años":
        # Aquí puedes integrar la función obtener_historia_20_anos que ya pulimos
        st.subheader("Auditoría Histórica Interanual")
        st.info("Este módulo procesa 20 años de Landsat 5, 7 y 8.")
        # ... (Insertar aquí el gráfico histórico ya desarrollado)

    elif menu == "🔥 Incendios":
        st.subheader("Vigilancia FIRMS (NASA)")
        # ... (Código FIRMS que tenías arriba)
