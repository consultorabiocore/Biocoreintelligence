import streamlit as st
import json
import ee
import requests
from datetime import datetime
from googleapiclient.discovery import build
from google.oauth2 import service_account
from streamlit_folium import folium_static
import folium

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="BioCore V5 Lite", layout="wide")
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

st.title("🛰️ BioCore V5 - Monitor Directo")

# --- 2. MAPA EN PANTALLA PRINCIPAL (No en la pestaña lateral) ---
st.subheader("📍 Ubicación de Proyectos")
try:
    m = folium.Map(location=[-35.0, -71.0], zoom_start=5)
    for n, i in CLIENTES.items():
        # Invertir coordenadas para Folium [lat, lon]
        p_folium = [[c[1], c[0]] for c in i['coords']]
        folium.Polygon(locations=p_folium, popup=n, color='blue', fill=True).add_to(m)
    folium_static(m, width=350, height=300) # Tamaño optimizado para móvil
except Exception as e:
    st.error(f"Error cargando mapa: {e}")

# --- 3. BOTÓN DE EJECUCIÓN (Grande y central) ---
st.divider()
if st.button("🚀 INICIAR ESCANEO FORZADO", use_container_width=True):
    try:
        creds_info = json.loads(st.secrets["gee"]["json"])
        creds = service_account.Credentials.from_service_account_info(creds_info, 
                scopes=['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/earthengine'])
        
        if not ee.data._credentials:
            ee.Initialize(creds)
        
        sheets = build('sheets', 'v4', credentials=creds)

        for nombre, info in CLIENTES.items():
            st.info(f"🔍 Procesando {nombre}...")
            p = ee.Geometry.Polygon(info['coords'])
            
            s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED').filterBounds(p).sort('system:time_start', False).first()
            f_rep = datetime.fromtimestamp(s2.get('system:time_start').getInfo()/1000).strftime('%d/%m/%Y')
            
            idx = s2.expression('((B8-B4)/(B8+B4+0.5))*1.5', {'B8':s2.select('B8'),'B4':s2.select('B4')}).rename('sa')\
                .addBands(s2.normalizedDifference(['B3','B8']).rename('nd'))\
                .reduceRegion(ee.Reducer.mean(), p, 30).getInfo()

            estado = "🟢 NORMAL"
            if idx['nd'] < UMBRAL: estado = "🔴 ALERTA"

            # Renderizado directo de resultados
            st.success(f"**Resultado {nombre}**")
            st.markdown(f"**Fecha:** {f_rep} | **Estado:** {estado}")
            st.write(f"📈 SAVI: `{idx['sa']:.3f}` | 📉 ND: `{idx['nd']:.3f}`")

            # Sincronización
            fila = [[f_rep, idx['sa'], idx['nd'], estado]]
            sheets.spreadsheets().values().append(spreadsheetId=info['sheet_id'], range=f"{info['pestaña']}!A2", valueInputOption="USER_ENTERED", body={'values': fila}).execute()
            
        st.balloons()

    except Exception as e:
        st.error(f"Error técnico: {str(e)}")
else:
    st.warning("⚠️ Presiona el botón para actualizar datos.")
