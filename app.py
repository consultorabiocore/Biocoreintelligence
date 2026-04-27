import streamlit as st
import ee
import json
import re
import folium
from streamlit_folium import st_folium
import os
import base64

# --- CONFIGURACIÓN ---
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

# --- PROCESADOR DE COORDENADAS (ADIÓS CORCHETES MANUALES) ---
def parsear_coordenadas(texto):
    """
    Busca números en el texto y los agrupa de a pares (lat, lon).
    Ya no importa si traen letras, comas o corchetes.
    """
    numeros = re.findall(r"[-+]?\d*\.\d+|\d+", texto)
    if not numeros: return None
    
    # Convertir a flotantes y agrupar en pares
    puntos = [float(n) for n in numeros]
    coords = []
    for i in range(0, len(puntos), 2):
        if i + 1 < len(puntos):
            # GEE usa [lon, lat]
            coords.append([puntos[i+1], puntos[i]]) 
    
    # Cerrar el polígono si es necesario
    if coords and coords[0] != coords[-1]:
        coords.append(coords[0])
    return coords

# --- INTERFAZ ---
if 'auth' not in st.session_state: st.session_state.auth = False

with st.sidebar:
    if os.path.exists(LOGO_PATH):
        with open(LOGO_PATH, "rb") as f:
            st.markdown(f'<div style="text-align:center"><img src="data:image/png;base64,{base64.b64encode(f.read()).decode()}" width="120"></div>', unsafe_allow_html=True)
    
    if st.session_state.auth:
        st.success("Loreto Campos | Directora")
        proy_name = st.text_input("Proyecto:", "Pascua Lama")
        tipo_auditoria = st.selectbox("Sector de Auditoría:", ["Minería", "Glaciares", "Humedales", "Forestal"])
        if st.button("Salir"): st.session_state.auth = False; st.rerun()
    else:
        u, p = st.text_input("Usuario"), st.text_input("Clave", type="password")
        if st.button("Entrar"):
            if u == "admin" and p == "loreto2026": st.session_state.auth = True; st.rerun()

# --- CUERPO PRINCIPAL ---
if st.session_state.auth and inicializar_gee():
    st.subheader(f"Dashboard de Vigilancia: {proy_name}")
    
    col1, col2 = st.columns([1, 1.5])

    with col1:
        st.markdown("**1. Entrada de Coordenadas**")
        raw_input = st.text_area("Pegue las coordenadas aquí (texto, excel, etc.):", height=150)
        
        lista_coords = parsear_coordenadas(raw_input) if raw_input else None
        
        if lista_coords:
            try:
                geom = ee.Geometry.Polygon(lista_coords)
                st.success(f"✅ {len(lista_coords)-1} vértices detectados.")
            except:
                st.error("Error en la geometría.")
                geom = None
        else:
            geom = None
            st.info("Pegue datos para visualizar el área.")

    with col2:
        st.markdown("**2. Localización Satelital**")
        if geom:
            centro = geom.centroid().coordinates().getInfo()[::-1]
            m = folium.Map(location=centro, zoom_start=14)
            folium.TileLayer('https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}', attr='Google', name='Google Satellite').add_to(m)
            folium.GeoJson(data=geom.getInfo(), style_function=lambda x: {'color': 'orange'}).add_to(m)
            st_folium(m, width="100%", height=350)
        else:
            # Mapa por defecto en Chile si no hay coordenadas
            m_def = folium.Map(location=[-37.27, -72.70], zoom_start=5)
            st_folium(m_def, width="100%", height=350)

    if geom:
        if st.button("🚀 GENERAR REPORTE DIARIO"):
            st.write("Generando análisis multiespectral...")
            # Aquí se dispara el Telegram y el PDF
