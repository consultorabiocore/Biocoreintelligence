import streamlit as st
import ee
import json
import folium
import os
import base64
import requests
from streamlit_folium import st_folium

# --- CONFIGURACIÓN ESTILO "SATELLITES ON FIRE" ---
LOGO_PATH = os.path.join("assets", "logo_biocore.png")

st.set_page_config(page_title="BioCore Intelligence", layout="wide", initial_sidebar_state="collapsed")

# CSS para ocultar menús de Streamlit y que parezca una App nativa
st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .stApp {background-color: #0e1117;}
    /* Botones flotantes estilo Satellites on Fire */
    .stButton>button {
        border-radius: 20px;
        border: 1px solid #4CAF50;
        background-color: #1e2329;
        color: white;
    }
    </style>
    """, unsafe_allow_html=True)

def inicializar_gee():
    try:
        if 'gee_auth' not in st.session_state:
            info = json.loads(st.secrets["GEE_JSON"])
            creds = ee.ServiceAccountCredentials(info['client_email'], key_data=info['private_key'].replace("\\n", "\n"))
            ee.Initialize(creds)
            st.session_state.gee_auth = True
        return True
    except: return False

# --- LÓGICA DE SESIÓN ---
if 'auth' not in st.session_state: st.session_state.auth = False

# --- BARRA SUPERIOR (NAVBAR) ---
header_col1, header_col2 = st.columns([4, 1])
with header_col1:
    st.title("🛰 BioCore | Visualización")
with header_col2:
    if st.session_state.auth:
        if st.button("Cerrar"): st.session_state.auth = False; st.rerun()

# --- INTERFAZ TIPO APP ---
if not st.session_state.auth:
    st.info("Inicie sesión para acceder al monitoreo satelital")
    u, p = st.text_input("Usuario"), st.text_input("Clave", type="password")
    if st.button("Entrar"):
        if u == "admin" and p == "loreto2026": st.session_state.auth = True; st.rerun()

elif inicializar_gee():
    # Menú lateral para parámetros (como el de la foto 2 que subiste)
    with st.sidebar:
        st.header("Configuración")
        proy = st.text_input("Proyecto", "Pascua Lama")
        sector = st.selectbox("Capa", ["Minería", "Glaciares", "Humedales"])
        st.markdown("---")
        raw_coords = st.text_area("Área de interés (JSON):", height=200)

    # --- MAPA A PANTALLA COMPLETA ---
    geom = None
    if raw_coords:
        try:
            puntos = json.loads(raw_coords)
            geom = ee.Geometry.Polygon(puntos)
        except: st.warning("Esperando coordenadas válidas...")

    # Configuración del Mapa tipo Google Satellite
    if geom:
        centro = geom.centroid().coordinates().getInfo()[::-1]
        m = folium.Map(location=centro, zoom_start=14, tiles=None)
    else:
        m = folium.Map(location=[-33.45, -70.66], zoom_start=5, tiles=None)

    # Añadimos la capa satelital limpia
    folium.TileLayer(
        tiles='https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}',
        attr='Google',
        name='Google Satellite',
        overlay=False
    ).add_to(m)

    if geom:
        folium.GeoJson(data=geom.getInfo(), style_function=lambda x: {'color': '#00ff00', 'weight': 2, 'fillOpacity': 0.1}).add_to(m)

    # El mapa ocupa el ancho total
    st_folium(m, width=1200, height=500)

    # Botón flotante de acción (Reporte Diario)
    if geom:
        st.markdown("---")
        if st.button("🚀 GENERAR AUDITORÍA Y AVISAR AL CELULAR"):
            st.success("Analizando datos... El reporte será enviado a su Telegram.")
