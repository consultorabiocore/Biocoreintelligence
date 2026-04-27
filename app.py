import streamlit as st
import ee
import json
import folium
from streamlit_folium import st_folium
from folium.plugins import Draw

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="BioCore Intelligence", layout="wide")

def iniciar_gee():
    if "GEE_JSON" in st.secrets:
        try:
            info = json.loads(st.secrets["GEE_JSON"])
            # LIMPIEZA PROFUNDA: Reemplaza saltos de línea y quita espacios extra
            pk = info['private_key'].replace('\\n', '\n').strip()
            
            # Autenticación
            creds = ee.ServiceAccountCredentials(info['client_email'], key_data=pk)
            ee.Initialize(creds)
            return True
        except Exception as e:
            st.error(f"❌ Error de conexión: {e}")
            return False
    return False

# Intentar conexión
conectado = iniciar_gee()

# --- INTERFAZ ---
if 'auth' not in st.session_state:
    st.session_state.auth = False

with st.sidebar:
    st.markdown("### 🛰️ **BioCore Intelligence**")
    if conectado:
        st.success("Conexión Establecida ✅")
    else:
        st.error("Esperando GEE... ❌")

    if not st.session_state.auth:
        u = st.text_input("Usuario")
        p = st.text_input("Password", type="password")
        if st.button("Ingresar"):
            if u == "admin" and p == "loreto2026":
                st.session_state.auth = True
                st.rerun()
    else:
        st.success("Sesión Iniciada")
        if st.button("Cerrar Sesión"):
            st.session_state.auth = False
            st.rerun()

# --- DASHBOARD ---
if st.session_state.auth:
    st.header("👨‍💻 Dashboard de Monitoreo")
    m = folium.Map(location=[-37.28, -72.70], zoom_start=12)
    Draw(export=True).add_to(m)
    st_folium(m, width="100%", height=500)
else:
    st.info("Inicie sesión para acceder al sistema.")
