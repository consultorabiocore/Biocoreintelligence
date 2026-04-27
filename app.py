import streamlit as st
import ee
import json
import folium
from streamlit_folium import st_folium
from folium.plugins import Draw

st.set_page_config(page_title="BioCore SaaS", layout="wide")

def iniciar_gee():
    if "GEE_JSON" in st.secrets:
        try:
            info = json.loads(st.secrets["GEE_JSON"])
            # Limpieza vital para evitar el InvalidPadding
            llave = info['private_key'].replace('\\n', '\n').strip()
            
            creds = ee.ServiceAccountCredentials(info['client_email'], key_data=llave)
            ee.Initialize(creds)
            return True
        except Exception as e:
            st.error(f"❌ Error de conexión: {e}")
            return False
    return False

# Ejecutar conexión y mostrar estado
gee_conectado = iniciar_gee()

with st.sidebar:
    st.title("🛰️ BioCore")
    if gee_conectado:
        st.success("GEE: ONLINE ✅")
    else:
        st.error("GEE: OFFLINE ❌")

# --- LÓGICA DE LOGIN ---
if 'auth' not in st.session_state:
    st.session_state.auth = False

if not st.session_state.auth:
    st.info("Inicie sesión para acceder.")
    u = st.sidebar.text_input("Usuario")
    p = st.sidebar.text_input("Password", type="password")
    if st.sidebar.button("Entrar"):
        if u == "admin" and p == "loreto2026":
            st.session_state.auth = True
            st.rerun()
else:
    st.header("Dashboard BioCore")
    m = folium.Map(location=[-37.28, -72.70], zoom_start=12)
    Draw(export=True).add_to(m)
    st_folium(m, width="100%", height=500)
