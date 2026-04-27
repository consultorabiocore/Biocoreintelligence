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
            
            # 2. LIMPIEZA AGRESIVA DE LA CLAVE
            # El error InvalidPadding ocurre por saltos de línea mal interpretados
            # Esta línea asegura que la clave sea un PEM válido para Python
            private_key = creds_info['private_key'].replace('\\n', '\n').strip()
            
            # 3. Autenticación con Service Account
            credentials = ee.ServiceAccountCredentials(
                creds_info['client_email'],
                key_data=private_key
            )
            ee.Initialize(credentials)
        except Exception as e:
            try:
                ee.Initialize() # Intento de respaldo
            except:
                st.error(f"❌ Error de conexión con GEE: {e}")
    else:
        st.error("⚠️ No se encontró GEE_JSON en Secrets.")

iniciar_gee()

# --- INTERFAZ ---
if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False

with st.sidebar:
    try:
        st.image("assets/logo.png", use_container_width=True)
    except:
        st.subheader("🛰️ BioCore Intelligence")

    st.title("🛡️ Acceso")
    if not st.session_state.autenticado:
        u = st.text_input("Usuario")
        p = st.text_input("Password", type="password")
        if st.button("Ingresar"):
            if u == "admin" and p == "loreto2026":
                st.session_state.autenticado = True
                st.rerun()
    else:
        st.success("Conectado")
        if st.button("Salir"):
            st.session_state.autenticado = False
            st.rerun()

# --- PANEL PRINCIPAL ---
if st.session_state.autenticado:
    st.header("👨‍💻 Dashboard BioCore")
    m = folium.Map(location=[-37.28, -72.70], zoom_start=12)
    Draw(export=True).add_to(m)
    st_folium(m, width=700, height=450)
else:
    st.info("Inicie sesión para continuar.")

