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
            info = json.loads(st.secrets["GEE_JSON"])
            # Recuperamos y limpiamos profundamente la llave
            llave = info['private_key'].replace('\\n', '\n').strip()
            
            # Si por algún motivo la llave se pegó con saltos literales extra
            if "-----BEGIN PRIVATE KEY-----" in llave:
                 creds = ee.ServiceAccountCredentials(info['client_email'], key_data=llave)
                 ee.Initialize(creds)
                 return True
        except Exception as e:
            st.error(f"❌ Error de conexión: {e}")
            return False
    return False

# Ejecutar conexión
gee_online = iniciar_gee()

# --- INTERFAZ ---
if 'auth' not in st.session_state:
    st.session_state.auth = False

with st.sidebar:
    st.markdown("### 🛰️ **BioCore Intelligence**")
    
    if gee_online:
        st.success("GEE Conectado ✅")

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
        m = folium.Map(location=[-37.28, -72.70], zoom_start=12)
        Draw(export=True).add_to(m)
        st_folium(m, width="100%", height=500)
    
    with col2:
        st.write("### Controles")
        st.info("Dibuja un polígono para analizar los índices.")
else:
    st.info("Inicie sesión para acceder a las herramientas de BioCore.")
