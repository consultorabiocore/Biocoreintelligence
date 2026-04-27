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
        # Mantenemos tu lógica exacta que dio el "verde"
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
        st.subheader("🛠️ Análisis Satelital")
        capa_select = st.radio(
            "Capa:",
            ["Mapa Base", "NDVI (Vegetación)", "NDWI (Agua)"]
        )
        if st.button("Cerrar Sesión"):
            st.session_state.auth = False
            st.rerun()

# --- PANEL PRINCIPAL ---
if st.session_state.auth:
    st.header("👨‍💻 Dashboard de Monitoreo: Laja - Biobío")
    
    # 1. Mapa Base
    m = folium.Map(location=[-37.28, -72.70], zoom_start=12)

    # 2. Procesamiento GEE (Sentinel-2)
    if conectado and capa_select != "Mapa Base":
        try:
            # Obtenemos la imagen más reciente y limpia de 2024
            s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED') \
                .filterBounds(ee.Geometry.Point([-72.70, -37.28])) \
                .filterDate('2024-01-01', '2024-12-31') \
                .sort('CLOUDY_PIXEL_PERCENTAGE') \
                .first()

            if capa_select == "NDVI (Vegetación)":
                img_proc = s2.normalizedDifference(['B8', 'B4'])
                vis = {'min': 0, 'max': 0.8, 'palette': ['red', 'yellow', 'green']}
            else: # NDWI
                img_proc = s2.normalizedDifference(['B3', 'B8'])
                vis = {'min': -0.5, 'max': 0.5, 'palette': ['white', 'blue']}

            map_id = ee.Image(img_proc).getMapId(vis)
            folium.TileLayer(
                tiles=map_id['tile_fetcher'].url_format,
                attr='Google Earth Engine',
                overlay=True,
                opacity=0.7
            ).add_to(m)
        except:
            st.sidebar.warning("Cargando datos satelitales...")

    # 3. Herramienta de Dibujo y Captura de Datos
    draw = Draw(
        export=True,
        position='topleft',
        draw_options={'polyline': False, 'circle': False, 'marker': False, 'circlemarker': False}
    )
    draw.add_to(m)
    
    salida = st_folium(m, width="100%", height=500)

    # 4. Cálculo de Hectáreas en Tiempo Real
    if salida.get('last_active_drawing'):
        coords = salida['last_active_drawing']['geometry']['coordinates'][0]
        area_ee = ee.Geometry.Polygon(coords).area().divide(10000).getInfo()
        
        st.metric("Superficie Analizada", f"{area_ee:.2f} Hectáreas")
        st.write("📌 Área seleccionada lista para análisis de DarwinCheck.")

else:
    st.info("Inicie sesión para acceder a las herramientas de BioCore.")
