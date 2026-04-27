import streamlit as st
import ee
import json
import folium
import os
import base64
import re
from streamlit_folium import st_folium

# --- CONFIGURACIÓN BIOCORE ---
st.set_page_config(page_title="BioCore Intelligence", layout="wide")
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

# --- PROCESADOR INTELIGENTE (SIN CORCHETES) ---
def procesar_coordenadas_simples(texto):
    """Convierte texto de Lat, Lon a formato GEE [Lon, Lat]"""
    lineas = texto.strip().split('\n')
    coords_finales = []
    for linea in lineas:
        # Busca números (incluyendo negativos y decimales)
        numeros = re.findall(r"[-+]?\d*\.\d+|\d+", linea)
        if len(numeros) >= 2:
            lat = float(numeros[0])
            lon = float(numeros[1])
            # Google Earth Engine usa [Longitud, Latitud]
            coords_finales.append([lon, lat])
    
    # Cerrar el polígono automáticamente si el último no es igual al primero
    if coords_finales and coords_finales[0] != coords_finales[-1]:
        coords_finales.append(coords_finales[0])
    return coords_finales

# --- PESTAÑA LATERAL ---
with st.sidebar:
    if os.path.exists(LOGO_PATH):
        with open(LOGO_PATH, "rb") as f:
            data = base64.b64encode(f.read()).decode()
            st.markdown(f'<div style="text-align:center"><img src="data:image/png;base64,{data}" width="160"></div>', unsafe_allow_html=True)
    
    st.markdown("---")
    if not st.session_state.get('auth', False):
        u, p = st.text_input("Usuario"), st.text_input("Clave", type="password")
        if st.button("Ingresar"):
            if u == "admin" and p == "loreto2026":
                st.session_state.auth = True
                st.rerun()
    else:
        st.subheader("📂 Proyecto")
        nombre_cliente = st.text_input("Cliente:", value="")
        tipo_sector = st.selectbox("Análisis:", ["Minería", "Glaciares", "Humedales", "Forestal"])
        if st.button("Cerrar Sesión"):
            st.session_state.auth = False
            st.rerun()

# --- PANEL PRINCIPAL ---
if st.session_state.get('auth', False) and inicializar_gee():
    st.title("🛰 Consola de Visualización")

    col_map, col_ctrl = st.columns([2, 1])

    with col_ctrl:
        st.markdown("### 📍 Coordenadas")
        
        # EL EJEMPLO EN EL FONDO COMO PEDISTE
        ejemplo = "-29.3177, -70.0191\n-29.3300, -70.0100\n-29.3400, -70.0300"
        
        raw_input = st.text_area(
            "Pegue la lista de coordenadas aquí:", 
            height=300,
            placeholder=f"Ejemplo:\n{ejemplo}"
        )
        
        geom = None
        if raw_input:
            puntos = procesar_coordenadas_simples(raw_input)
            if len(puntos) >= 3:
                try:
                    geom = ee.Geometry.Polygon(puntos)
                    st.success(f"✅ {len(puntos)-1} puntos detectados.")
                except: st.error("Error al generar el polígono.")
            else:
                st.warning("Ingrese al menos 3 puntos.")

    with col_map:
        if geom:
            centro = geom.centroid().coordinates().getInfo()[::-1]
            m = folium.Map(location=centro, zoom_start=14)
        else:
            m = folium.Map(location=[-37.0, -72.0], zoom_start=5)
        
        folium.TileLayer('https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}', attr='Google', name='Satélite').add_to(m)

        if geom:
            folium.GeoJson(data=geom.getInfo(), style_function=lambda x: {'color': '#39FF14', 'weight': 2}).add_to(m)

        st_folium(m, width="100%", height=450)

    if geom and nombre_cliente:
        if st.button(f"🚀 GENERAR REPORTE PARA {nombre_cliente.upper()}"):
            st.info("Procesando datos... Revisar Telegram.")
