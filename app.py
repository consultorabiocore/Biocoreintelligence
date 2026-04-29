import streamlit as st
import ee
import json
import pandas as pd
import requests
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

# --- 2. BASE DE DATOS DE CLIENTES ---
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

# --- 3. INICIALIZACIÓN DE SERVICIOS ---
@st.cache_resource
def iniciar_servicios():
    try:
        creds_info = json.loads(st.secrets["gee"]["json"])
        creds = service_account.Credentials.from_service_account_info(
            creds_info, 
            scopes=['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/earthengine']
        )
        try:
            ee.Initialize(credentials=creds)
        except:
            pass
        return build('sheets', 'v4', credentials=creds)
    except Exception as e:
        st.error(f"Error técnico: {e}")
        return None

# --- 4. INTERFAZ ---
st.title("🛰️ BioCore Intelligence: Vigilancia Geoespacial")
service = iniciar_servicios()

if service:
    sel = st.selectbox("🎯 Objetivo de Auditoría:", list(CLIENTES.keys()))
    info = CLIENTES[sel]

    col_map, col_ctrl = st.columns([2, 1])

    with col_map:
        avg_lat = sum(p[1] for p in info['coords']) / len(info['coords'])
        avg_lon = sum(p[0] for p in info['coords']) / len(info['coords'])
        m = folium.Map(location=[avg_lat, avg_lon], zoom_start=14)
        folium.TileLayer('https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}', attr='Google', name='Google Sat').add_to(m)
        folium.Polygon(locations=[[p[1], p[0]] for p in info['coords']], color='#2ecc71', fill=True, opacity=0.4).add_to(m)
        folium_static(m)

    with col_ctrl:
        st.subheader("⚙️ Control de Sensores")
        if st.button("🚀 INICIAR ESCANEO MULTIESPECTRAL"):
            with st.spinner("Procesando telemetría..."):
                try:
                    p = ee.Geometry.Polygon(info['coords'])
                    
                    # 1. Óptico Sentinel-2
                    s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED').filterBounds(p).sort('system:time_start', False).first()
                    f_rep = datetime.fromtimestamp(s2.get('system:time_start').getInfo()/1000).strftime('%d/%m/%Y')
                    
                    # 2. Radar Sentinel-1
                    s1 = ee.ImageCollection('COPERNICUS/S1_GRD').filterBounds(p).filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV')).sort('system:time_start', False).first()
                    sar_val = s1.reduceRegion(ee.Reducer.mean(), p, 30).getInfo().get('VV', 0)

                    # 3. Índices (SAVI, NDWI, NDSI, SWIR, Clay)
                    idx = s2.expression('((B8-B4)/(B8+B4+0.5))*1.5', {'B8':s2.select('B8'),'B4':s2.select('B4')}).rename('sa')\
                        .addBands(s2.normalizedDifference(['B3','B8']).rename('nd'))\
                        .addBands(s2.normalizedDifference(['B3','B11']).rename('mn'))\
                        .addBands(s2.select('B11').divide(10000).rename('sw'))\
                        .addBands(s2.select('B11').divide(s2.select('B12')).rename('clay'))\
                        .reduceRegion(ee.Reducer.mean(), p, 30).getInfo()
                    
                    # 4. GEDI (NASA) y TerraClimate
                    try:
                        gedi = ee.ImageCollection("LARSE/GEDI/L2A_002").filterBounds(p).sort('system:time_start', False).first()
                        alt = gedi.reduceRegion(ee.Reducer.mean(), p, 30).getInfo().get('rh98', 1.2)
                    except: alt = 1.2
                    
                    clim = ee.ImageCollection("IDAHO_EPSCOR/TERRACLIMATE").filterBounds(p).sort('system:time_start', False).first()
                    defic = abs(float(clim.reduceRegion(ee.Reducer.mean(), p, 4638).getInfo().get('pr', 0)) - 100)

                    # --- LÓGICA DE DIAGNÓSTICO ---
                    sa, nd, mn, sw, clay = idx['sa'], idx['nd'], idx['mn'], idx['sw'], idx['clay']
                    estado_global = "🟢 BAJO CONTROL"
                    diagnostico = "Sin indicios de intervención antrópica reciente."
                    
                    if info['glaciar'] and mn < 0.35:
                        estado_global = "🔴 ALERTA TÉCNICA"
                        diagnostico = f"Pérdida crítica de cobertura criosférica (NDSI: {mn:.2f})."
                    elif info['tipo'] == "HUMEDAL" and nd < 0.1:
                        estado_global = "🔴 ALERTA TÉCNICA"
                        diagnostico = "Estrés hídrico detectado en polígono."

                    st.session_state['res_biocore'] = {
                        "fecha": f_rep, "sa": sa, "nd": nd, "mn": mn, "sw": sw, "clay": clay,
                        "alt": alt, "def": defic, "sar": sar_val, "estado": estado_global, "diag": diagnostico
                    }

                    # Sincronización Google Sheets
                    fila = [[f_rep, sa, nd, mn, sw, clay, defic]]
                    service.spreadsheets().values().append(
                        spreadsheetId=info['sheet_id'], range=f"{info['pestaña']}!A2", 
                        valueInputOption="USER_ENTERED", body={'values': fila}
                    ).execute()
                    
                    st.success("✅ Datos sincronizados.")
                    st.metric("Estatus", estado_global)

                except Exception as e:
                    st.error(f"Fallo: {e}")

        if 'res_biocore' in st.session_state:
            if st.button("📄 TRANSMITIR REPORTE FINAL"):
                r = st.session_state['res_biocore']
                pdf = FPDF()
                pdf.add_page()
                pdf.set_fill_color(20, 50, 80); pdf.rect(0, 0, 210, 40, 'F')
                pdf.set_text_color(255, 255, 255); pdf.set_font("helvetica", "B", 16)
                pdf.cell(0, 20, clean(f"AUDITORÍA BIOCORE: {sel}"), align="C", ln=1)
                
                pdf.ln(25); pdf.set_text_color(0, 0, 0); pdf.set_font("helvetica", "B", 12)
                pdf.cell(0, 10, clean(f"Diagnóstico Técnico - {r['fecha']}"), ln=1)
                
                pdf.set_font("helvetica", "", 10)
                txt = (
                    f"ESTADO: {r['estado']}\nDIAGNÓSTICO: {r['diag']}\n\n"
                    f"MÉTRICAS:\n- Vigor (SAVI): {r['sa']:.2f}\n- Criósfera (NDSI): {r['mn']:.2f}\n"
                    f"- Radar: {r['sar']:.2f} dB\n- Altura: {r['alt']:.1f}m\n- Arcillas: {r['clay']:.2f}"
                )
                pdf.multi_cell(0, 7, clean(txt), border=1)
                
                pdf_bytes = pdf.output(dest='S').encode('latin-1')
                files = {"document": (f"BioCore_{sel}.pdf", pdf_bytes)}
                msg = f"🛡️ **REPORTE BIOCORE**\nProyecto: {sel}\nEstado: {r['estado']}"
                requests.post(f"https://api.telegram.org/bot{T_TOKEN}/sendDocument", data={"chat_id": T_ID, "caption": msg}, files=files)
                st.success("🚀 Enviado a Telegram.")
