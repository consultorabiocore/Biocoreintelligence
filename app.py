import streamlit as st
import pandas as pd
import json
import ee
import requests
from datetime import datetime, timedelta
from googleapiclient.discovery import build
from google.oauth2 import service_account

# --- 1. CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="BioCore Omnimodal V5", layout="wide")

# Estilo personalizado para mejorar la visibilidad
st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    .stMetric { background-color: #1f2937; padding: 15px; border-radius: 10px; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. CREDENCIALES Y CONSTANTES ---
T_TOKEN = st.secrets["telegram"]["token"]
T_ID = st.secrets["telegram"]["chat_id"]
UMBRAL_CRITICO = 0.4
DIRECTORA = "Loreto Campos Carrasco"

CLIENTES = {
    "Laguna Señoraza (Laja)": {
        "coords": [[-72.715,-37.275],[-72.715,-37.285],[-72.690,-37.285],[-72.690,-37.270]], 
        "tipo": "HUMEDAL", "sheet_id": "1x6yAXNNlea3e43rijJu0aqcRpe4oP3BEnzgSgLuG1vU", "pestaña": "Humedales"
    },
    "Pascua Lama (Cordillera)": {
        "coords": [[-70.033,-29.316],[-70.016,-29.316],[-70.016,-29.333],[-70.033,-29.333]], 
        "tipo": "GLACIAR", "sheet_id": "1UTrDs939rPlVIR1OTIwbJ6rM3FazgjX43YnJdue-Dmc", "pestaña": "Mineria"
    }
}

# --- 3. FUNCIONES DE SISTEMA ---
def enviar_telegram(m):
    try:
        requests.post(f"https://api.telegram.org/bot{T_TOKEN}/sendMessage", 
                      data={"chat_id": T_ID, "text": m, "parse_mode": "Markdown"})
    except: pass

def inicializar_gee():
    if not ee.data._credentials:
        creds_json = json.loads(st.secrets["gee"]["json"])
        creds = service_account.Credentials.from_service_account_info(creds_json, 
                scopes=['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/earthengine'])
        ee.Initialize(creds)
        return creds
    return None

# --- 4. INTERFAZ DE USUARIO ---
st.title("🛰️ BioCore Intelligence Console V5")
st.subheader(f"Directora Técnica: {DIRECTORA}")

with st.sidebar:
    st.header("Módulos de Vigilancia")
    activar_monitoreo = st.button("🚀 Ejecutar BioCore Total", use_container_width=True)
    st.divider()
    st.write(f"**Umbral de Alerta:** {UMBRAL_CRITICO}")

# --- 5. LÓGICA DE PROCESAMIENTO ---
if activar_monitoreo:
    try:
        creds = inicializar_gee()
        sheets_service = build('sheets', 'v4', credentials=creds)
        
        for nombre, info in CLIENTES.items():
            st.write(f"### Analizando: {nombre}")
            p = ee.Geometry.Polygon(info['coords'])
            
            # Captura de datos satelitales
            s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED').filterBounds(p).sort('system:time_start', False).first()
            f_rep = datetime.fromtimestamp(s2.get('system:time_start').getInfo()/1000).strftime('%d/%m/%Y')
            
            # Índices Multimodales
            idx = s2.expression('((B8-B4)/(B8+B4+0.5))*1.5', {'B8':s2.select('B8'),'B4':s2.select('B4')}).rename('sa')\
                .addBands(s2.normalizedDifference(['B3','B8']).rename('nd'))\
                .addBands(s2.normalizedDifference(['B3','B11']).rename('mn'))\
                .reduceRegion(ee.Reducer.mean(), p, 30).getInfo()

            # Lógica de Estado
            estado = "🟢 BAJO CONTROL"
            if info['tipo'] == "HUMEDAL" and idx['nd'] < UMBRAL_CRITICO: estado = "🔴 ALERTA HÍDRICA"
            elif info['tipo'] == "GLACIAR" and idx['mn'] < UMBRAL_CRITICO: estado = "🔴 ALERTA CRIÓSFERA"

            # Visualización de Métricas en Pantalla (Esto es lo que no se veía)
            col1, col2, col3 = st.columns(3)
            with col1: st.metric("Estado", estado)
            with col2: st.metric("Vigor (SAVI)", f"{idx['sa']:.2f}")
            with col3: st.metric("Agua/Nieve", f"{idx['nd']:.2f}")

            # Sincronización a Sheets
            fila = [[f_rep, idx['sa'], idx['nd'], idx['mn'], estado]]
            sheets_service.spreadsheets().values().append(
                spreadsheetId=info['sheet_id'], 
                range=f"{info['pestaña']}!A2", 
                valueInputOption="USER_ENTERED", 
                body={'values': fila}).execute()

            # Notificación Telegram
            enviar_telegram(f"🛰 **BioCore V5**\nProyecto: {nombre}\nEstado: {estado}\nSAVI: {idx['sa']:.2f}")
            
        st.balloons()
        st.success("✅ Monitoreo completado y sincronizado.")

    except Exception as e:
        st.error(f"Se produjo un error: {e}")
