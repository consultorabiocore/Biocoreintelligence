import streamlit as st
import pandas as pd
import json
import ee
import requests
from datetime import datetime, timedelta
from googleapiclient.discovery import build
from google.oauth2 import service_account

# --- 1. CONFIGURACIÓN DE IDENTIDAD Y ESTILOS ---
st.set_page_config(page_title="BioCore V5 Intelligence", layout="wide")
T_TOKEN = st.secrets["telegram"]["token"]
T_ID = st.secrets["telegram"]["chat_id"]
UMBRAL_CRITICO = 0.4
DIRECTORA = "Loreto Campos Carrasco"

# --- 2. DICCIONARIO MAESTRO ---
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

def enviar_telegram(m):
    try:
        requests.post(f"https://api.telegram.org/bot{T_TOKEN}/sendMessage", 
                      data={"chat_id": T_ID, "text": m, "parse_mode": "Markdown"})
    except: pass

# --- 3. INTERFAZ PRINCIPAL ---
st.title("🛰️ BioCore Intelligence V5")
st.write(f"**Directora Técnica:** {DIRECTORA}")

# Sidebar para control
with st.sidebar:
    st.header("Consola de Control")
    ejecutar = st.button("🚀 Ejecutar BioCore V5")
    st.divider()
    st.info("Sistema calibrado a umbral 0.4 para detección de anomalías.")

# --- 4. MOTOR DE PROCESAMIENTO ---
if ejecutar:
    try:
        # Autenticación
        creds_json = json.loads(st.secrets["gee"]["json"])
        creds = service_account.Credentials.from_service_account_info(creds_json, 
                scopes=['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/earthengine'])
        ee.Initialize(creds)
        sheets = build('sheets', 'v4', credentials=creds)

        progress_bar = st.progress(0)
        status_text = st.empty()

        for idx_p, (nombre, info) in enumerate(CLIENTES.items()):
            status_text.text(f"Procesando: {nombre}...")
            p = ee.Geometry.Polygon(info['coords'])
            
            # Módulo Fuego (FIRMS)
            ayer = datetime.now() - timedelta(days=3)
            fuegos = ee.ImageCollection("FIRMS").filterBounds(p).filterDate(ayer.strftime('%Y-%m-%d'), datetime.now().strftime('%Y-%m-%d')).size().getInfo()
            
            # Captura Satelital
            s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED').filterBounds(p).sort('system:time_start', False).first()
            s1 = ee.ImageCollection('COPERNICUS/S1_GRD').filterBounds(p).filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV')).sort('system:time_start', False).first()
            f_rep = datetime.fromtimestamp(s2.get('system:time_start').getInfo()/1000).strftime('%d/%m/%Y')

            # Índices
            res_idx = s2.expression('((B8-B4)/(B8+B4+0.5))*1.5', {'B8':s2.select('B8'),'B4':s2.select('B4')}).rename('sa')\
                .addBands(s2.normalizedDifference(['B3','B8']).rename('nd'))\
                .addBands(s2.normalizedDifference(['B3','B11']).rename('mn'))\
                .addBands(s2.select('B11').divide(s2.select('B12')).rename('cl'))\
                .reduceRegion(ee.Reducer.mean(), p, 30).getInfo()

            # Diagnóstico (Umbral 0.4)
            estado = "🟢 BAJO CONTROL"
            if fuegos > 0: estado = "🚨 EMERGENCIA: FUEGO"
            elif info['tipo'] == "HUMEDAL" and res_idx['nd'] < UMBRAL_CRITICO: estado = "🔴 ALERTA HÍDRICA"
            elif info['tipo'] == "GLACIAR" and res_idx['mn'] < UMBRAL_CRITICO: estado = "🔴 ALERTA CRIÓSFERA"

            # Telegram y visualización en App
            reporte = (f"🛰 **BIOCORE V5**\n**{nombre}**\n📅 {f_rep}\n🛡️ **ESTADO:** {estado}\n"
                       f"🌿 SAVI: `{res_idx['sa']:.2f}` | ❄️ NDSI/WI: `{res_idx['nd']:.2f}`")
            enviar_telegram(reporte)
            
            st.success(f"Sincronizado: {nombre} - Estado: {estado}")
            progress_bar.progress((idx_p + 1) / len(CLIENTES))

        st.balloons()
        status_text.text("Monitoreo Global Completado.")

    except Exception as e:
        st.error(f"Error en la ejecución: {e}")
        enviar_telegram(f"❌ Error BioCore: {str(e)}")

else:
    st.write("Esperando instrucción... Selecciona 'Ejecutar' en la barra lateral para iniciar el escaneo multimodal.")
