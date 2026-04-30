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
            # Usamos las credenciales de tus secrets
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
        # Supabase ajustado a tus secrets
        url: str = st.secrets["connections"]["supabase"]["url"]
        key: str = st.secrets["connections"]["supabase"]["key"]
        supabase: Client = create_client(url, key)

        # Google Earth Engine
        creds_info = json.loads(st.secrets["gee"]["json"])
        if not ee.data.is_initialized():
            credentials = ee.ServiceAccountCredentials(creds_info['client_email'], key_data=creds_info['private_key'])
            ee.Initialize(credentials)
    except Exception as e:
        st.error(f"Error de conexión: {e}")
        st.stop()

    # --- 3. OBTENCIÓN DE DATOS (Ajustado a tu imagen) ---
    @st.cache_data(ttl=600)
    def get_projects():
        # Cambiamos "clientes" por "usuarios" que es el nombre en tu SQL
        res = supabase.table("usuarios").select("*").execute()
        return res.data

    data_proyectos = get_projects()

    # --- 4. INTERFAZ ---
    tab1, tab2, tab3 = st.tabs(["🌍 Monitoreo Actual", "📊 Historial", "🌡️ Clima"])

    with st.sidebar:
        st.header("🛰️ Panel BioCore")
        btn_ejecutar = st.button("🚀 ACTUALIZAR Y NOTIFICAR", use_container_width=True)

    # --- 5. PROCESAMIENTO ---
    for proy in data_proyectos:
        # Ajustamos los nombres de columnas a tu SQL: "Proyecto" y "Coordenadas"
        nombre = proy.get('Proyecto', 'Sin Nombre')
        raw_coords = proy.get('Coordenadas')
        
        if not raw_coords:
            continue

        coords = json.loads(raw_coords)
        poly = ee.Geometry.Polygon(coords)
        
        # Procesamiento Sentinel-2 (SAVI)
        s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED').filterBounds(poly).sort('system:time_start', False).first()
        res = s2.expression('((B8-B4)/(B8+B4+0.5))*1.5', {'B8':s2.select('B8'),'B4':s2.select('B4')}).rename('savi')\
            .reduceRegion(ee.Reducer.mean(), poly, 30).getInfo()

        with tab1:
            st.subheader(f"📍 Proyecto: {nombre}")
            st.metric("Vigor Vegetacional (SAVI)", f"{res['savi']:.3f}")
            
            if btn_ejecutar:
                # Notificación Telegram
                requests.post(f"https://api.telegram.org/bot{st.secrets['telegram']['token']}/sendMessage", 
                             data={"chat_id": st.secrets['telegram']['chat_id'], "text": f"✅ {nombre} monitoreado."})

    with tab1:
        st.divider()
        m = folium.Map(location=[-30.0, -70.0], zoom_start=5) # Centrado hacia Pascua Lama
        for p in data_proyectos:
            if p.get('Coordenadas'):
                folium.Polygon(locations=[[c[1], c[0]] for c in json.loads(p['Coordenadas'])], 
                               popup=p['Proyecto'], color='cyan').add_to(m)
        folium_static(m)
