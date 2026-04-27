import streamlit as st
import ee
import json
import folium
from streamlit_folium import st_folium
from folium.plugins import Draw
import re

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="BioCore SaaS", layout="wide")

def iniciar_gee():
    if "GEE_JSON" in st.secrets:
        try:
            # 1. Cargamos el JSON
            info = json.loads(st.secrets["GEE_JSON"])
            pk = info['private_key']
            
            # 2. LIMPIEZA QUIRÚRGICA (Elimina puntos, barras y basura al inicio/final)
            # Solo permitimos caracteres que pertenecen a un PEM real
            if isinstance(pk, str):
                # Quitamos cualquier cosa que no sea parte de la estructura PEM
                pk = pk.replace("\\n", "\n")
                pk = re.sub(r'^[^{A-Za-z0-9\-]*', '', pk) # Limpia el inicio
                pk = pk.strip()
            
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
    st.markdown("### 🛰️ **BioCore Intelligence**")
    if not st.session_state.auth:
        u = st.text_input("Usuario")
        p = st.text_input("Password", type="password")
        if st.button("Ingresar"):
            if u == "admin" and p == "loreto2026":
                st.session_state.auth = True
                st.rerun()
            else:
                st.error("Credenciales incorrectas")
    else:
        st.success("Sesión Iniciada")
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
