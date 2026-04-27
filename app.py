import streamlit as st
import ee
import json
import folium
import os
import base64
from streamlit_folium import st_folium

# --- CONFIGURACIÓN DE PANTALLA ---
st.set_page_config(page_title="BioCore Intelligence", layout="wide")

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

# --- LÓGICA DE ACCESO ---
if 'auth' not in st.session_state: st.session_state.auth = False

# --- PESTAÑA LATERAL (SIDEBAR) ---
with st.sidebar:
    # Carga del Logo
    if os.path.exists(LOGO_PATH):
        with open(LOGO_PATH, "rb") as f:
            data = base64.b64encode(f.read()).decode()
            st.markdown(f'<div style="text-align:center"><img src="data:image/png;base64,{data}" width="160"></div>', unsafe_allow_html=True)
    else:
        st.title("BioCore")
    
    st.markdown("---")
    
    if not st.session_state.auth:
        u = st.text_input("Usuario")
        p = st.text_input("Clave", type="password")
        if st.button("Ingresar"):
            if u == "admin" and p == "loreto2026":
                st.session_state.auth = True
                st.rerun()
    else:
        # Aquí los campos aparecen vacíos para que tú los llenes
        st.subheader("Datos del Cliente")
        nombre_cliente = st.text_input("Nombre del Proyecto/Cliente:", value="")
        tipo_sector = st.selectbox("Tipo de Análisis:", ["Seleccione...", "Minería", "Glaciares", "Humedales", "Agrícola", "Forestal"])
        
        if st.button("Cerrar Sesión"):
            st.session_state.auth = False
            st.rerun()

# --- PANEL CENTRAL ---
if st.session_state.auth and inicializar_gee():
    # Título dinámico
    if nombre_cliente:
        st.title(f"Monitoreo: {nombre_cliente}")
    else:
        st.title("Consola de Vigilancia Satelital")

    col_map, col_ctrl = st.columns([2, 1])

    with col_ctrl:
        st.markdown("### 📍 Área de Estudio")
        # Cuadro de coordenadas sin texto de ejemplo que moleste
        raw_input = st.text_area("Ingrese las coordenadas del polígono:", height=250)
        
        geom = None
        if raw_input:
            try:
                puntos = json.loads(raw_input)
                geom = ee.Geometry.Polygon(puntos)
                st.success("Geometría cargada")
            except:
                st.error("Error en los datos. Revise el formato.")

    with col_map:
        if geom:
            centro = geom.centroid().coordinates().getInfo()[::-1]
            m = folium.Map(location=centro, zoom_start=14)
        else:
            # Vista general de Chile si no hay datos
            m = folium.Map(location=[-37.0, -72.0], zoom_start=5)
        
        # Capa Satelital limpia (Estilo Satellites on Fire)
        folium.TileLayer(
            tiles='https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}',
            attr='Google',
            name='Satélite'
        ).add_to(m)

        if geom:
            folium.GeoJson(data=geom.getInfo(), style_function=lambda x: {'color': '#39FF14', 'weight': 2, 'fillOpacity': 0.1}).add_to(m)

        st_folium(m, width="100%", height=450)

    # Botón de acción al final
    if geom and nombre_cliente:
        if st.button(f"🚀 GENERAR REPORTE PARA {nombre_cliente.upper()}"):
            st.info("Procesando índices... El reporte se enviará a su Telegram.")
