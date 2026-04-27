import streamlit as st
import ee
import json
import folium
from streamlit_folium import st_folium
from folium.plugins import Draw

# --- CONFIGURACIÓN INICIAL ---
st.set_page_config(page_title="BioCore Intelligence", layout="wide")

def iniciar_gee():
    if "GEE_JSON" in st.secrets:
        try:
            # Cargamos el JSON directamente
            info = json.loads(st.secrets["GEE_JSON"])
            
            # Recuperamos la llave asegurando que los saltos de línea sean correctos
            # Esta es la parte que nos dio el 'verde' antes
            pk = info['private_key'].replace('\\n', '\n')
            
            creds = ee.ServiceAccountCredentials(info['client_email'], key_data=pk)
            ee.Initialize(creds)
            return True
        except Exception as e:
            st.error(f"❌ Error: {e}")
            return False
    return False

# Intentar conectar
conectado = iniciar_gee()

# --- INTERFAZ ---
if 'auth' not in st.session_state:
    st.session_state.auth = False

with st.sidebar:
    st.title("🛰️ BioCore")
    
    if conectado:
        st.success("Google Earth Engine: ONLINE")
    
    if not st.session_state.auth:
        u = st.text_input("Usuario")
        p = st.text_input("Password", type="password")
        if st.button("Entrar"):
            if u == "admin" and p == "loreto2026":
                st.session_state.auth = True
                st.rerun()
    else:
        st.success("Sesión activa")
        if st.button("Cerrar Sesión"):
            st.session_state.auth = False
            st.rerun()

# --- PANEL PRINCIPAL ---
if st.session_state.auth:
    st.header("Dashboard de Monitoreo")
    m = folium.Map(location=[-37.28, -72.70], zoom_start=12)
    Draw(export=True).add_to(m)
    st_folium(m, width="100%", height=500)
else:
    st.info("Inicie sesión para acceder.")
