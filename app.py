import streamlit as st
import ee
import json
import folium
from streamlit_folium import st_folium
import os
import base64

# --- CONFIGURACIÓN BIOCORE ---
LOGO_PATH = os.path.join("assets", "logo_biocore.png")

def inicializar_gee():
    try:
        if 'gee_auth' not in st.session_state:
            info = json.loads(st.secrets["GEE_JSON"])
            creds = ee.ServiceAccountCredentials(info['client_email'], key_data=info['private_key'].replace("\\n", "\n"))
            ee.Initialize(creds)
            st.session_state.gee_auth = True
        return True
    except: return False

# --- INTERFAZ ---
if 'auth' not in st.session_state: st.session_state.auth = False

with st.sidebar:
    if os.path.exists(LOGO_PATH):
        with open(LOGO_PATH, "rb") as f:
            st.markdown(f'<div style="text-align:center"><img src="data:image/png;base64,{base64.b64encode(f.read()).decode()}" width="120"></div>', unsafe_allow_html=True)
    
    st.markdown("---")
    if st.session_state.auth:
        st.subheader("Configuración")
        proy_name = st.text_input("Proyecto:", "Pascua Lama")
        tipo_auditoria = st.selectbox("Sector:", ["Minería", "Glaciares", "Humedales", "Forestal"])
        if st.button("Cerrar Sesión"): 
            st.session_state.auth = False
            st.rerun()
    else:
        u, p = st.text_input("Usuario"), st.text_input("Clave", type="password")
        if st.button("Entrar"):
            if u == "admin" and p == "loreto2026": 
                st.session_state.auth = True
                st.rerun()

# --- CUERPO PRINCIPAL ---
if st.session_state.auth and inicializar_gee():
    st.title(f"Auditoría: {proy_name}")
    
    col1, col2 = st.columns([1, 1.2])

    with col1:
        st.markdown("**1. Polígono de Monitoreo**")
        
        # TEXT AREA CON EL FORMATO DE FONDO (PLACEHOLDER)
        ejemplo_json = "[[-70.033, -29.316], [-70.016, -29.316], [-70.016, -29.333], [-70.033, -29.333], [-70.033, -29.316]]"
        
        raw_coords = st.text_area(
            "Ingrese coordenadas en formato JSON:",
            height=200,
            placeholder=f"Ejemplo:\n{ejemplo_json}",
            help="Asegúrese de cerrar el polígono repitiendo el primer punto al final."
        )
        
        geom = None
        if raw_coords:
            try:
                puntos = json.loads(raw_coords)
                geom = ee.Geometry.Polygon(puntos)
                st.success("✅ Estructura válida.")
            except Exception as e:
                st.error("❌ Error de formato. Verifique los corchetes y comas.")

    with col2:
        st.markdown("**2. Visualización Satelital**")
        if geom:
            centro = geom.centroid().coordinates().getInfo()[::-1]
            m = folium.Map(location=centro, zoom_start=13)
            folium.TileLayer(
                tiles='https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}',
                attr='Google',
                name='Google Satellite'
            ).add_to(m)
            folium.GeoJson(data=geom.getInfo(), style_function=lambda x: {'color': 'red', 'fillOpacity': 0.2}).add_to(m)
            st_folium(m, width="100%", height=400)
        else:
            # Mapa base si no hay datos
            m_base = folium.Map(location=[-33.45, -70.66], zoom_start=4)
            st_folium(m_base, width="100%", height=400)

    if geom:
        if st.button("🚀 GENERAR REPORTE DIARIO"):
            # Aquí se ejecuta la lógica técnica y el envío a Telegram
            st.info("Procesando índices multiespectrales...")
