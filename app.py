import streamlit as st
import ee
import json
import folium
from streamlit_folium import st_folium
from folium.plugins import Draw

st.set_page_config(page_title="BioCore SaaS", layout="wide")

def iniciar_gee():
    try:
        info = json.loads(st.secrets["GEE_JSON"])
        pk = info["private_key"].replace("\\n", "\n")
        creds = ee.ServiceAccountCredentials(info["client_email"], key_data=pk)
        ee.Initialize(creds)
        return True
    except Exception as e:
        st.error(f"❌ Error GEE: {type(e).__name__}: {e}")
        return False

conectado = iniciar_gee()

with st.sidebar:
    st.subheader("🛰️ BioCore Intelligence")
    if conectado:
        st.success("Conexión GEE ✅")

    if 'auth' not in st.session_state:
        st.session_state.auth = False

    if not st.session_state.auth:
        u = st.text_input("Usuario")
        p = st.text_input("Password", type="password")
        if st.button("Entrar"):
            if u == "admin" and p == "loreto2026":
                st.session_state.auth = True
                st.rerun()
    else:
        st.info("Sesión activa")
        if st.button("Cerrar Sesión"):
            st.session_state.auth = False
            st.rerun()

if st.session_state.auth:
    st.header("👨‍💻 Dashboard de Monitoreo")
    m = folium.Map(location=[-37.28, -72.70], zoom_start=12)
    Draw(export=True).add_to(m)
    st_folium(m, width="100%", height=500)
else:
    st.info("Inicie sesión para acceder a las herramientas de BioCore.")
