import streamlit as st
import ee
import json
import folium
from streamlit_folium import st_folium
from folium.plugins import Draw

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="BioCore Intelligence", layout="wide")

def iniciar_gee():
    if "GEE_JSON" in st.secrets:
        try:
            # 1. Cargamos el JSON de los Secrets
            creds_info = json.loads(st.secrets["GEE_JSON"])
            
            # 2. LIMPIEZA PROFUNDA DE LA LLAVE (Solución definitiva)
            pk = creds_info['private_key']
            
            # Eliminamos caracteres de escape y saltos de línea mal formados
            if isinstance(pk, str):
                pk = pk.replace("\\n", "\n").strip()
            
            # 3. Autenticación
            credentials = ee.ServiceAccountCredentials(
                creds_info['client_email'],
                key_data=pk
            )
            ee.Initialize(credentials)
        except Exception as e:
            st.error(f"❌ Error de conexión con GEE: {e}")
    else:
        st.warning("⚠️ GEE_JSON no configurado en Secrets.")

iniciar_gee()

# --- LÓGICA DE ACCESO ---
if 'auth' not in st.session_state:
    st.session_state.auth = False

with st.sidebar:
    st.markdown("### 🛰️ **BioCore Intelligence**")
    if not st.session_state.auth:
        u = st.text_input("Usuario")
        p = st.text_input("Password", type="password")
        if st.button("Ingresar"):
            if u == "admin" and p == "loreto2026":
                st.session_state.auth = True
                st.rerun()
    else:
        st.success("Conectado")
        if st.button("Cerrar Sesión"):
            st.session_state.auth = False
            st.rerun()

# --- PANEL PRINCIPAL ---
if st.session_state.auth:
    st.header("👨‍💻 Dashboard BioCore")
    m = folium.Map(location=[-37.28, -72.70], zoom_start=12)
    Draw(export=True).add_to(m)
    st_folium(m, width="100%", height=500)
else:
    st.info("Inicie sesión para acceder al sistema.")
