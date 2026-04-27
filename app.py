import streamlit as st
import ee
import json
import folium
from streamlit_folium import st_folium
from folium.plugins import Draw
from datetime import datetime

# --- INICIALIZACIÓN PROFESIONAL CORREGIDA ---
def iniciar_gee():
    try:
        # Streamlit Cloud usa st.secrets para manejar las llaves
        if "GEE_JSON" in st.secrets:
            # Cargamos el secreto como diccionario
            creds_info = json.loads(st.secrets["GEE_JSON"])
            
            # Usamos el diccionario directamente para las credenciales
            # Esto corrige el error de "could not be converted to bytes"
            credentials = ee.ServiceAccountCredentials(
                creds_info['client_email'], 
                key_data=st.secrets["GEE_JSON"]
            )
            
            # Inicialización moderna
            ee.Initialize(credentials)
        else:
            st.error("⚠️ No se encontró la variable GEE_JSON en los Secrets de Streamlit.")
    except Exception as e:
        st.error(f"❌ Error crítico de GEE: {e}")

# Llamamos a la función de inicialización
iniciar_gee()

# --- LÓGICA DE PROCESAMIENTO ---
def procesar_biocore(coords, tipo, glaciar):
    p = ee.Geometry.Polygon(coords)
    
    # Imagen Sentinel-2 más reciente
    s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED').filterBounds(p).sort('system:time_start', False).first()
    
    # Índices ambientales
    idx = s2.expression('((B8-B4)/(B8+B4+0.5))*1.5', {
        'B8': s2.select('B8'), 'B4': s2.select('B4')
    }).rename('sa').addBands(
        s2.normalizedDifference(['B3','B8']).rename('nd') # NDWI
    ).addBands(
        s2.normalizedDifference(['B3','B11']).rename('mn') # NDSI (Hielo)
    ).reduceRegion(ee.Reducer.mean(), p, 30).getInfo()
    
    return idx

# --- INTERFAZ STREAMLIT ---
st.set_page_config(
    page_title="BioCore Intelligence SaaS", 
    page_icon="assets/logo.png", # Corregido: apunta a la carpeta assets
    layout="wide"
)

# Login Simple
if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False

with st.sidebar:
    # --- LOGO CORREGIDO ---
    # Se agrega la ruta 'assets/' porque ahí es donde está el archivo en tu GitHub
    try:
        st.image("assets/logo.png", use_container_width=True) 
    except:
        st.warning("⚠️ No se pudo cargar el logo desde assets/logo.png")
        
    st.title("🛡️ BioCore SaaS")
    user = st.text_input("Usuario")
    passw = st.text_input("Password", type="password")
    
    if st.button("Ingresar"):
        if user == "admin" and passw == "loreto2026":
            st.session_state.autenticado = True
            st.session_state.rol = "admin"
        elif user == "cliente":
            st.session_state.autenticado = True
            st.session_state.rol = "cliente"

# --- PANEL DE CONTROL ---
if st.session_state.autenticado:
    if st.session_state.rol == "admin":
        st.header("👨‍💻 Panel de Administración (Loreto)")
        
        with st.expander("➕ Registrar Nuevo Proyecto Ambiental"):
            nombre = st.text_input("Nombre del Proyecto")
            tipo = st.selectbox("Tipo", ["HUMEDAL", "MINERIA"])
            es_glaciar = st.checkbox("¿Monitoreo de Glaciares?")
            
            m = folium.Map(location=[-37.28, -72.70], zoom_start=10)
            Draw(export=True).add_to(m)
            mapa = st_folium(m, width=700, height=400)
            
            if st.button("Guardar y Analizar"):
                if mapa['last_active_drawing']:
                    coords = mapa['last_active_drawing']['geometry']['coordinates'][0]
                    resultados = procesar_biocore(coords, tipo, es_glaciar)
                    st.success(f"Proyecto {nombre} analizado con éxito.")
                    st.write(resultados)
    else:
        st.header("📊 Dashboard de Cumplimiento Ambiental")
        st.write("Bienvenido a su plataforma de vigilancia.")
        col1, col2 = st.columns(2)
        col1.metric("SAVI (Vigor)", "0.42", "Óptimo")
        col2.metric("NDSI (Nieve)", "0.55", "Estable")
else:
    st.info("Por favor inicie sesión para acceder al sistema BioCore.")
