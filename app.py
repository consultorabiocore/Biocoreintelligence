import streamlit as st
import ee
import json
import folium
from streamlit_folium import st_folium
from folium.plugins import Draw

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="BioCore Intelligence SaaS", layout="wide")

# --- INICIALIZACIÓN DE GOOGLE EARTH ENGINE ---
def iniciar_gee():
    if "GEE_JSON" in st.secrets:
        try:
            # 1. Cargamos el JSON desde los Secrets
            creds_info = json.loads(st.secrets["GEE_JSON"])
            
            # 2. REPARACIÓN AUTOMÁTICA DE LA LLAVE
            # Esto limpia los saltos de línea y espacios que causan "InvalidPadding"
            pk = creds_info['private_key']
            if isinstance(pk, str):
                pk = pk.replace("\\n", "\n").strip()
            
            # 3. Inicialización con Service Account
            credentials = ee.ServiceAccountCredentials(
                creds_info['client_email'],
                key_data=pk
            )
            ee.Initialize(credentials)
        except Exception as e:
            st.error(f"❌ Error de conexión con GEE: {e}")
    else:
        st.error("⚠️ No se encontró la configuración GEE_JSON en Secrets.")

iniciar_gee()

# --- INTERFAZ ---
if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False

with st.sidebar:
    # Ruta flexible para el logo
    try:
        st.image("assets/logo.png", use_container_width=True)
    except:
        st.markdown("### 🛰️ **BioCore Intelligence**")

    st.title("🛡️ Panel de Acceso")
    
    if not st.session_state.autenticado:
        user = st.text_input("Usuario")
        passw = st.text_input("Password", type="password")
        if st.button("Ingresar"):
            if user == "admin" and passw == "loreto2026":
                st.session_state.autenticado = True
                st.rerun()
            else:
                st.error("Credenciales incorrectas")
    else:
        st.success("Sesión Iniciada")
        if st.button("Cerrar Sesión"):
            st.session_state.autenticado = False
            st.rerun()

# --- PANEL PRINCIPAL ---
if st.session_state.autenticado:
    st.header("👨‍💻 Análisis Satelital BioCore")
    
    m = folium.Map(location=[-37.28, -72.70], zoom_start=12)
    Draw(export=True).add_to(m)
    st_folium(m, width=700, height=450)
    st.info("Dibuja un polígono para comenzar el análisis.")
else:
    st.info("Por favor, inicie sesión para acceder al sistema.")
