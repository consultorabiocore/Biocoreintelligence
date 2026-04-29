import streamlit as st
import ee
import json
import pandas as pd
import matplotlib.pyplot as plt
import requests
import io
from google.oauth2 import service_account
from googleapiclient.discovery import build
from datetime import datetime
from fpdf import FPDF
import folium
from streamlit_folium import folium_static

# --- 1. CONFIGURACIÓN ESTRATÉGICA ---
st.set_page_config(page_title="BioCore Intelligence Console", layout="wide")

T_TOKEN = st.secrets["telegram"]["token"]
T_ID = st.secrets["telegram"]["chat_id"]
DIRECTORA = "Loreto Campos Carrasco"

def clean(text):
    return text.encode('latin-1', 'replace').decode('latin-1')

# --- 2. BASE DE DATOS DE PROYECTOS (TU LÓGICA INTEGRADA) ---
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

# --- 3. INICIALIZACIÓN DE SERVICIOS (GEE Y SHEETS) ---
@st.cache_resource
def iniciar_servicios():
    try:
        creds_info = json.loads(st.secrets["gee"]["json"])
        creds = service_account.Credentials.from_service_account_info(
            creds_info, 
            scopes=['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/earthengine']
        )
        if not ee.data._credentials:
            ee.Initialize(creds)
        service = build('sheets', 'v4', credentials=creds)
        return service
    except Exception as e:
        st.error(f"Error de conexión: {e}")
        return None

# --- 4. INTERFAZ DE USUARIO ---
st.title("🛰️ BioCore Intelligence: Consola de Alta Vigilancia")
service = iniciar_servicios()

if service:
    sel = st.selectbox("🎯 Seleccione Proyecto de Auditoría:", list(CLIENTES.keys()))
    info = CLIENTES[sel]

    col_map, col_ctrl = st.columns([2, 1])

    with col_map:
        st.subheader("🗺️ Área de Vigilancia Geoespacial")
        # Generar Mapa Folium
        m = folium.Map(location=[info['coords'][0][1], info['coords'][0][0]], zoom_start=14)
        folium.TileLayer('https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}', attr='Google', name='Google Sat').add_to(m)
        folium.Polygon(locations=[[p[1], p[0]] for p in info['coords']], color='#2ecc71', fill=True, opacity=0.4).add_to(m)
        folium_static(m)

    with col_ctrl:
        st.subheader("⚙️ Control de Sensores")
        
        if st.button("🚀 EJECUTAR MONITOREO Y SINCRONIZAR"):
            with st.spinner("Analizando Radar, Óptico y GEDI..."):
                try:
                    p = ee.Geometry.Polygon(info['coords'])
                    
                    # Captura Sentinel-2
                    s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED').filterBounds(p).sort('system:time_start', False).first()
                    f_rep = datetime.fromtimestamp(s2.get('system:time_start').getInfo()/1000).strftime('%d/%m/%Y')
                    
                    # Radar S1
                    s1 = ee.ImageCollection('COPERNICUS/S1_GRD').filterBounds(p).filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV')).sort('system:time_start', False).first()
                    sar_val = s1.reduceRegion(ee.Reducer.mean(), p, 30).getInfo().get('VV', 0)

                    # Índices Espectrales (Tu fórmula de SAVI, NDSI, NDWI, SWIR, Clay)
                    idx = s2.expression('((B8-B4)/(B8+B4+0.5))*1.5', {'B8':s2.select('B8'),'B4':s2.select('B4')}).rename('sa')\
                        .addBands(s2.normalizedDifference(['B3','B8']).rename('nd'))\
                        .addBands(s2.normalizedDifference(['B3','B11']).rename('mn'))\
                        .addBands(s2.select('B11').divide(10000).rename('sw'))\
                        .addBands(s2.select('B11').divide(s2.select('B12')).rename('clay'))\
                        .reduceRegion(ee.Reducer.mean(), p, 30).getInfo()
                    
                    # Clima y GEDI
                    clim = ee.ImageCollection("IDAHO_EPSCOR/TERRACLIMATE").filterBounds(p).sort('system:time_start', False).first()
                    defic = abs(float(clim.reduceRegion(ee.Reducer.mean(), p, 4638).getInfo().get('pr', 0)) - 100)

                    # --- LÓGICA DE DIAGNÓSTICO BIOCORE ---
                    sa, nd, mn, sw, clay = idx['sa'], idx['nd'], idx['mn'], idx['sw'], idx['clay']
                    estado_global = "🟢 BAJO CONTROL"
                    diagnostico = "Parámetros dentro de la norma legal."
                    
                    if info['glaciar'] and mn < 0.35:
                        estado_global = "🔴 ALERTA TÉCNICA"
                        diagnostico = f"Pérdida de cobertura criosférica detectada (NDSI: {mn:.2f})."
                    elif not info['glaciar'] and nd < 0.1:
                        estado_global = "🔴 ALERTA TÉCNICA"
                        diagnostico = "Estrés hídrico detectado en humedal."

                    # Guardar en Session State para el PDF
                    st.session_state['res_biocore'] = {
                        "fecha": f_rep, "savi": sa, "ndsi": mn, "swir": sw, 
                        "estado": estado_global, "diag": diagnostico, "sar": sar_val
                    }

                    # Sincronizar con Google Sheets
                    fila = [[f_rep, sa, nd, mn, sw, clay, defic]]
                    service.spreadsheets().values().append(
                        spreadsheetId=info['sheet_id'], range=f"{info['pestaña']}!A2", 
                        valueInputOption="USER_ENTERED", body={'values': fila}
                    ).execute()
                    
                    st.success(f"Datos sincronizados. Estatus: {estado_global}")
                    st.metric("Vigor SAVI", f"{sa:.2f}")
                    st.metric("Índice Criósfera", f"{mn:.2f}")

                except Exception as e:
                    st.error(f"Fallo en motor de análisis: {e}")

        # --- GENERAR Y ENVIAR REPORTE ---
        if 'res_biocore' in st.session_state:
            if st.button("📄 GENERAR REPORTE FINAL Y ENVIAR"):
                r = st.session_state['res_biocore']
                
                # Crear PDF
                pdf = FPDF()
                pdf.add_page()
                pdf.set_fill_color(20, 50, 80); pdf.rect(0, 0, 210, 40, 'F')
                pdf.set_text_color(255, 255, 255); pdf.set_font("helvetica", "B", 16)
                pdf.cell(0, 20, clean(f"AUDITORÍA AMBIENTAL: {sel}"), align="C", ln=1)
                
                pdf.ln(25); pdf.set_text_color(0, 0, 0); pdf.set_font("helvetica", "B", 12)
                pdf.cell(0, 10, clean(f"Diagnóstico Técnico - {r['fecha']}"), ln=1)
                
                # Cuerpo del Reporte
                pdf.set_font("helvetica", "", 10)
                contenido = (
                    f"ESTADO GLOBAL: {r['estado']}\n"
                    f"DIAGNÓSTICO: {r['diag']}\n\n"
                    f"DATOS TÉCNICOS:\n"
                    f"- Vigor Vegetacional (SAVI): {r['savi']:.2f}\n"
                    f"- Estabilidad Criósfera (NDSI): {r['ndsi']:.2f}\n"
                    f"- Radar (VV): {r['sar']:.2f} dB\n"
                    f"- Reflectancia Mineral (SWIR): {r['swir']:.2f}"
                )
                pdf.multi_cell(0, 7, clean(contenido), border=1)
                
                pdf_output = pdf.output(dest='S').encode('latin-1')
                
                # Envío a Telegram
                files = {"document": (f"Reporte_{sel}.pdf", pdf_output)}
                msg = f"🛡️ REPORTE BIOCORE: {sel}\nEstatus: {r['estado']}\nFecha: {r['fecha']}"
                requests.post(f"https://api.telegram.org/bot{T_TOKEN}/sendDocument", data={"chat_id": T_ID, "caption": msg}, files=files)
                
                st.success("Reporte enviado a Telegram exitosamente.")
