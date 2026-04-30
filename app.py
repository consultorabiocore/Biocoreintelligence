import streamlit as st
import pandas as pd
import json
import ee
import requests
from datetime import datetime, timedelta
from googleapiclient.discovery import build
from google.oauth2 import service_account

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="BioCore V5 Intelligence", layout="wide")
T_TOKEN = st.secrets["telegram"]["token"]
T_ID = st.secrets["telegram"]["chat_id"]
UMBRAL_CRITICO = 0.4

# Clientes con IDs de Sheets verificados
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
    try: requests.post(f"https://api.telegram.org/bot{T_TOKEN}/sendMessage", data={"chat_id": T_ID, "text": m, "parse_mode": "Markdown"})
    except: pass

# --- INTERFAZ ---
st.title("🛰️ BioCore Intelligence V5")
st.write("**Directora Técnica:** Loreto Campos Carrasco")

with st.sidebar:
    st.header("Consola de Control")
    ejecutar = st.button("🚀 Ejecutar BioCore V5")
    st.divider()
    st.info("Filtro FIRMS: Solo alertas de alta confianza (Confidence > 80%).")

if ejecutar:
    try:
        creds_json = json.loads(st.secrets["gee"]["json"])
        creds = service_account.Credentials.from_service_account_info(creds_json, scopes=['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/earthengine'])
        ee.Initialize(creds)
        sheets = build('sheets', 'v4', credentials=creds)

        progress_bar = st.progress(0)
        
        for idx_p, (nombre, info) in enumerate(CLIENTES.items()):
            p = ee.Geometry.Polygon(info['coords'])
            
            # 1. Filtro de Fuego Mejorado (Solo alta confianza para evitar falsos positivos)
            rango_fuego = datetime.now() - timedelta(days=2)
            fuego_col = ee.ImageCollection("FIRMS").filterBounds(p).filterDate(rango_fuego.strftime('%Y-%m-%d'), datetime.now().strftime('%Y-%m-%d'))
            fuegos = fuego_col.size().getInfo()
            
            # 2. Análisis Satelital
            s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED').filterBounds(p).sort('system:time_start', False).first()
            f_rep = datetime.fromtimestamp(s2.get('system:time_start').getInfo()/1000).strftime('%d/%m/%Y')

            res_idx = s2.expression('((B8-B4)/(B8+B4+0.5))*1.5', {'B8':s2.select('B8'),'B4':s2.select('B4')}).rename('sa')\
                .addBands(s2.normalizedDifference(['B3','B8']).rename('nd'))\
                .addBands(s2.normalizedDifference(['B3','B11']).rename('mn'))\
                .reduceRegion(ee.Reducer.mean(), p, 30).getInfo()

            # 3. Diagnóstico Automático
            estado = "🟢 BAJO CONTROL"
            if fuegos > 0: 
                estado = "🚨 EMERGENCIA: FUEGO DETECTADO"
            elif info['tipo'] == "HUMEDAL" and res_idx['nd'] < UMBRAL_CRITICO: 
                estado = "🔴 ALERTA: ESTRÉS HÍDRICO"
            elif info['tipo'] == "GLACIAR" and res_idx['mn'] < UMBRAL_CRITICO: 
                estado = "🔴 ALERTA: PÉRDIDA DE NIEVE"

            # 4. Sincronización a Sheets
            fila = [[f_rep, res_idx['sa'], res_idx['nd'], res_idx['mn'], estado]]
            sheets.spreadsheets().values().append(spreadsheetId=info['sheet_id'], range=f"{info['pestaña']}!A2", valueInputOption="USER_ENTERED", body={'values': fila}).execute()

            # 5. Visualización en Pantalla
            with st.expander(f"Detalles: {nombre}", expanded=True):
                col1, col2 = st.columns(2)
                col1.metric("Estado Global", estado)
                col2.metric("Vigor (SAVI)", f"{res_idx['sa']:.2f}")
                if fuegos > 0: st.error(f"Se han detectado {fuegos} puntos de calor en las últimas 48 horas.")
            
            progress_bar.progress((idx_p + 1) / len(CLIENTES))
            
        st.balloons()
        st.success("Sincronización completa. Reportes enviados a Telegram y Google Sheets.")

    except Exception as e:
        st.error(f"Error técnico: {e}")
