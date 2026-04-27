import streamlit as st
import ee
import json
import folium
import os
import base64
from streamlit_folium import st_folium

# --- CONFIGURACIÓN DE BIOCORE ---
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

# --- PESTAÑA LATERAL (ESTILO SATELLITES ON FIRE) ---
with st.sidebar:
    # 1. Tu Logo arriba
    if os.path.exists(LOGO_PATH):
        with open(LOGO_PATH, "rb") as f:
            data = base64.b64encode(f.read()).decode()
            st.markdown(f'<div style="text-align:center"><img src="data:image/png;base64,{data}" width="160"></div>', unsafe_allow_html=True)
    
    st.markdown("---")
    
    if not st.session_state.get('auth', False):
        st.subheader("Iniciar Sesión")
        u = st.text_input("Usuario")
        p = st.text_input("Clave", type="password")
        if st.button("Ingresar"):
            if u == "admin" and p == "loreto2026":
                st.session_state.auth = True
                st.rerun()
    else:
        # Pestaña del lado para los datos del cliente
        st.subheader("📂 Gestión de Proyectos")
        nombre_cliente = st.text_input("Nombre del Cliente/Proyecto:", value="", placeholder="Ej: Minera X")
        tipo_sector = st.selectbox("Capa de Análisis:", ["Seleccione...", "Minería", "Glaciares", "Humedales", "Forestal"])
        
        st.markdown("---")
        if st.button("Cerrar Sesión"):
            st.session_state.auth = False
            st.rerun()

# --- PANEL PRINCIPAL ---
if st.session_state.get('auth', False) and inicializar_gee():
    st.title("🛰 Consola de Visualización")

    col_map, col_ctrl = st.columns([2, 1])

    with col_ctrl:
        st.markdown("### 📍 Área de Estudio")
        
        # TEXTO DE FONDO PARA QUE SEPAS CÓMO ESCRIBIRLO
        ejemplo_formato = "[[-70.01, -29.31], [-70.03, -29.31], [-70.03, -29.33], [-70.01, -29.33], [-70.01, -29.31]]"
        
        raw_input = st.text_area(
            "Ingrese las coordenadas del polígono:", 
            height=300,
            placeholder=f"Copie el formato JSON aquí:\n{ejemplo_formato}"
        )
        
        geom = None
        if raw_input:
            try:
                # Intentamos leer el JSON
                puntos = json.loads(raw_input)
                geom = ee.Geometry.Polygon(puntos)
                st.success("✅ Polígono cargado")
            except:
                st.error("❌ Formato incorrecto. Recuerda usar corchetes [ ] y comas.")

    with col_map:
        if geom:
            centro = geom.centroid().coordinates().getInfo()[::-1]
            m = folium.Map(location=centro, zoom_start=14)
        else:
            # Mapa base de Chile
            m = folium.Map(location=[-37.0, -72.0], zoom_start=5)
        
        folium.TileLayer(
            tiles='https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}',
            attr='Google',
            name='Google Satellite'
        ).add_to(m)

        if geom:
            folium.GeoJson(data=geom.getInfo(), style_function=lambda x: {'color': '#39FF14', 'weight': 2, 'fillOpacity': 0.1}).add_to(m)

        st_folium(m, width="100%", height=450)

    # Botón final de reporte
    if geom and nombre_cliente != "":
        if st.button(f"🚀 GENERAR REPORTE DIARIO PARA {nombre_cliente.upper()}"):
            st.info(f"Analizando {tipo_sector}... Enviando reporte a Telegram.")
