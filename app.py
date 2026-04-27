import streamlit as st
import ee
import json
import folium
import pandas as pd
import io
from streamlit_folium import st_folium
from folium.plugins import Draw

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="BioCore Intelligence", layout="wide")

def iniciar_gee():
    try:
        info = json.loads(st.secrets["GEE_JSON"])
        pk = info["private_key"].replace("\\n", "\n")
        creds = ee.ServiceAccountCredentials(info["client_email"], key_data=pk)
        ee.Initialize(creds)
        return True
    except:
        return False

conectado = iniciar_gee()

# --- BARRA LATERAL ---
with st.sidebar:
    st.subheader("🛰️ BioCore Intelligence")
    
    if not st.session_state.get('auth', False):
        u = st.text_input("Usuario")
        p = st.text_input("Password", type="password")
        if st.button("Entrar"):
            if u == "admin" and p == "loreto2026":
                st.session_state.auth = True
                st.rerun()
    else:
        st.success("Conexión GEE ✅")
        st.markdown("---")
        
        # 1. SEGMENTACIÓN POR TIPO DE PROYECTO
        st.subheader("📁 Definición del Proyecto")
        nombre_cliente = st.text_input("Nombre del Cliente/Proyecto", "Proyecto_Alpha")
        
        tipo_proyecto = st.selectbox(
            "Categoría de Evaluación:",
            ["Energía (Eólico/Solar)", "Inmobiliario/Urbano", "Agrícola/Forestal", "Minería/Industrial"]
        )

        # 2. CARGA DE COORDENADAS CON PLACEHOLDER
        st.subheader("📍 Puntos de Muestreo")
        ejemplo = "-37.2812, -72.7034\n-37.2845, -72.7056"
        input_coords = st.text_area("Pegar lat, lon:", placeholder=ejemplo, height=100)
        
        # 3. VARIABLES DINÁMICAS SEGÚN PROYECTO
        st.markdown("---")
        st.subheader("🔍 Variables de Análisis")
        
        if tipo_proyecto == "Energía (Eólico/Solar)":
            opciones_var = ["Mapa Base", "NDVI (Vigor Vegetal)", "NDSI (Suelo Desnudo)"]
        elif tipo_proyecto == "Inmobiliario/Urbano":
            opciones_var = ["Mapa Base", "NDWI (Humedad/Agua)", "NDVI (Áreas Verdes)"]
        elif tipo_proyecto == "Agrícola/Forestal":
            opciones_var = ["Mapa Base", "NDVI (Salud Cultivos)", "EVI (Estructura de Dosel)"]
        else:
            opciones_var = ["Mapa Base", "NDVI", "NDWI", "NDSI"]

        capa_select = st.radio("Capa Satelital Activa:", opciones_var)
        
        if st.button("Cerrar Sesión"):
            st.session_state.auth = False
            st.rerun()

# --- PANEL PRINCIPAL ---
if st.session_state.get('auth', False):
    st.header(f"Dashboard: {nombre_cliente} | {tipo_proyecto}")
    
    # Procesamiento de Coordenadas
    df_puntos = None
    lat_c, lon_c = -37.28, -72.70
    if input_coords:
        try:
            data = io.StringIO(input_coords.strip())
            df_puntos = pd.read_csv(data, names=['lat', 'lon'], skipinitialspace=True)
            if not df_puntos.empty:
                lat_c, lon_c = df_puntos['lat'].iloc[0], df_puntos['lon'].iloc[0]
        except:
            st.sidebar.error("⚠️ Error de formato en coordenadas.")

    col1, col2 = st.columns([3, 1])
    
    with col1:
        m = folium.Map(location=[lat_c, lon_c], zoom_start=13)
        
        if df_puntos is not None:
            for i, row in df_puntos.iterrows():
                folium.Marker([row['lat'], row['lon']], popup=f"Punto {i+1}", icon=folium.Icon(color='red')).add_to(m)

        # Lógica de Variables de Earth Engine
        if conectado and capa_select != "Mapa Base":
            s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED') \
                .filterBounds(ee.Geometry.Point([lon_c, lat_c])) \
                .filterDate('2024-01-01', '2024-12-31') \
                .sort('CLOUDY_PIXEL_PERCENTAGE').first()
            
            # Definición de Variables (Fórmulas)
            if "NDVI" in capa_select:
                img = s2.normalizedDifference(['B8', 'B4']) # NIR, RED
                vis = {'min': 0, 'max': 0.8, 'palette': ['#e5f5f9','#99d8c9','#2ca25f']}
            elif "NDWI" in capa_select:
                img = s2.normalizedDifference(['B3', 'B8']) # GREEN, NIR
                vis = {'min': -0.5, 'max': 0.5, 'palette': ['#f7fbff','#6baed6','#08306b']}
            elif "NDSI" in capa_select or "Suelo" in capa_select:
                img = s2.normalizedDifference(['B3', 'B11']) # GREEN, SWIR
                vis = {'min': -1, 'max': 1, 'palette': ['#fec44f','#d95f0e','#993404']}
            elif "EVI" in capa_select:
                # EVI (Enhanced Vegetation Index)
                evi = s2.expression(
                    '2.5 * ((NIR - RED) / (NIR + 6 * RED - 7.5 * BLUE + 1))',
                    {'NIR': s2.select('B8'), 'RED': s2.select('B4'), 'BLUE': s2.select('B2')}
                )
                img = evi
                vis = {'min': 0, 'max': 1, 'palette': ['white', 'green']}

            map_id = ee.Image(img).getMapId(vis)
            folium.TileLayer(tiles=map_id['tile_fetcher'].url_format, attr='GEE', overlay=True, name=capa_select).add_to(m)

        Draw(export=True).add_to(m)
        salida = st_folium(m, width="100%", height=550)

    with col2:
        st.subheader("📋 Reporte Técnico")
        if df_puntos is not None:
            st.metric("Puntos Cargados", len(df_puntos))
            with st.expander("Ver Coordenadas"):
                st.dataframe(df_puntos, use_container_width=True)
        
        if salida.get('last_active_drawing'):
            coords = salida['last_active_drawing']['geometry']['coordinates'][0]
            area = ee.Geometry.Polygon(coords).area().divide(10000).getInfo()
            st.metric("Superficie Total", f"{area:.2f} ha")
            
            # RECOMENDACIÓN BASADA EN PROYECTO
            st.markdown("---")
            st.write("**Alertas de Consultoría:**")
            if tipo_proyecto == "Inmobiliario/Urbano" and area > 5:
                st.warning("⚠️ Requiere análisis de Humedales Urbanos.")
            elif tipo_proyecto == "Energía (Eólico/Solar)":
                st.info("ℹ️ Recomendado: Verificar servidumbres eléctricas.")

else:
    st.info("Bienvenido a BioCore Intelligence. Inicie sesión para comenzar el análisis.")
