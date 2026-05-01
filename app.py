import streamlit as st
import ee
import folium
from streamlit_folium import folium_static
import json
import pandas as pd
import requests
from datetime import datetime
from supabase import create_client, Client

# 1. ESTILO PARA EVITAR PANTALLA NEGRA
st.markdown("<style>body { background-color: #f0f2f6; }</style>", unsafe_allow_html=True)

# 2. CONEXIÓN SEGURA
@st.cache_resource
def conectar_db():
    return create_client(st.secrets["connections"]["supabase"]["url"], st.secrets["connections"]["supabase"]["key"])

try:
    supabase = conectar_db()
except:
    st.error("Error en Secrets de Supabase")
    st.stop()

# 3. MOTOR GEE
def iniciar_gee():
    if not ee.data.is_initialized():
        try:
            creds = json.loads(st.secrets["gee"]["json"])
            ee_creds = ee.ServiceAccountCredentials(creds['client_email'], key_data=creds['private_key'])
            ee.Initialize(ee_creds)
        except: st.error("Error en credenciales GEE")

# 4. MAPA (VERSIÓN LITE)
def dibujar_mapa(coords_json):
    try:
        js = json.loads(coords_json) if isinstance(coords_json, str) else coords_json
        raw = js['coordinates'][0] if 'coordinates' in js else js
        puntos = [[float(p[1]), float(p[0])] for p in raw]
        m = folium.Map(location=puntos[0], zoom_start=15, tiles='OpenStreetMap') # Cambiado a OSM para evitar fallos de Google
        folium.Polygon(locations=puntos, color="red", weight=3).add_to(m)
        return m
    except: return folium.Map(location=[-37.2, -72.7], zoom_start=10)

# --- APP ---
st.title("🛰️ BioCore Intelligence")

tab1, tab2 = st.tabs(["🚀 Vigilancia", "📊 Historial Excel"])

try:
    proyectos = supabase.table("usuarios").select("*").execute().data
except:
    proyectos = []

with tab1:
    if proyectos:
        for p in proyectos:
            with st.container():
                st.subheader(p['Proyecto'])
                c1, c2 = st.columns([3,1])
                with c1:
                    mapa = dibujar_mapa(p['Coordenadas'])
                    folium_static(mapa, width=700, height=400)
                with c2:
                    if st.button("🚀 Reporte Largo", key=p['Proyecto']):
                        st.write("Procesando...")
    else: st.warning("Sin datos.")

with tab2:
    st.subheader("Datos para Excel")
    try:
        hist = supabase.table("historial_reportes").select("*").execute().data
        if hist:
            df = pd.DataFrame(hist)
            st.dataframe(df)
            st.download_button("📥 Bajar CSV", df.to_csv().encode('utf-8'), "BioCore.csv")
    except: st.info("Historial vacío.")
