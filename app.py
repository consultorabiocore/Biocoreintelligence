import streamlit as st
import ee
import json
import folium
import os
import base64
from streamlit_folium import st_folium

# --- CONFIGURACIÓN ESTRATÉGICA ---
st.set_page_config(page_title="BioCore Intelligence", layout="wide")

# Ruta del logo - Ajusta esto según tu carpeta en GitHub
LOGO_PATH = os.path.join("assets", "logo_biocore.png")

def inicializar_gee():
    try:
        if 'gee_auth' not in st.session_state:
            info = json.loads(st.secrets["GEE_JSON"])
            creds = ee.ServiceAccountCredentials(info['client_email'], key_data=info['private_key'].replace("\\n", "\n"))
            ee.Initialize(creds)
            st.session_state.gee_auth = True
        return True
    except: return False

# --- FUNCIÓN PARA MOSTRAR LOGO ---
def mostrar_logo():
    if os.path.exists(LOGO_PATH):
        with open(LOGO_PATH, "rb") as f:
            data = base64.b64encode(f.read()).decode()
            st.sidebar.markdown(
                f'<div style="text-align:center"><img src="data:image/png;base64,{data}" width="150"></div>', 
                unsafe_allow_html=True
            )
    else:
        st.sidebar.title("🌿 BioCore")

# --- LÓGICA DE NAVEGACIÓN ---
if 'auth' not in st.session_state: st.session_state.auth = False

mostrar_logo() # El logo siempre visible en la pestaña del lado

with st.sidebar:
    st.markdown("---")
    if not st.session_state.auth:
        st.subheader("Acceso Restringido")
        u = st.text_input("Usuario")
        p = st.text_input("Clave", type="password")
        if st.button("Entrar"):
            if u == "admin" and p == "loreto2026":
                st.session_state.auth = True
                st.rerun()
    else:
        st.success("Sesión: Loreto Campos")
        proy_name = st.text_input("Proyecto Actual:", "Pascua Lama")
        tipo_auditoria = st.selectbox("Capa de Análisis:", ["Minería", "Glaciares", "Humedales"])
        if st.button("Cerrar Sesión"):
            st.session_state.auth = False
            st.rerun()

# --- CUERPO PRINCIPAL (MAPA Y DATOS) ---
if st.session_state.auth and inicializar_gee():
    st.title(f"Visualización Satelital: {proy_name}")
    
    col_mapa, col_datos = st.columns([2, 1])

    with col_datos:
        st.markdown("**1. Configuración Geográfica**")
        raw_coords = st.text_area("Pegue coordenadas JSON aquí:", height=200, placeholder="[[-70.03, -29.31], ...]")
        
        geom = None
        if raw_coords:
            try:
                puntos = json.loads(raw_coords)
                geom = ee.Geometry.Polygon(puntos)
                st.success("Polígono detectado")
            except:
                st.error("Error en formato de coordenadas")

    with col_mapa:
        if geom:
            centro = geom.centroid().coordinates().getInfo()[::-1]
            m = folium.Map(location=centro, zoom_start=14)
        else:
            m = folium.Map(location=[-33.45, -70.66], zoom_start=4)
        
        # Capa Satelital tipo Google (Limpia como Satellites on Fire)
        folium.TileLayer(
            tiles='https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}',
            attr='Google Satellite',
            name='Google Satellite'
        ).add_to(m)

        if geom:
            folium.GeoJson(data=geom.getInfo(), style_function=lambda x: {'color': '#00ff00', 'weight': 2}).add_to(m)

        # Ajuste de tamaño para que se vea bien en celular
        st_folium(m, width="100%", height=400)

    if geom:
        st.markdown("---")
        if st.button("🚀 EJECUTAR REPORTE DIARIO"):
            st.info("Calculando índices ambientales...")
