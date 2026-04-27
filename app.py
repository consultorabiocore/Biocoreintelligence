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
            # 1. Cargamos el JSON
            creds_info = json.loads(st.secrets["GEE_JSON"])
            
            # 2. LIMPIEZA PROFUNDA DE LA CLAVE (Solución al error InvalidPadding)
            # Esto quita espacios raros y asegura que los saltos de línea sean correctos
            private_key = creds_info['private_key']
            if isinstance(private_key, str):
                private_key = private_key.replace("\\n", "\n")
            
            # 3. Inicialización
            credentials = ee.ServiceAccountCredentials(
                creds_info['client_email'],
                key_data=private_key
            )
            ee.Initialize(credentials)
        except Exception as e:
            try:
                ee.Initialize()
            except:
                st.error(f"❌ Error de conexión con GEE: {e}")
    else:
        st.error("⚠️ GEE_JSON no encontrado en Secrets.")

iniciar_gee()

# --- INTERFAZ DE USUARIO (SIDEBAR) ---
if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False

with st.sidebar:
    try:
        st.image("assets/logo.png", use_container_width=True)
    except:
        try:
            st.image("logo.png", use_container_width=True)
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
    
    # Lógica del mapa y procesamiento
    m = folium.Map(location=[-37.28, -72.70], zoom_start=12)
    Draw(export=True).add_to(m)
    st_folium(m, width=700, height=450)
    st.info("Dibuja un área y presiona analizar (lógica simplificada para probar conexión)")
else:
    st.info("Inicie sesión para acceder al sistema.")
