import streamlit as st
import ee
import json
import folium
from streamlit_folium import st_folium
from folium.plugins import Draw
import re

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="BioCore Intelligence", layout="wide")

def iniciar_gee():
    if "GEE_JSON" in st.secrets:
        try:
            # 1. Cargamos el JSON
            info = json.loads(st.secrets["GEE_JSON"])
            pk = info['private_key']
            
            # 2. LIMPIEZA QUIRÚRGICA (Solución definitiva a InvalidPadding)
            if isinstance(pk, str):
                # Convertimos saltos de línea de texto a reales
                pk = pk.replace("\\n", "\n")
                # Removemos cualquier cosa que no sea parte de una llave PEM válida
                # Esto quita espacios, puntos o barras que se cuelan al pegar
                pk = re.sub(r'^[^{A-Za-z0-9\-]*', '', pk).strip()
            
            # 3. Autenticación
            creds = ee.ServiceAccountCredentials(info['client_email'], key_data=pk)
            ee.Initialize(creds)
        except Exception as e:
            st.error(f"❌ Error de conexión con GEE: {e}")
    else:
        st.warning("⚠️ Esperando configuración de GEE_JSON en Secrets...")

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
                st.error("Credenciales incorrectas")
    else:
        st.success("Sesión Iniciada")
        if st.button("Cerrar Sesión"):
            st.session_state.auth = False
            st.rerun()

# --- PANEL PRINCIPAL ---
if st.session_state.auth:
    st.header("👨‍💻 Dashboard de Monitoreo")
    m = folium.Map(location=[-37.28, -72.70], zoom_start=12)
    Draw(export=True).add_to(m)
    st_folium(m, width="100%", height=500)
else:
    st.info("Inicie sesión para acceder al sistema.")
