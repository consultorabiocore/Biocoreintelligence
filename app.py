import streamlit as st
import pandas as pd
import json
import ee
import requests
from datetime import datetime
from googleapiclient.discovery import build
from google.oauth2 import service_account

# --- CONFIGURACIÓN DE IDENTIDAD ---
T_TOKEN = st.secrets["telegram"]["token"]
T_ID = st.secrets["telegram"]["chat_id"]
UMBRAL_CRITICO = 0.4

# --- DICCIONARIO MAESTRO EXPANDIBLE (Los 5 Tipos) ---
CLIENTES = {
    "Laguna Señoraza (Laja)": {
        "coords": [[-72.715,-37.275],[-72.715,-37.285],[-72.690,-37.285],[-72.690,-37.270]], 
        "tipo": "HUMEDAL", "sheet_id": "TU_ID_1", "pestaña": "Humedales"
    },
    "Pascua Lama (Cordillera)": {
        "coords": [[-70.033,-29.316],[-70.016,-29.316],[-70.016,-29.333],[-70.033,-29.333]], 
        "tipo": "GLACIAR", "sheet_id": "TU_ID_2", "pestaña": "Mineria"
    },
    "Predio Forestal Biobío": {
        "coords": [[-72.50, -37.50], [-72.48, -37.50], [-72.48, -37.52], [-72.50, -37.52]],
        "tipo": "FORESTAL", "sheet_id": "TU_ID_3", "pestaña": "Forestal"
    }
    # Se pueden agregar tipos 'INFRAESTRUCTURA' y 'RIESGO' siguiendo la misma lógica
}

def enviar_telegram(m):
    requests.post(f"https://api.telegram.org/bot{T_TOKEN}/sendMessage", 
                  data={"chat_id": T_ID, "text": m, "parse_mode": "Markdown"})

# --- MOTOR OMNIMODAL BIOCORE ---
def ejecutar_biocore_total():
    try:
        creds_json = json.loads(st.secrets["gee"]["json"])
        creds = service_account.Credentials.from_service_account_info(creds_json, 
                scopes=['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/earthengine'])
        ee.Initialize(creds)
        sheets = build('sheets', 'v4', credentials=creds)

        for nombre, info in CLIENTES.items():
            p = ee.Geometry.Polygon(info['coords'])
            
            # 1. Captura de Sensores (Fusión Óptico + Radar)
            s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED').filterBounds(p).sort('system:time_start', False).first()
            s1 = ee.ImageCollection('COPERNICUS/S1_GRD').filterBounds(p).filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV')).sort('system:time_start', False).first()
            f_rep = datetime.fromtimestamp(s2.get('system:time_start').getInfo()/1000).strftime('%d/%m/%Y')

            # 2. Procesamiento Espectral Multimodal
            idx = s2.expression('((B8-B4)/(B8+B4+0.5))*1.5', {'B8':s2.select('B8'),'B4':s2.select('B4')}).rename('savi')\
                .addBands(s2.normalizedDifference(['B3','B8']).rename('ndwi'))\
                .addBands(s2.normalizedDifference(['B3','B11']).rename('ndsi'))\
                .addBands(s2.select('B11').divide(s2.select('B12')).rename('clay'))\
                .addBands(s2.select('B11').divide(10000).rename('swir'))\
                .reduceRegion(ee.Reducer.mean(), p, 30).getInfo()
            
            # 3. Lógica de Diagnóstico según Tipo (Calibrada a 0.4)
            estado = "🟢 BAJO CONTROL"
            diagnostico = "Parámetros estables."
            
            if info['tipo'] == "HUMEDAL":
                # Alerta si el agua (ndwi) cae bajo 0.4
                if idx['ndwi'] < UMBRAL_CRITICO:
                    estado = "🔴 ALERTA TÉCNICA"; diagnostico = f"Estrés hídrico severo detectado (NDWI: {idx['ndwi']:.2f})."
            
            elif info['tipo'] == "GLACIAR":
                # Alerta si la nieve (ndsi) cae bajo 0.4
                if idx['ndsi'] < UMBRAL_CRITICO:
                    estado = "🔴 ALERTA TÉCNICA"; diagnostico = f"Pérdida de cobertura criosférica (NDSI: {idx['ndsi']:.2f})."
            
            elif info['tipo'] == "FORESTAL":
                # Alerta si el vigor (savi) cae bajo 0.4
                if idx['savi'] < UMBRAL_CRITICO:
                    estado = "🔴 ALERTA TÉCNICA"; diagnostico = f"Degradación de dosel detectada (SAVI: {idx['savi']:.2f})."

            elif info['tipo'] == "MINERIA":
                # Alerta si hay movimiento de material (SWIR alto)
                if idx['swir'] > UMBRAL_CRITICO:
                    estado = "🔴 ALERTA TÉCNICA"; diagnostico = "Posible movimiento de estériles o excavación."

            # 4. Sincronización y Reporte
            reporte = (
                f"🛰 **BIOCORE OMNIMODAL**\n"
                f"**{nombre}** ({info['tipo']})\n"
                f"📅 **Análisis:** {f_rep}\n"
                f"──────────────────\n"
                f"🌿 **SAVI:** `{idx['savi']:.2f}`\n"
                f"❄️ **NDSI/NDWI:** `{idx['ndsi']:.2f}`\n"
                f"🏗 **Arcillas:** `{idx['clay']:.2f}`\n"
                f"📡 **Radar VV:** `{s1.reduceRegion(ee.Reducer.mean(), p, 30).getInfo().get('VV', 0):.2f} dB`\n"
                f"──────────────────\n"
                f"✅ **ESTADO:** {estado}\n"
                f"📝 **Diagnóstico:** {diagnostico}"
            )
            enviar_telegram(reporte)

    except Exception as e:
        enviar_telegram(f"❌ Error Crítico: {str(e)}")

if st.button("🚀 Ejecutar BioCore Total (5 Módulos)"):
    ejecutar_biocore_total()
