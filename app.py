import streamlit as st
import pandas as pd
import json
import ee
import requests
from datetime import datetime, timedelta
from googleapiclient.discovery import build
from google.oauth2 import service_account
from streamlit_folium import folium_static
import folium

# --- 1. CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="BioCore V5 Intelligence", layout="wide")

T_TOKEN = st.secrets["telegram"]["token"]
T_ID = st.secrets["telegram"]["chat_id"]
UMBRAL_CRITICO = 0.4

# --- 2. DICCIONARIO MAESTRO (5 TIPOS) ---
CLIENTES = {
    "Laguna Señoraza (Laja)": {
        "coords": [[-72.715,-37.275],[-72.715,-37.285],[-72.690,-37.285],[-72.690,-37.270]], 
        "tipo": "HUMEDAL", "sheet_id": "1x6yAXNNlea3e43rijJu0aqcRpe4oP3BEnzgSgLuG1vU", "pestaña": "Humedales"
    },
    "Pascua Lama (Cordillera)": {
        "coords": [[-70.033,-29.316],[-70.016,-29.316],[-70.016,-29.333],[-70.033,-29.333]], 
        "tipo": "GLACIAR", "sheet_id": "1UTrDs939rPlVIR1OTIwbJ6rM3FazgjX43YnJdue-Dmc", "pestaña": "Mineria"
    },
    "Predio Forestal Biobío": {
        "coords": [[-72.50, -37.50], [-72.48, -37.50], [-72.48, -37.52], [-72.50, -37.52]],
        "tipo": "FORESTAL", "sheet_id": "TU_ID_3", "pestaña": "Forestal"
    }
}

# --- 3. BARRA LATERAL (RECUPERADA) ---
with st.sidebar:
    st.title("⚙️ Configuración")
    umbral = st.slider("Umbral de Alerta", 0.0, 1.0, UMBRAL_CRITICO)
    st.divider()
    ejecutar = st.button("🚀 INICIAR MONITOREO", use_container_width=True)
    st.info("Al activar, se sincronizarán Google Sheets y Telegram.")

# --- 4. CUERPO PRINCIPAL ---
st.title("🛰️ BioCore Intelligence V5")

# Mapa de Proyectos
st.subheader("Mapa de Operaciones")
m = folium.Map(location=[-35.0, -71.0], zoom_start=5)
for n, i in CLIENTES.items():
    p_fol = [[c[1], c[0]] for c in i['coords']]
    folium.Polygon(locations=p_fol, popup=n, color='green', fill=True).add_to(m)
folium_static(m)

# --- 5. LÓGICA DE PROCESAMIENTO ---
if ejecutar:
    try:
        creds_info = json.loads(st.secrets["gee"]["json"])
        creds = service_account.Credentials.from_service_account_info(creds_info, 
                scopes=['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/earthengine'])
        
        if not ee.data._credentials: ee.Initialize(creds)
        sheets = build('sheets', 'v4', credentials=creds)

        for nombre, info in CLIENTES.items():
            st.markdown(f"### 📍 Proyecto: {nombre}")
            p = ee.Geometry.Polygon(info['coords'])
            
            # Sensores e Índices
            s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED').filterBounds(p).sort('system:time_start', False).first()
            f_rep = datetime.fromtimestamp(s2.get('system:time_start').getInfo()/1000).strftime('%d/%m/%Y')
            
            idx = s2.expression('((B8-B4)/(B8+B4+0.5))*1.5', {'B8':s2.select('B8'),'B4':s2.select('B4')}).rename('sa')\
                .addBands(s2.normalizedDifference(['B3','B8']).rename('nd'))\
                .reduceRegion(ee.Reducer.mean(), p, 30).getInfo()

            # Diagnóstico Automático
            estado = "🟢 NORMAL"
            if idx['nd'] < umbral: estado = "🔴 ALERTA TÉCNICA"

            # Visualización de Resultados (Tarjetas)
            c1, c2, c3 = st.columns(3)
            c1.metric("Estado", estado)
            c2.metric("SAVI (Vigor)", f"{idx['sa']:.3f}")
            c3.metric("Agua/Nieve (ND)", f"{idx['nd']:.3f}")

            # Sincronización
            fila = [[f_rep, idx['sa'], idx['nd'], estado]]
            sheets.spreadsheets().values().append(spreadsheetId=info['sheet_id'], 
                range=f"{info['pestaña']}!A2", valueInputOption="USER_ENTERED", body={'values': fila}).execute()
            
            # Telegram
            requests.post(f"https://api.telegram.org/bot{T_TOKEN}/sendMessage", 
                         data={"chat_id": T_ID, "text": f"🛰 BioCore: {nombre}\nEstado: {estado}\nFecha: {f_rep}"})

        st.balloons()
        st.success("Sincronización Exitosa.")

    except Exception as e:
        st.error(f"Error: {e}")
