import streamlit as st
import pandas as pd
import json
import ee
import requests
from datetime import datetime, timedelta
from googleapiclient.discovery import build
from google.oauth2 import service_account

# --- CONFIGURACIÓN DE IDENTIDAD ---
T_TOKEN = st.secrets["telegram"]["token"]
T_ID = st.secrets["telegram"]["chat_id"]
UMBRAL_CRITICO = 0.4
DIRECTORA = "Loreto Campos Carrasco"

# --- DICCIONARIO MAESTRO (5 TIPOS DE PROYECTO) ---
CLIENTES = {
    "Laguna Señoraza (Laja)": {
        "coords": [[-72.715,-37.275],[-72.715,-37.285],[-72.690,-37.285],[-72.690,-37.270]], 
        "tipo": "HUMEDAL", "sheet_id": "ID_SHEET_1", "pestaña": "Humedales"
    },
    "Pascua Lama (Cordillera)": {
        "coords": [[-70.033,-29.316],[-70.016,-29.316],[-70.016,-29.333],[-70.033,-29.333]], 
        "tipo": "GLACIAR", "sheet_id": "ID_SHEET_2", "pestaña": "Mineria"
    },
    "Predio Forestal Biobío": {
        "coords": [[-72.50, -37.50], [-72.48, -37.50], [-72.48, -37.52], [-72.50, -37.52]],
        "tipo": "FORESTAL", "sheet_id": "ID_SHEET_3", "pestaña": "Forestal"
    }
}

def enviar_telegram(m):
    requests.post(f"https://api.telegram.org/bot{T_TOKEN}/sendMessage", 
                  data={"chat_id": T_ID, "text": m, "parse_mode": "Markdown"})

# --- MOTOR OMNIMODAL BIOCORE V5 ---
def ejecutar_biocore_integral():
    try:
        creds_json = json.loads(st.secrets["gee"]["json"])
        creds = service_account.Credentials.from_service_account_info(creds_json, 
                scopes=['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/earthengine'])
        ee.Initialize(creds)
        sheets = build('sheets', 'v4', credentials=creds)

        for nombre, info in CLIENTES.items():
            p = ee.Geometry.Polygon(info['coords'])
            
            # 1. Monitoreo de Incendios (Módulo 5: FIRMS)
            ayer = datetime.now() - timedelta(days=3)
            fuegos = ee.ImageCollection("FIRMS").filterBounds(p).filterDate(ayer.strftime('%Y-%m-%d'), datetime.now().strftime('%Y-%m-%d')).size().getInfo()
            alerta_fuego = f"🔥 ALERTA: {fuegos} focos detectados" if fuegos > 0 else "✅ Sin anomalías térmicas"

            # 2. Captura Satelital (S1 y S2)
            s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED').filterBounds(p).sort('system:time_start', False).first()
            s1 = ee.ImageCollection('COPERNICUS/S1_GRD').filterBounds(p).filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV')).sort('system:time_start', False).first()
            f_rep = datetime.fromtimestamp(s2.get('system:time_start').getInfo()/1000).strftime('%d/%m/%Y')

            # 3. Cálculo de Índices Multimodales
            idx = s2.expression('((B8-B4)/(B8+B4+0.5))*1.5', {'B8':s2.select('B8'),'B4':s2.select('B4')}).rename('sa')\
                .addBands(s2.normalizedDifference(['B3','B8']).rename('nd'))\
                .addBands(s2.normalizedDifference(['B3','B11']).rename('mn'))\
                .addBands(s2.select('B11').divide(s2.select('B12')).rename('cl'))\
                .addBands(s2.select('B11').divide(10000).rename('sw'))\
                .reduceRegion(ee.Reducer.mean(), p, 30).getInfo()

            # 4. Diagnóstico de Estado (Calibración 0.4)
            estado = "🟢 BAJO CONTROL"
            diagnostico = "Parámetros estables dentro de la norma técnica."

            if info['tipo'] == "HUMEDAL" and idx['nd'] < UMBRAL_CRITICO:
                estado = "🔴 ALERTA TÉCNICA"; diagnostico = "Estrés hídrico detectado en cuerpo de agua."
            elif info['tipo'] == "GLACIAR" and idx['mn'] < UMBRAL_CRITICO:
                estado = "🔴 ALERTA TÉCNICA"; diagnostico = "Pérdida de cobertura de nieve/hielo detectada."
            elif info['tipo'] == "FORESTAL" and idx['sa'] < UMBRAL_CRITICO:
                estado = "🔴 ALERTA TÉCNICA"; diagnostico = "Disminución crítica de vigor vegetativo."
            elif fuegos > 0:
                estado = "🚨 EMERGENCIA ACTIVADA"; diagnostico = "Presencia de focos de incendio en el polígono."

            # 5. Reporte BioCore
            sar_val = s1.reduceRegion(ee.Reducer.mean(), p, 30).getInfo().get('VV', 0)
            reporte = (
                f"🛰 **BIOCORE OMNIMODAL V5**\n"
                f"**{nombre}**\n"
                f"**Directora:** {DIRECTORA}\n"
                f"📅 **Análisis:** {f_rep}\n"
                f"──────────────────\n"
                f"🛡️ **ESTADO:** {estado}\n"
                f"🔥 **Fuego:** {alerta_fuego}\n"
                f"🌿 **SAVI:** `{idx['sa']:.2f}` | 🏗 **Arcilla:** `{idx['cl']:.2f}`\n"
                f"❄️ **NDSI/NDWI:** `{idx['nd']:.2f}`\n"
                f"📡 **Radar VV:** `{sar_val:.2f} dB`\n"
                f"──────────────────\n"
                f"📝 **Diagnóstico:** {diagnostico}"
            )
            enviar_telegram(reporte)

    except Exception as e: enviar_telegram(f"❌ Error en ejecución BioCore: {str(e)}")

if st.button("🚀 Ejecutar BioCore V5"):
    ejecutar_biocore_integral()
    st.balloons()
