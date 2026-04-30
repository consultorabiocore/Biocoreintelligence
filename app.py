import streamlit as st
import json
import ee
import requests
from datetime import datetime
from googleapiclient.discovery import build
from google.oauth2 import service_account

# --- 1. CONFIGURACIÓN MÍNIMA ---
st.set_page_config(page_title="BioCore V5", layout="centered")

T_TOKEN = st.secrets["telegram"]["token"]
T_ID = st.secrets["telegram"]["chat_id"]
UMBRAL = 0.4

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

# --- 2. LÓGICA DE VISUALIZACIÓN ---
st.title("🛰️ BioCore V5")
st.write("Estado: Listo para escanear.")

# Usamos session_state para forzar que los datos se queden en pantalla
if 'resultados' not in st.session_state:
    st.session_state.resultados = []

if st.button("🚀 INICIAR ESCANEO AHORA", use_container_width=True):
    try:
        with st.status("Conectando con Satélites...", expanded=True) as status:
            # Autenticación Limpia
            creds_info = json.loads(st.secrets["gee"]["json"])
            creds = service_account.Credentials.from_service_account_info(creds_info, 
                    scopes=['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/earthengine'])
            
            if not ee.data._credentials:
                ee.Initialize(creds)
            
            sheets = build('sheets', 'v4', credentials=creds)
            st.session_state.resultados = [] # Limpiar previos

            for nombre, info in CLIENTES.items():
                st.write(f"Procesando {nombre}...")
                p = ee.Geometry.Polygon(info['coords'])
                
                # Análisis ultra rápido
                s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED').filterBounds(p).sort('system:time_start', False).first()
                f_rep = datetime.fromtimestamp(s2.get('system:time_start').getInfo()/1000).strftime('%d/%m/%Y')
                
                indices = s2.expression('((B8-B4)/(B8+B4+0.5))*1.5', {'B8':s2.select('B8'),'B4':s2.select('B4')}).rename('sa')\
                    .addBands(s2.normalizedDifference(['B3','B8']).rename('nd'))\
                    .reduceRegion(ee.Reducer.mean(), p, 30).getInfo()

                estado = "🟢 NORMAL"
                if info['tipo'] == "HUMEDAL" and indices['nd'] < UMBRAL: estado = "🔴 ALERTA HÍDRICA"
                elif info['tipo'] == "GLACIAR" and indices['nd'] < UMBRAL: estado = "🔴 ALERTA NIEVE"

                # Guardar resultado en el estado de la sesión
                res = {"nombre": nombre, "fecha": f_rep, "savi": indices['sa'], "nd": indices['nd'], "estado": estado}
                st.session_state.resultados.append(res)
                
                # Sincronización silenciosa a Sheets
                fila = [[f_rep, indices['sa'], indices['nd'], estado]]
                sheets.spreadsheets().values().append(spreadsheetId=info['sheet_id'], range=f"{info['pestaña']}!A2", valueInputOption="USER_ENTERED", body={'values': fila}).execute()
            
            status.update(label="✅ Escaneo Exitoso", state="complete", expanded=False)
            st.balloons()

    except Exception as e:
        st.error(f"Error de conexión: {str(e)}")

# --- 3. RENDERIZADO FORZADO ---
# Esto asegura que los datos aparezcan sí o sí abajo del botón
if st.session_state.resultados:
    for r in st.session_state.resultados:
        with st.container():
            st.markdown(f"### 📍 {r['nombre']}")
            st.info(f"**Estado:** {r['estado']} | **Fecha:** {r['fecha']}")
            st.write(f"🌿 SAVI: `{r['savi']:.3f}` | 💧 NDWI: `{r['nd']:.3f}`")
            st.divider()
