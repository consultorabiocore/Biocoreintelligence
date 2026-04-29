import streamlit as st
import ee, requests, os, io, json
import pandas as pd
import matplotlib.pyplot as plt
from google.oauth2 import service_account
from googleapiclient.discovery import build
from datetime import datetime
from fpdf import FPDF
import folium
from streamlit_folium import folium_static

# --- 1. CONFIGURACIÓN ESTRATÉGICA ---
T_TOKEN, T_ID = "7961684994:AAGbepFHxXJtjCVTCjEwq2xWh9vT9TO6G68", "6712325113"
DIRECTORA = "Loreto Campos Carrasco"

st.set_page_config(page_title="BioCore Intelligence Console", layout="wide")

def clean(text):
    return text.encode('latin-1', 'replace').decode('latin-1')

# --- 2. BASE DE DATOS DE CLIENTES (TU LÓGICA) ---
CLIENTES = {
 "Laguna Señoraza (Laja)": {
    "coords": [[-72.715,-37.275],[-72.715,-37.285],[-72.690,-37.285],[-72.690,-37.270]], 
    "tipo": "HUMEDAL", "glaciar": False,
    "sheet_id": "1x6yAXNNlea3e43rijJu0aqcRpe4oP3BEnzgSgLuG1vU", "pestaña": "ID_CARPETA_1"
 },
 "Pascua Lama (Cordillera)": {
    "coords": [[-70.033,-29.316],[-70.016,-29.316],[-70.016,-29.333],[-70.033,-29.333]], 
    "tipo": "MINERIA", "glaciar": True,
    "sheet_id": "1UTrDs939rPlVIR1OTIwbJ6rM3FazgjX43YnJdue-Dmc", "pestaña": "ID_CARPETA_2"
 }
}

# --- 3. FUNCIONES DE AUTENTICACIÓN ---
def iniciar_servicios():
    try:
        # Cargamos desde Secrets de Streamlit para que funcione en la web
        creds_info = json.loads(st.secrets["EARTH_ENGINE_JSON"])
        creds = service_account.Credentials.from_service_account_info(creds_info, 
                scopes=['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/earthengine'])
        if not ee.data._credentials: ee.Initialize(creds)
        service = build('sheets', 'v4', credentials=creds)
        return service
    except: return None

# --- 4. INTERFAZ ---
st.title("🛰️ BioCore Intelligence: Consola de Alta Vigilancia")
service = iniciar_servicios()

if service:
    sel = st.selectbox("Seleccione Proyecto:", list(CLIENTES.keys()))
    info = CLIENTES[sel]

    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader("🗺️ Área de Vigilancia")
        m = folium.Map(location=[info['coords'][0][1], info['coords'][0][0]], zoom_start=14)
        folium.TileLayer('https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}', attr='Google', name='Google Sat').add_to(m)
        folium.Polygon(locations=[[p[1], p[0]] for p in info['coords']], color='#2ecc71', fill=True, opacity=0.4).add_to(m)
        folium_static(m)

    with col2:
        st.subheader("⚙️ Control Técnico")
        if st.button("🚀 EJECUTAR MONITOREO Y SINCRONIZAR"):
            with st.spinner("Procesando Radar, Óptico y GEDI..."):
                # --- AQUÍ VA TODA TU LÓGICA DE MONITOR_BIOCORE.PY ---
                p = ee.Geometry.Polygon(info['coords'])
                s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED').filterBounds(p).sort('system:time_start', False).first()
                f_rep = datetime.fromtimestamp(s2.get('system:time_start').getInfo()/1000).strftime('%d/%m/%Y')
                
                # Índices (SAVI, NDWI, NDSI, SWIR, CLAY)
                idx = s2.expression('((B8-B4)/(B8+B4+0.5))*1.5', {'B8':s2.select('B8'),'B4':s2.select('B4')}).rename('sa')\
                    .addBands(s2.normalizedDifference(['B3','B8']).rename('nd'))\
                    .addBands(s2.normalizedDifference(['B3','B11']).rename('mn'))\
                    .addBands(s2.select('B11').divide(10000).rename('sw'))\
                    .addBands(s2.select('B11').divide(s2.select('B12')).rename('clay'))\
                    .reduceRegion(ee.Reducer.mean(), p, 30).getInfo()
                
                # Sincronización a Sheet
                fila = [[f_rep, idx['sa'], idx['nd'], idx['mn'], idx['sw'], idx['clay']]]
                service.spreadsheets().values().append(spreadsheetId=info['sheet_id'], range=f"{info['pestaña']}!A2", 
                                                       valueInputOption="USER_ENTERED", body={'values': fila}).execute()
                
                st.success(f"Datos sincronizados en {info['pestaña']}")
                st.session_state['ready'] = True

        if st.session_state.get('ready'):
            if st.button("📄 GENERAR REPORTE PDF Y ENVIAR"):
                # --- AQUÍ VA TODA TU LÓGICA DE BIOCORE_REPORTE_FINAL.PY ---
                res = service.spreadsheets().values().get(spreadsheetId=info['sheet_id'], range=f"{info['pestaña']}!A:F").execute()
                df = pd.DataFrame(res.get('values', [])[1:], columns=["Fecha", "SAVI", "NDWI", "NDSI", "SWIR", "Clay"])
                
                # Generación de PDF con lógica de alerta de NDSI < 0.35
                pdf = FPDF()
                pdf.add_page()
                pdf.set_fill_color(20, 50, 80); pdf.rect(0, 0, 210, 40, 'F')
                pdf.set_text_color(255, 255, 255); pdf.set_font("helvetica", "B", 16)
                pdf.cell(0, 20, clean(f"AUDITORÍA BIOCORE: {sel}"), align="C", ln=1)
                
                # (Aquí incluirías los gráficos y el diagnóstico legal que ya escribiste)
                pdf_output = pdf.output(dest='S').encode('latin-1')
                
                # Envío a Telegram
                requests.post(f"https://api.telegram.org/bot{T_TOKEN}/sendDocument", 
                              data={"chat_id": T_ID, "caption": f"🛡️ Reporte Final Enviado: {sel}"}, 
                              files={"document": ("Reporte_BioCore.pdf", pdf_output)})
                st.success("Reporte enviado a Telegram exitosamente.")
