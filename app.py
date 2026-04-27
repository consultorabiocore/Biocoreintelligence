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
    st.header("🛰️ BioCore Intelligence")
    
    if not st.session_state.get('auth', False):
        u = st.text_input("Usuario")
        p = st.text_input("Password", type="password")
        if st.button("Entrar"):
            if u == "admin" and p == "loreto2026":
                st.session_state.auth = True
                st.rerun()
    else:
        st.success("Conexión Satelital Activa ✅")
        st.markdown("---")
        
        # 1. TODOS LOS TIPOS DE PROYECTOS (CATEGORÍAS SEIA)
        tipo_proyecto = st.selectbox(
            "Categoría de Proyecto:",
            [
                "Minería", 
                "Industrial / Manufactura", 
                "Infraestructura / Vialidad", 
                "Saneamiento / Rellenos Sanitarios", 
                "Energía (Eólico/Solar/Hídrico)", 
                "Inmobiliario / Urbano", 
                "Conservación / Patrimonio Natural",
                "Agrícola / Forestal",
                "Acuicultura / Borde Costero"
            ]
        )

        # 2. CARGA DE COORDENADAS CON EJEMPLO VISUAL
        st.subheader("📍 Coordenadas de Campo")
        ejemplo = "-37.2812, -72.7034\n-37.2845, -72.7056"
        input_coords = st.text_area("Pega aquí tus puntos (lat, lon):", placeholder=ejemplo, height=100)
        
        # 3. TRADUCCIÓN TÉCNICA PARA EL TITULAR
        st.markdown("---")
        st.subheader("🔍 Análisis Visual del Terreno")
        
        if tipo_proyecto == "Minería":
            opciones = {"Mapa Base": "BASE", "Estado de Suelos y Relaves": "NDSI", "Salud Vegetal Perimetral": "NDVI"}
        elif tipo_proyecto == "Saneamiento / Rellenos Sanitarios":
            opciones = {"Mapa Base": "BASE", "Detección de Humedad y Filtraciones": "NDMI", "Control de Cuerpos de Agua": "NDWI"}
        elif tipo_proyecto == "Inmobiliario / Urbano":
            opciones = {"Mapa Base": "BASE", "Zonas Inundables / Humedales": "NDWI", "Áreas Verdes y Vigor": "NDVI"}
        elif tipo_proyecto == "Acuicultura / Borde Costero":
            opciones = {"Mapa Base": "BASE", "Turbidez y Cuerpos de Agua": "NDWI", "Vigor de Vegetación Ribereña": "NDVI"}
        elif tipo_proyecto in ["Conservación / Patrimonio Natural", "Agrícola / Forestal"]:
            opciones = {"Mapa Base": "BASE", "Salud Forestal Avanzada": "EVI", "Humedad de la Biomasa": "NDMI"}
        else:
            opciones = {"Mapa Base": "BASE", "Salud de la Vegetación": "NDVI", "Humedad del Suelo": "NDMI"}

        capa_label = st.radio("Ver en mapa:", list(opciones.keys()))
        capa_tecnica = opciones[capa_label]
        
        st.markdown("---")
        st.info("📩 **¿Proyecto Especial?** Si no encuentras tu categoría, contáctame para habilitar variables personalizadas.")
        
        if st.button("Cerrar Sesión"):
            st.session_state.auth = False
            st.rerun()

# --- PANEL PRINCIPAL ---
if st.session_state.get('auth', False):
    st.title(f"BioCore: Evaluación de {tipo_proyecto}")
    
    # Procesamiento de Datos Pegados
    df_puntos = None
    lat_c, lon_c = -37.28, -72.70
    if input_coords:
        try:
            data = io.StringIO(input_coords.strip())
            df_puntos = pd.read_csv(data, names=['lat', 'lon'], skipinitialspace=True)
            if not df_puntos.empty:
                lat_c, lon_c = df_puntos['lat'].iloc[0], df_puntos['lon'].iloc[0]
        except:
            st.sidebar.error("⚠️ Error en formato: usa 'lat, lon'")

    col1, col2 = st.columns([3, 1])
    
    with col1:
        m = folium.Map(location=[lat_c, lon_c], zoom_start=13)
        
        if df_puntos is not None:
            for i, row in df_puntos.iterrows():
                folium.Marker([row['lat'], row['lon']], icon=folium.Icon(color='green', icon='leaf')).add_to(m)

        # Lógica GEE Multivariable
        if conectado and capa_tecnica != "BASE":
            s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED') \
                .filterBounds(ee.Geometry.Point([lon_c, lat_c])) \
                .filterDate('2024-01-01', '2024-12-31').sort('CLOUDY_PIXEL_PERCENTAGE').first()

            if capa_tecnica == "NDVI":
                img = s2.normalizedDifference(['B8', 'B4'])
                vis = {'min': 0, 'max': 0.8, 'palette': ['red', 'yellow', 'green']}
            elif capa_tecnica == "NDWI":
                img = s2.normalizedDifference(['B3', 'B8'])
                vis = {'min': -0.5, 'max': 0.5, 'palette': ['white', 'blue']}
            elif capa_tecnica == "NDMI":
                img = s2.normalizedDifference(['B8', 'B11'])
                vis = {'min': -0.5, 'max': 0.5, 'palette': ['#f7fbff','#6baed6','#08306b']}
            elif capa_tecnica == "NDSI":
                img = s2.normalizedDifference(['B11', 'B3'])
                vis = {'min': -1, 'max': 1, 'palette': ['blue', 'white', 'brown']}
            elif capa_tecnica == "EVI":
                img = s2.expression('2.5 * ((B8 - B4) / (B8 + 6 * B4 - 7.5 * B2 + 1))', 
                                    {'B8': s2.select('B8'), 'B4': s2.select('B4'), 'B2': s2.select('B2')})
                vis = {'min': 0, 'max': 1, 'palette': ['white', 'green']}

            map_id = ee.Image(img).getMapId(vis)
            folium.TileLayer(tiles=map_id['tile_fetcher'].url_format, attr='GEE', overlay=True).add_to(m)

        Draw(export=True).add_to(m)
        salida = st_folium(m, width="100%", height=550)

    with col2:
        st.subheader("📊 Resultados")
        if df_puntos is not None:
            st.write(f"📍 {len(df_puntos)} puntos detectados.")
            st.dataframe(df_puntos, height=180)
        
        if salida.get('last_active_drawing'):
            coords = salida['last_active_drawing']['geometry']['coordinates'][0]
            area = ee.Geometry.Polygon(coords).area().divide(10000).getInfo()
            st.metric("Área Seleccionada", f"{area:.2f} ha")
            
            st.markdown("---")
            st.write("**Resumen para Titular:**")
            st.caption(f"Análisis basado en {capa_label}. Los valores resaltados permiten identificar áreas críticas de cumplimiento ambiental.")

else:
    st.info("Bienvenido a BioCore Intelligence. Inicie sesión para comenzar.")
