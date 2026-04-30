import streamlit as st
import json
import ee
import requests
import pandas as pd
from datetime import datetime, timedelta
from googleapiclient.discovery import build
from google.oauth2 import service_account
from streamlit_folium import folium_static
import folium

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="BioCore Intelligence V5", layout="wide", page_icon="🛰️")

def check_password():
    if "password_correct" not in st.session_state:
        st.title("🛰️ BioCore V5 - Acceso")
        u = st.text_input("Usuario").lower().strip()
        p = st.text_input("Contraseña", type="password").strip()
        if st.button("Entrar"):
            if u == st.secrets["auth"]["user"].lower().strip() and p == str(st.secrets["auth"]["password"]).strip():
                st.session_state["password_correct"] = True
                st.rerun()
            else:
                st.error("Credenciales incorrectas")
        return False
    return True

# --- FLUJO PRINCIPAL (TODO ESTO VA IDENTADO DENTRO DEL IF) ---
if check_password():
    # --- 2. INICIALIZACIÓN DE SERVICIOS ---
    try:
        # Usamos ee.ServiceAccountCredentials para evitar errores de versión
        creds_info = json.loads(st.secrets["gee"]["json"])
        credentials = ee.ServiceAccountCredentials(
            creds_info['client_email'], 
            key_data=creds_info['private_key']
        )
        if not ee.data.get_info_all():
            ee.Initialize(credentials)
            
        sheets_creds = service_account.Credentials.from_service_account_info(
            creds_info, scopes=['https://www.googleapis.com/auth/spreadsheets']
        )
        sheets = build('sheets', 'v4', credentials=sheets_creds)
    except Exception as e:
        st.error(f"Error de conexión técnica: {e}")

    # --- 3. DICCIONARIO MULTIMODAL ---
    CLIENTES = {
        "Laguna Señoraza (Laja)": {
            "coords": [[-72.715,-37.275],[-72.715,-37.285],[-72.690,-37.285],[-72.690,-37.270]], 
            "sheet_id": "1x6yAXNNlea3e43rijJu0aqcRpe4oP3BEnzgSgLuG1vU", "pest": "Humedales"
        },
        "Pascua Lama (Cordillera)": {
            "coords": [[-70.033,-29.316],[-70.016,-29.316],[-70.016,-29.333],[-70.033,-29.333]], 
            "sheet_id": "1UTrDs939rPlVIR1OTIwbJ6rM3FazgjX43YnJdue-Dmc", "pest": "Mineria"
        }
    }

    # --- 4. BARRA LATERAL ---
    with st.sidebar:
        st.success(f"Conectada: {st.secrets['auth']['user']}")
        umbral = st.slider("Umbral Crítico", 0.1, 0.9, 0.4)
        ejecutar = st.button("🚀 INICIAR MONITOREO TOTAL", use_container_width=True)
        if st.button("Salir"):
            st.session_state.clear()
            st.rerun()

    st.title("🛰️ BioCore V5: Monitoreo Multimodal")
    
    tab1, tab2, tab3 = st.tabs(["🌍 Actual", "📊 Histórico", "🔥 Fuego"])

    with tab1:
        m = folium.Map(location=[-35.0, -71.0], zoom_start=5)
        for n, i in CLIENTES.items():
            p_fol = [[c[1], c[0]] for c in i['coords']]
            folium.Polygon(locations=p_fol, popup=n, color='cyan', fill=True).add_to(m)
        folium_static(m)

    if ejecutar:
        with tab1:
            for nombre, info in CLIENTES.items():
                st.write(f"### Analizando: {nombre}")
                poly = ee.Geometry.Polygon(info['coords'])
                
                # Sentinel-2: SAVI, NDWI, NDSI, Arcillas
                s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED').filterBounds(poly).sort('system:time_start', False).first()
                fecha = datetime.fromtimestamp(s2.get('system:time_start').getInfo()/1000).strftime('%d/%m/%Y')
                
                res = s2.expression(
                    '((B8-B4)/(B8+B4+0.5))*1.5', {'B8':s2.select('B8'),'B4':s2.select('B4')}
                ).rename('savi').addBands(
                    s2.normalizedDifference(['B3','B8']).rename('ndwi')
                ).reduceRegion(ee.Reducer.mean(), poly, 30).getInfo()

                # Sentinel-1: SAR (Atraviesa nubes)
                s1 = ee.ImageCollection('COPERNICUS/S1_GRD').filterBounds(poly).sort('system:time_start', False).first()
                sar_db = s1.reduceRegion(ee.Reducer.mean(), poly, 30).getInfo()['VV']

                estado = "🟢 NORMAL" if res['ndwi'] > umbral else "🔴 ALERTA"
                st.metric(f"{nombre}", f"{estado}", f"NDWI: {res['ndwi']:.3f}")

                # Reporte Sheets y Telegram
                fila = [[fecha, res['savi'], res['ndwi'], sar_db, estado]]
                sheets.spreadsheets().values().append(spreadsheetId=info['sheet_id'], 
                    range=f"{info['pest']}!A2", valueInputOption="USER_ENTERED", body={'values': fila}).execute()
                
                requests.post(f"https://api.telegram.org/bot{st.secrets['telegram']['token']}/sendMessage", 
                             data={"chat_id": st.secrets['telegram']['chat_id'], "text": f"✅ {nombre}: {estado}"})
        st.balloons()
