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
        nombre_cliente = st.text_input("Cliente/Proyecto", "Proyecto_Laja")
        
        # --- CUADRO PARA PEGAR COORDENADAS ---
        st.subheader("📍 Pegar Coordenadas")
        input_coords = st.text_area(
            "Pega aquí (formato: lat, lon)", 
            placeholder="-37.2812, -72.7034\n-37.2845, -72.7056",
            help="Una fila por cada punto."
        )
        
        st.markdown("---")
        capa_select = st.radio("Capa Satelital:", ["Mapa Base", "NDVI (Vegetación)", "NDWI (Agua)"])
        
        if st.button("Cerrar Sesión"):
            st.session_state.auth = False
            st.rerun()

# --- PANEL PRINCIPAL ---
if st.session_state.get('auth', False):
    st.header(f"Panel: {nombre_cliente}")
    
    # Procesar las coordenadas pegadas
    df_puntos = None
    lat_centro, lon_centro = -37.28, -72.70
    
    if input_coords:
        try:
            # Convertimos el texto pegado en un DataFrame
            data = io.StringIO(input_coords.replace(" ", ""))
            df_puntos = pd.read_csv(data, names=['lat', 'lon'])
            lat_centro = df_puntos['lat'].iloc[0]
            lon_centro = df_puntos['lon'].iloc[0]
        except:
            st.error("Formato de coordenadas incorrecto. Usa: lat, lon")

    col1, col2 = st.columns([3, 1])
    
    with col1:
        m = folium.Map(location=[lat_centro, lon_centro], zoom_start=14)
        
        # Dibujar los puntos pegados
        if df_puntos is not None:
            for i, row in df_puntos.iterrows():
                folium.Marker(
                    [row['lat'], row['lon']], 
                    popup=f"Punto {i+1}",
                    icon=folium.Icon(color='green', icon='leaf')
                ).add_to(m)

        # Capas GEE
        if conectado and capa_select != "Mapa Base":
            s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED') \
                .filterBounds(ee.Geometry.Point([lon_centro, lat_centro])) \
                .filterDate('2024-01-01', '2024-12-31') \
                .sort('CLOUDY_PIXEL_PERCENTAGE').first()
            
            # Ajuste de índices
            if "NDVI" in capa_select:
                img = s2.normalizedDifference(['B8', 'B4'])
                vis = {'min': 0, 'max': 0.8, 'palette': ['red', 'yellow', 'green']}
            else:
                img = s2.normalizedDifference(['B3', 'B8'])
                vis = {'min': -0.5, 'max': 0.5, 'palette': ['white', 'blue']}
            
            map_id = ee.Image(img).getMapId(vis)
            folium.TileLayer(tiles=map_id['tile_fetcher'].url_format, attr='GEE', overlay=True).add_to(m)

        Draw(export=True).add_to(m)
        salida = st_folium(m, width="100%", height=500, key="biocore_map")

    with col2:
        st.subheader("📊 Análisis")
        if df_puntos is not None:
            st.write(f"📍 **{len(df_puntos)} puntos** detectados.")
            
            # EXTRA: Mostrar el valor de NDVI para cada punto si la capa está activa
            if conectado and capa_select == "NDVI (Vegetación)":
                st.info("Extrayendo vigor vegetal...")
                # Aquí podríamos añadir la lógica de extracción por punto
        
        if salida.get('last_active_drawing'):
            coords = salida['last_active_drawing']['geometry']['coordinates'][0]
            area = ee.Geometry.Polygon(coords).area().divide(10000).getInfo()
            st.metric("Área Polígono", f"{area:.2f} ha")

else:
    st.info("Inicie sesión para acceder.")
