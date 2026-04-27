import streamlit as st
import ee
import json
import folium
from streamlit_folium import st_folium
from folium.plugins import Draw

# --- CONFIGURACIÓN INICIAL ---
st.set_page_config(page_title="BioCore SaaS", layout="wide")

def iniciar_gee():
    if "GEE_JSON" in st.secrets:
        try:
            # Cargamos y limpiamos la llave
            info = json.loads(st.secrets["GEE_JSON"])
            # Esta línea es la que arregla el error de Padding
            llave = info['private_key'].replace('\\n', '\n').strip()
            
            creds = ee.ServiceAccountCredentials(info['client_email'], key_data=llave)
            ee.Initialize(creds)
        except Exception as e:
            st.error(f"❌ Error de conexión: {e}")
    else:
        st.warning("⚠️ Esperando configuración de GEE_JSON...")

iniciar_gee()

# --- INTERFAZ ---
if 'auth' not in st.session_state:
    st.session_state.auth = False

with st.sidebar:
    # Intento de cargar logo
    try:
        st.image("assets/logo.png", use_container_width=True)
    except:
        st.subheader("🛰️ BioCore Intelligence")

    if not st.session_state.auth:
        u = st.text_input("Usuario")
        p = st.text_input("Password", type="password")
        if st.button("Entrar"):
            if u == "admin" and p == "loreto2026":
                st.session_state.auth = True
                st.rerun()
    else:
        st.success("Conexión Exitosa")
        if st.button("Cerrar Sesión"):
            st.session_state.auth = False
            st.rerun()

# --- PANEL PRINCIPAL ---
if st.session_state.auth:
    st.header("👨‍💻 Dashboard de Monitoreo")
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        # Mapa centrado en Chile
        m = folium.Map(location=[-37.28, -72.70], zoom_start=12)
        Draw(export=True).add_to(m)
        st_folium(m, width="100%", height=500)
    
    with col2:
        st.write("### Controles")
        st.info("Dibuja un polígono en el mapa para analizar los índices ambientales.")
else:
    st.info("Inicie sesión para acceder a las herramientas de BioCore.")
