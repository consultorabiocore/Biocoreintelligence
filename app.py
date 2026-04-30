import streamlit as st
import pandas as pd
import json
import ee
import requests
from datetime import datetime, timedelta
from googleapiclient.discovery import build
from google.oauth2 import service_account

# --- 1. CONFIGURACIÓN BÁSICA ---
st.set_page_config(page_title="BioCore V5", layout="centered") # Centrado es mejor para móvil

T_TOKEN = st.secrets["telegram"]["token"]
T_ID = st.secrets["telegram"]["chat_id"]
UMBRAL_CRITICO = 0.4

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

# --- 2. MOTOR DE PROCESAMIENTO ---
def ejecutar_analisis():
    try:
        # Autenticación GEE
        creds_json = json.loads(st.secrets["gee"]["json"])
        creds = service_account.Credentials.from_service_account_info(creds_json, 
                scopes=['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/earthengine'])
        if not ee.data._credentials:
            ee.Initialize(creds)
        
        sheets_service = build('sheets', 'v4', credentials=creds)

        for nombre, info in CLIENTES.items():
            st.markdown(f"---")
            st.header(f"📍 {nombre}")
            
            p = ee.Geometry.Polygon(info['coords'])
            
            # Captura Satelital (Sentinel-2)
            s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED').filterBounds(p).sort('system:time_start', False).first()
            f_rep = datetime.fromtimestamp(s2.get('system:time_start').getInfo()/1000).strftime('%d/%m/%Y')
            
            # Cálculo de Índices
            idx = s2.expression('((B8-B4)/(B8+B4+0.5))*1.5', {'B8':s2.select('B8'),'B4':s2.select('B4')}).rename('sa')\
                .addBands(s2.normalizedDifference(['B3','B8']).rename('nd'))\
                .addBands(s2.normalizedDifference(['B3','B11']).rename('mn'))\
                .reduceRegion(ee.Reducer.mean(), p, 30).getInfo()

            # Lógica de Alerta
            estado = "🟢 NORMAL"
            if info['tipo'] == "HUMEDAL" and idx['nd'] < UMBRAL_CRITICO: estado = "🔴 ALERTA HÍDRICA"
            elif info['tipo'] == "GLACIAR" and idx['mn'] < UMBRAL_CRITICO: estado = "🔴 ALERTA NIEVE"

            # MOSTRAR RESULTADOS (Forzado para visibilidad)
            st.subheader(f"Estado: {estado}")
            st.write(f"📅 Fecha Satélite: {f_rep}")
            st.write(f"🌿 Vigor Vegetal (SAVI): **{idx['sa']:.3f}**")
            st.write(f"💧 Índice Agua/Nieve: **{idx['nd']:.3f}**")

            # Sincronizar Google Sheets
            fila = [[f_rep, idx['sa'], idx['nd'], idx['mn'], estado]]
            sheets_service.spreadsheets().values().append(
                spreadsheetId=info['sheet_id'], 
                range=f"{info['pestaña']}!A2", 
                valueInputOption="USER_ENTERED", 
                body={'values': fila}).execute()
            
            st.info(f"✅ Datos sincronizados para {nombre}")

        st.balloons()

    except Exception as e:
        st.error(f"Ocurrió un error: {e}")

# --- 3. INTERFAZ ---
st.title("🛰️ BioCore V5")
st.write("Presiona el botón para iniciar el monitoreo de los polígonos.")

if st.button("🚀 INICIAR ESCANEO", use_container_width=True):
    ejecutar_analisis()
else:
    st.warning("Esperando ejecución...")
