import streamlit as st
import ee
import json
import folium
from streamlit_folium import st_folium
from folium.plugins import Draw

# --- CONFIGURACIÓN DE PÁGINA (Debe ser la primera instrucción de Streamlit) ---
st.set_page_config(page_title="BioCore Intelligence SaaS", layout="wide")

# --- INICIALIZACIÓN DE GOOGLE EARTH ENGINE ---
def iniciar_gee():
    if "GEE_JSON" in st.secrets:
        try:
            # 1. Cargamos el JSON desde los Secrets
            creds_info = json.loads(st.secrets["GEE_JSON"])
            
            # 2. Limpiamos la clave privada (reemplazamos los saltos de línea literales)
            # Esto corrige el error 'could not be converted to bytes'
            private_key = creds_info['private_key'].replace('\\n', '\n')
            
            # 3. Creamos las credenciales con los datos separados
            credentials = ee.ServiceAccountCredentials(
                creds_info['client_email'],
                key_data=private_key
            )
            
            # 4. Inicializamos
            ee.Initialize(credentials)
        except Exception as e:
            # Intento de inicialización por defecto si falla la anterior
            try:
                ee.Initialize()
            except:
                st.error(f"❌ Error de conexión con GEE: {e}")
    else:
        st.error("⚠️ Configuración incompleta: GEE_JSON no encontrado en Secrets.")

iniciar_gee()

# --- LÓGICA DE PROCESAMIENTO ---
def procesar_biocore(coords, tipo, glaciar):
    try:
        p = ee.Geometry.Polygon(coords)
        # Imagen Sentinel-2 con corrección atmosférica
        s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED') \
               .filterBounds(p) \
               .sort('CLOUDY_PIXEL_PERCENTAGE') \
               .first()
        
        # Cálculo de índices ambientales
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
    # Doble ruta para el logo (Raíz o carpeta Assets)
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

# --- PANEL DE CONTROL ---
if st.session_state.autenticado:
    st.header("👨‍💻 Análisis de Datos Satelitales")
    
    col1, col2 = st.columns([2, 1])
    
    with col2:
        st.subheader("Parámetros")
        nombre = st.text_input("Nombre del Proyecto")
        tipo = st.selectbox("Ecosistema", ["Humedal", "Bosque", "Zona Minera"])
    
    with col1:
        st.subheader("Área de Interés")
        # Centro del mapa en Chile (Biobío)
        m = folium.Map(location=[-37.28, -72.70], zoom_start=12)
        Draw(export=True).add_to(m)
        mapa = st_folium(m, width=700, height=450)
        
        if st.button("🚀 Ejecutar Análisis"):
            if mapa.get('last_active_drawing'):
                with st.spinner("Calculando índices..."):
                    coords = mapa['last_active_drawing']['geometry']['coordinates'][0]
                    res = procesar_biocore(coords, tipo, False)
                    
                    if "error" in res:
                        st.error(f"Error: {res['error']}")
                    else:
                        st.success("Análisis exitoso")
                        c1, c2, c3 = st.columns(3)
                        c1.metric("Vigor (SAVI)", f"{res.get('savi', 0):.2f}")
                        c2.metric("Agua (NDWI)", f"{res.get('ndwi', 0):.2f}")
                        c3.metric("Nieve (NDSI)", f"{res.get('ndsi', 0):.2f}")
            else:
                st.warning("Por favor, dibuje un área en el mapa.")
else:
    st.info("Inicie sesión para acceder al sistema.")
