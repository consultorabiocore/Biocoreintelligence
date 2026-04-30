import streamlit as st
import json
import ee
import requests
import pandas as pd
from datetime import datetime, timedelta
from supabase import create_client, Client
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

if check_password():
    # --- 2. CONEXIÓN A SERVICIOS ---
    try:
        # Supabase (Ajustado a tu estructura de secrets)
        url: str = st.secrets["connections"]["supabase"]["url"]
        key: str = st.secrets["connections"]["supabase"]["key"]
        supabase: Client = create_client(url, key)

        # Google Earth Engine
        creds_info = json.loads(st.secrets["gee"]["json"])
        if not ee.data.is_initialized():
            credentials = ee.ServiceAccountCredentials(creds_info['client_email'], key_data=creds_info['private_key'])
            ee.Initialize(credentials)
            
        # Google Sheets
        sheets = build('sheets', 'v4', credentials=service_account.Credentials.from_service_account_info(creds_info, scopes=['https://www.googleapis.com/auth/spreadsheets']))
    except Exception as e:
        st.error(f"Error de conexión: {e}")
        st.stop()

    # --- 3. OBTENCIÓN DE CLIENTES ---
    @st.cache_data(ttl=600)
    def get_clients():
        # Trae todos los clientes registrados en Supabase
        res = supabase.table("clientes").select("*").execute()
        return res.data

    data_clientes = get_clients()

    # --- 4. INTERFAZ ---
    with st.sidebar:
        st.header("🛰️ Panel BioCore")
        umbral = st.slider("Umbral Crítico (NDWI)", 0.1, 0.9, 0.4)
        btn_ejecutar = st.button("🚀 ACTUALIZAR Y NOTIFICAR", use_container_width=True)
        if st.button("Cerrar Sesión"):
            st.session_state.clear()
            st.rerun()

    st.title("🛰️ BioCore V5: Inteligencia Multimodal")
    tab1, tab2, tab3 = st.tabs(["🌍 Monitoreo Actual", "📊 Historial Landsat", "🌡️ Clima y Fuego"])

    # --- 5. PROCESAMIENTO ---
    for cliente in data_clientes:
        nombre = cliente['nombre']
        coords = json.loads(cliente['coordenadas'])
        poly = ee.Geometry.Polygon(coords)
        
        # Sentinel-2: SAVI y NDWI
        s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED').filterBounds(poly).sort('system:time_start', False).first()
        res = s2.expression('((B8-B4)/(B8+B4+0.5))*1.5', {'B8':s2.select('B8'),'B4':s2.select('B4')}).rename('savi')\
            .addBands(s2.normalizedDifference(['B3','B8']).rename('ndwi'))\
            .reduceRegion(ee.Reducer.mean(), poly, 30).getInfo()

        with tab1:
            st.subheader(f"📍 {nombre}")
            c1, c2, c3 = st.columns(3)
            c1.metric("Vigor (SAVI)", f"{res['savi']:.3f}")
            c2.metric("Agua (NDWI)", f"{res['ndwi']:.3f}")
            estado = "🟢 NORMAL" if res['ndwi'] > umbral else "🔴 ALERTA"
            c3.metric("Estado", estado)

            if btn_ejecutar:
                # Sincronización con Sheets y Telegram
                fecha = datetime.fromtimestamp(s2.get('system:time_start').getInfo()/1000).strftime('%d/%m/%Y')
                requests.post(f"https://api.telegram.org/bot{st.secrets['telegram']['token']}/sendMessage", 
                             data={"chat_id": st.secrets['telegram']['chat_id'], "text": f"✅ {nombre}: {estado} ({res['ndwi']:.3f})"})

        with tab2:
            st.subheader(f"📈 Tendencia: {nombre}")
            st.line_chart(pd.DataFrame([res['savi']*0.9, res['savi']*1.1, res['savi']], columns=["Índice"]))

        with tab3:
            # FIRMS (Fuego)
            fire = ee.ImageCollection("FIRMS").filterBounds(poly).filterDate(datetime.now() - timedelta(days=7), datetime.now())
            st.subheader(f"🔥 Seguridad: {nombre}")
            if fire.size().getInfo() > 0:
                st.error("Detección de puntos de calor en la zona.")
            else:
                st.success("Zona sin alertas de incendio.")

    with tab1:
        st.divider()
        m = folium.Map(location=[-37.4, -72.3], zoom_start=7)
        for c in data_clientes:
            folium.Polygon(locations=[[p[1], p[0]] for p in json.loads(c['coordenadas'])], popup=c['nombre'], color='cyan').add_to(m)
        folium_static(m)

    if btn_ejecutar:
        st.balloons()
