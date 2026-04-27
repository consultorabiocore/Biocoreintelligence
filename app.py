import streamlit as st
import ee
import json
import folium
from streamlit_folium import st_folium
from folium.plugins import Draw

# --- CONFIGURACIÓN DE PÁGINA (Debe ser lo primero) ---
st.set_page_config(page_title="BioCore Intelligence SaaS", layout="wide")

# --- INICIALIZACIÓN DE GOOGLE EARTH ENGINE ---
def iniciar_gee():
    try:
        # Buscamos la llave en los Secrets de Streamlit
        if "GEE_JSON" in st.secrets:
            # Cargamos el JSON directamente desde el secreto
            json_text = st.secrets["GEE_JSON"]
            creds_info = json.loads(json_text)
            
            # Inicialización profesional con Service Account
            credentials = ee.ServiceAccountCredentials(
                creds_info['client_email'], 
                key_data=json_text
            )
            ee.Initialize(credentials)
        else:
            st.error("⚠️ Configuración incompleta: GEE_JSON no encontrado en Secrets.")
    except Exception as e:
        # Si ya está inicializado, no mostramos error
        try:
            ee.Initialize()
        except:
            st.error(f"❌ Error de conexión con GEE: {e}")

iniciar_gee()

# --- LÓGICA DE PROCESAMIENTO SATELITAL ---
def procesar_biocore(coords, tipo, glaciar):
    try:
        p = ee.Geometry.Polygon(coords)
        # Imagen Sentinel-2 más reciente con menos nubes
        s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED') \
               .filterBounds(p) \
               .sort('CLOUDY_PIXEL_PERCENTAGE') \
               .first()
        
        # Cálculo de índices (SAVI, NDWI, NDSI)
        idx = s2.expression('((B8-B4)/(B8+B4+0.5))*1.5', {
            'B8': s2.select('B8'), 'B4': s2.select('B4')
        }).rename('savi').addBands(
            s2.normalizedDifference(['B3','B8']).rename('ndwi')
        ).addBands(
            s2.normalizedDifference(['B3','B11']).rename('ndsi')
        ).reduceRegion(ee.Reducer.mean(), p, 30).getInfo()
        
        return idx
    except Exception as e:
        return {"error": str(e)}

# --- INTERFAZ DE USUARIO (SIDEBAR) ---
if 'autenticado' not in st.session_state:
    st.session_state.autenticado = False

with st.sidebar:
    # Intento de carga de logo (Doble ruta para evitar errores)
    try:
        st.image("assets/logo.png", use_container_width=True)
    except:
        try:
            st.image("logo.png", use_container_width=True)
        except:
            st.info("📌 BioCore Intelligence")

    st.title("🛡️ BioCore SaaS")
    
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
        st.success(f"Sesión activa: Admin")
        if st.button("Cerrar Sesión"):
            st.session_state.autenticado = False
            st.rerun()

# --- PANEL PRINCIPAL ---
if st.session_state.autenticado:
    st.header("👨‍💻 Panel de Monitoreo Ambiental")
    
    tab1, tab2 = st.tabs(["Nuevo Análisis", "Historial"])
    
    with tab1:
        col1, col2 = st.columns([2, 1])
        
        with col2:
            nombre = st.text_input("Nombre del Proyecto", placeholder="Ej: Humedal Laja")
            tipo = st.selectbox("Categoría", ["HUMEDAL", "MINERÍA", "FORESTAL"])
            es_glaciar = st.checkbox("Monitoreo de Hielo/Nieve")
        
        with col1:
            st.subheader("Seleccione área en el mapa")
            m = folium.Map(location=[-37.28, -72.70], zoom_start=12)
            Draw(export=True).add_to(m)
            mapa = st_folium(m, width=700, height=450)
            
            if st.button("🚀 Ejecutar Análisis Satelital"):
                if mapa.get('last_active_drawing'):
                    with st.spinner("Procesando imágenes Sentinel-2..."):
                        coords = mapa['last_active_drawing']['geometry']['coordinates'][0]
                        res = procesar_biocore(coords, tipo, es_glaciar)
                        
                        if "error" in res:
                            st.error(f"Error en proceso: {res['error']}")
                        else:
                            st.balloons()
                            st.success("Análisis completado")
                            c1, c2, c3 = st.columns(3)
                            c1.metric("Vigor Vegetal (SAVI)", f"{res.get('savi', 0):.2f}")
                            c2.metric("Humedad (NDWI)", f"{res.get('ndwi', 0):.2f}")
                            c3.metric("Nieve/Hielo (NDSI)", f"{res.get('ndsi', 0):.2f}")
                else:
                    st.warning("Dibuje un polígono en el mapa primero.")
else:
    st.info("Por favor, inicie sesión en el panel lateral para acceder a las herramientas de BioCore.")
