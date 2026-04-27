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
            # 1. Cargamos el JSON
            info = json.loads(st.secrets["GEE_JSON"])
            
            # 2. LIMPIEZA BLINDADA (Solución definitiva a InvalidPadding)
            pk = info['private_key']
            # Quitamos comillas extras, corregimos saltos de línea y eliminamos espacios laterales
            pk = pk.replace("\\n", "\n").replace('"', '').strip()
            
            # 3. Inicialización
            creds = ee.ServiceAccountCredentials(info['client_email'], key_data=pk)
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

if st.session_state.auth:
    st.header("👨‍💻 Dashboard de Monitoreo")
    m = folium.Map(location=[-37.28, -72.70], zoom_start=12)
    Draw(export=True).add_to(m)
    st_folium(m, width="100%", height=500)
else:
    st.info("Inicie sesión para acceder.")
