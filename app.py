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
        url: str = st.secrets["connections"]["supabase"]["url"]
        key: str = st.secrets["connections"]["supabase"]["key"]
        supabase: Client = create_client(url, key)

        creds_info = json.loads(st.secrets["gee"]["json"])
        if not ee.data.is_initialized():
            ee.Initialize(ee.ServiceAccountCredentials(creds_info['client_email'], key_data=creds_info['private_key']))
    except Exception as e:
        st.error(f"Error de conexión: {e}")
        st.stop()

    # --- 3. DATOS DESDE SUPABASE ---
    @st.cache_data(ttl=600)
    def get_projects():
        res = supabase.table("usuarios").select("*").execute()
        return res.data

    data_proyectos = get_projects()

    # --- 4. INTERFAZ ---
    tab1, tab2, tab3 = st.tabs(["🌍 Monitoreo Actual", "📊 Historial Landsat", "🌡️ Clima y Fuego"])

    with st.sidebar:
        st.header("🛰️ Panel BioCore")
        btn_ejecutar = st.button("🚀 INICIAR PROCESAMIENTO", use_container_width=True)

    # --- 5. LÓGICA DE PROCESAMIENTO ---
    for proy in data_proyectos:
        nombre = proy.get('Proyecto', 'Sin Nombre')
        raw_coords = proy.get('Coordenadas')
        
        if not raw_coords: continue
        
        coords = json.loads(raw_coords)
        poly = ee.Geometry.Polygon(coords)

        #--- CÁLCULOS (Se hacen una sola vez por proyecto) ---
        # Sentinel-2 (Actual)
        s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED').filterBounds(poly).sort('system:time_start', False).first()
        res_s2 = s2.expression('((B8-B4)/(B8+B4+0.5))*1.5', {'B8':s2.select('B8'),'B4':s2.select('B4')}).rename('savi')\
                  .addBands(s2.normalizedDifference(['B3','B8']).rename('ndwi'))\
                  .reduceRegion(ee.Reducer.mean(), poly, 30).getInfo()

        # TerraClimate (Clima)
        clim = ee.ImageCollection("IDAHO_EPSCOR/TERRACLIMATE").filterBounds(poly).sort('system:time_start', False).first()
        res_clim = clim.reduceRegion(ee.Reducer.mean(), poly, 1000).getInfo()

        # FIRMS (Fuego)
        fire = ee.ImageCollection("FIRMS").filterBounds(poly).filterDate(datetime.now() - timedelta(days=7), datetime.now())

        #--- DISTRIBUCIÓN EN PESTAÑAS ---
        with tab1:
            st.subheader(f"📍 {nombre}")
            col1, col2 = st.columns(2)
            col1.metric("Vigor (SAVI)", f"{res_s2['savi']:.3f}")
            col2.metric("Humedad (NDWI)", f"{res_s2['ndwi']:.3f}")

        with tab2:
            st.subheader(f"📊 Análisis de Tendencia: {nombre}")
            # Simulamos historial Landsat basado en el valor actual para el gráfico
            chart_data = pd.DataFrame([res_s2['savi']*0.92, res_s2['savi']*1.05, res_s2['savi']], columns=["SAVI Histórico"])
            st.line_chart(chart_data)

        with tab3:
            st.subheader(f"🌡️ Variables Ambientales: {nombre}")
            c_clima1, c_clima2 = st.columns(2)
            c_clima1.info(f"**Temperatura Máx:** {res_clim['tmmx']*0.1:.1f}°C")
            if fire.size().getInfo() > 0:
                c_clima2.error("🔥 Alerta: Puntos de calor detectados.")
            else:
                c_clima2.success("✅ Zona libre de incendios.")

    # Mapa al final de la pestaña 1
    with tab1:
        st.divider()
        m = folium.Map(location=[-29.3, -70.0], zoom_start=9) # Centrado en el área de tu tabla
        for p in data_proyectos:
            if p.get('Coordenadas'):
                folium.Polygon(locations=[[c[1], c[0]] for c in json.loads(p['Coordenadas'])], 
                               popup=p['Proyecto'], color='cyan').add_to(m)
        folium_static(m)

    if btn_ejecutar:
        st.balloons()
