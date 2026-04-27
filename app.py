import streamlit as st
import ee
import json
import folium
from streamlit_folium import st_folium
from folium.plugins import Draw

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="BioCore SaaS", layout="wide")

def iniciar_gee():
    try:
        # Mantenemos tu lógica exacta de conexión que ya funcionó
        info = json.loads(st.secrets["GEE_JSON"])
        pk = info["private_key"].replace("\\n", "\n")
        creds = ee.ServiceAccountCredentials(info["client_email"], key_data=pk)
        ee.Initialize(creds)
        return True
    except Exception as e:
        st.error(f"❌ Error GEE: {type(e).__name__}: {e}")
        return False

conectado = iniciar_gee()

# --- BARRA LATERAL ---
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
        st.markdown("---")
        st.subheader("🛠️ Herramientas de Análisis")
        
        # Selector de Capas para la Bióloga
        capa_select = st.radio(
            "Seleccionar Capa Satelital:",
            ["Mapa Base", "NDVI (Vigor Vegetal)", "NDWI (Cuerpos de Agua)"]
        )
        
        st.markdown("---")
        if st.button("Cerrar Sesión"):
            st.session_state.auth = False
            st.rerun()

# --- PANEL PRINCIPAL ---
if st.session_state.auth:
    st.header("👨‍💻 Dashboard de Monitoreo: Biobío")
    
    # 1. Crear el mapa base
    m = folium.Map(location=[-37.28, -72.70], zoom_start=12)

    # 2. Lógica de procesamiento de imágenes GEE
    if conectado and capa_select != "Mapa Base":
        try:
            # Filtramos Sentinel-2 por la zona de Laja y nubes bajas
            s2_col = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED') \
                .filterBounds(ee.Geometry.Point([-72.70, -37.28])) \
                .filterDate('2024-01-01', '2024-12-31') \
                .sort('CLOUDY_PIXEL_PERCENTAGE') \
                .first()

            if capa_select == "NDVI (Vigor Vegetal)":
                # Cálculo de NDVI: (NIR - RED) / (NIR + RED)
                img_proc = s2_col.normalizedDifference(['B8', 'B4'])
                vis_params = {'min': 0, 'max': 0.8, 'palette': ['red', 'yellow', 'green']}
            
            elif capa_select == "NDWI (Cuerpos de Agua)":
                # Cálculo de NDWI: (GREEN - NIR) / (GREEN + NIR)
                img_proc = s2_col.normalizedDifference(['B3', 'B8'])
                vis_params = {'min': -0.5, 'max': 0.5, 'palette': ['white', 'blue']}

            # Obtener la URL de las teselas de Google
            map_id_dict = ee.Image(img_proc).getMapId(vis_params)
            folium.TileLayer(
                tiles=map_id_dict['tile_fetcher'].url_format,
                attr='Google Earth Engine',
                name=capa_select,
                overlay=True,
                control=True,
                opacity=0.7
            ).add_to(m)
            
        except Exception as e:
            st.sidebar.error(f"Error procesando capa: {e}")

    # 3. Mostrar Mapa
    Draw(export=True).add_to(m)
    st_folium(m, width="100%", height=600)
    
    # Pie de página técnico
    if capa_select == "NDVI (Vigor Vegetal)":
        st.caption("🟢 **NDVI:** Los tonos verdes intensos indican vegetación densa y saludable (bosques nativos/plantaciones).")
    elif capa_select == "NDWI (Cuerpos de Agua)":
        st.caption("🔵 **NDWI:** Los tonos azules resaltan la presencia de agua, útil para monitorear el cauce del Río Laja.")

else:
    st.info("Inicie sesión para acceder a las herramientas de BioCore.")
