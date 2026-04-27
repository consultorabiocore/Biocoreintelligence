import streamlit as st
import ee
import json
import folium
import pandas as pd
import io
import matplotlib.pyplot as plt
from streamlit_folium import st_folium
from folium.plugins import Draw
from fpdf import FPDF
from datetime import datetime

# --- CONFIGURACIÓN Y UTILIDADES ---
st.set_page_config(page_title="BioCore Intelligence", layout="wide", page_icon="🛰️")

def clean(text):
    """Limpia texto para evitar errores de codificación en PDF"""
    return str(text).encode('latin-1', 'replace').decode('latin-1')

def iniciar_gee():
    try:
        # Intenta cargar desde secrets (Streamlit Cloud)
        info = json.loads(st.secrets["GEE_JSON"])
        pk = info["private_key"].replace("\\n", "\n")
        creds = ee.ServiceAccountCredentials(info["client_email"], key_data=pk)
        ee.Initialize(creds)
        return True
    except Exception as e:
        st.error(f"Error de conexión GEE: {e}")
        return False

conectado = iniciar_gee()

# --- MOTOR DE REPORTES PDF ---
def generar_pdf(cliente, proyecto, area, datos_indices):
    pdf = FPDF()
    pdf.add_page()
    
    # Encabezado Corporativo
    pdf.set_fill_color(20, 50, 80) # Azul BioCore
    pdf.rect(0, 0, 210, 40, 'F')
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("helvetica", "B", 16)
    pdf.cell(0, 20, clean(f"REPORTE TÉCNICO: {cliente.upper()}"), align="C", ln=1)
    pdf.set_font("helvetica", "I", 10)
    pdf.cell(0, 5, clean(f"BioCore Intelligence | Auditoría Satelital | {datetime.now().strftime('%d/%m/%Y')}"), align="C", ln=1)
    
    pdf.ln(25)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("helvetica", "B", 12)
    pdf.cell(0, 10, clean(f"DIAGNÓSTICO DE CUMPLIMIENTO AMBIENTAL: {proyecto}"), ln=1)
    
    # Resumen Ejecutivo
    pdf.set_font("helvetica", "", 10)
    resumen = (
        f"Se ha procesado una superficie de {area:.2f} hectáreas utilizando sensores remotos Sentinel-2 (Copernicus). "
        "El presente informe analiza la firma espectral de los componentes ambientales críticos para el titular."
    )
    pdf.multi_cell(0, 6, clean(resumen))
    pdf.ln(5)

    # Tabla de Resultados
    pdf.set_fill_color(230, 230, 230)
    pdf.set_font("helvetica", "B", 10)
    pdf.cell(100, 10, clean("Indicador / Índice Satelital"), border=1, fill=True)
    pdf.cell(90, 10, clean("Valor / Estado Detectado"), border=1, fill=True, ln=1)
    
    pdf.set_font("helvetica", "", 10)
    for k, v in datos_indices.items():
        pdf.cell(100, 10, clean(k), border=1)
        pdf.cell(90, 10, clean(v), border=1, ln=1)

    # Firma Directora
    pdf.set_y(250)
    pdf.set_font("helvetica", "B", 10)
    pdf.cell(0, 5, clean("Loreto Campos Carrasco"), align="C", ln=1)
    pdf.set_font("helvetica", "I", 9)
    pdf.cell(0, 5, clean("Directora Técnica - BioCore Intelligence"), align="C", ln=1)
    
    return pdf.output(dest='S').encode('latin-1')

# --- INTERFAZ DE USUARIO ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2092/2092031.png", width=100)
    st.title("BioCore v3.0")
    
    if not st.session_state.get('auth', False):
        u = st.text_input("Usuario")
        p = st.text_input("Password", type="password")
        if st.button("Acceder"):
            if u == "admin" and p == "loreto2026":
                st.session_state.auth = True
                st.rerun()
    else:
        st.success("Satelital Conectado ✅")
        st.markdown("---")
        
        nombre_cliente = st.text_input("Nombre del Cliente", "Titular_01")
        
        tipo_proyecto = st.selectbox(
            "Categoría de Proyecto:",
            ["Minería", "Industrial", "Infraestructura", "Saneamiento", "Energía", "Conservación", "Agrícola/Forestal"]
        )

        st.subheader("📍 Puntos de Control")
        ejemplo = "-37.2812, -72.7034\n-37.2845, -72.7056"
        input_coords = st.text_area("Pegar coordenadas (lat, lon):", placeholder=ejemplo, height=100)
        
        # Mapeo de variables según proyecto
        if tipo_proyecto == "Minería":
            mapa_vars = {"Base": "BASE", "Suelos y Relaves (NDSI)": "NDSI", "Vegetación (NDVI)": "NDVI"}
        elif tipo_proyecto == "Saneamiento":
            mapa_vars = {"Base": "BASE", "Humedad/Filtraciones (NDMI)": "NDMI", "Agua (NDWI)": "NDWI"}
        else:
            mapa_vars = {"Base": "BASE", "Vigor Vegetal (NDVI)": "NDVI", "Humedad (NDMI)": "NDMI", "Agua (NDWI)": "NDWI"}

        capa_label = st.radio("Capa en Mapa:", list(mapa_vars.keys()))
        capa_tec = mapa_vars[capa_label]

        if st.button("Salir"):
            st.session_state.auth = False
            st.rerun()

# --- PANEL DE CONTROL PRINCIPAL ---
if st.session_state.get('auth', False):
    st.header(f"Evaluación: {tipo_proyecto} - {nombre_cliente}")
    
    df_puntos = None
    lat_c, lon_c = -37.28, -72.70 # Coordenadas Biobío por defecto
    
    if input_coords:
        try:
            data = io.StringIO(input_coords.strip())
            df_puntos = pd.read_csv(data, names=['lat', 'lon'], skipinitialspace=True)
            if not df_puntos.empty:
                lat_c, lon_c = df_puntos['lat'].iloc[0], df_puntos['lon'].iloc[0]
        except:
            st.sidebar.error("Error en formato de coordenadas.")

    col_map, col_res = st.columns([3, 1])
    
    with col_map:
        m = folium.Map(location=[lat_c, lon_c], zoom_start=13)
        
        # Puntos del cliente
        if df_puntos is not None:
            for i, row in df_puntos.iterrows():
                folium.Marker([row['lat'], row['lon']], popup=f"Punto {i+1}", icon=folium.Icon(color='green')).add_to(m)

        # Capas Earth Engine
        if conectado and capa_tec != "BASE":
            s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED') \
                .filterBounds(ee.Geometry.Point([lon_c, lat_c])) \
                .filterDate('2024-01-01', '2026-12-31').sort('CLOUDY_PIXEL_PERCENTAGE').first()

            if capa_tec == "NDVI":
                img = s2.normalizedDifference(['B8', 'B4'])
                vis = {'min': 0, 'max': 0.8, 'palette': ['red', 'yellow', 'green']}
            elif capa_tec == "NDWI":
                img = s2.normalizedDifference(['B3', 'B8'])
                vis = {'min': -0.5, 'max': 0.5, 'palette': ['white', 'blue']}
            elif capa_tec == "NDSI":
                img = s2.normalizedDifference(['B11', 'B3'])
                vis = {'min': -1, 'max': 1, 'palette': ['blue', 'white', 'brown']}
            elif capa_tec == "NDMI":
                img = s2.normalizedDifference(['B8', 'B11'])
                vis = {'min': -0.5, 'max': 0.5, 'palette': ['white', 'cyan', 'blue']}

            map_id = ee.Image(img).getMapId(vis)
            folium.TileLayer(tiles=map_id['tile_fetcher'].url_format, attr='GEE', overlay=True).add_to(m)

        Draw(export=True).add_to(m)
        salida = st_folium(m, width="100%", height=550)

    with col_res:
        st.subheader("📋 Auditoría")
        
        if salida.get('last_active_drawing'):
            coords = salida['last_active_drawing']['geometry']['coordinates'][0]
            poly = ee.Geometry.Polygon(coords)
            area = poly.area().divide(10000).getInfo()
            
            st.metric("Área Analizada", f"{area:.2f} ha")
            
            if st.button("📄 Generar Informe"):
                with st.spinner("Procesando índices..."):
                    # Cálculo real de NDVI para el reporte
                    val_ndvi = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED').filterBounds(poly).first() \
                                .normalizedDifference(['B8', 'B4']).reduceRegion(ee.Reducer.mean(), poly, 10).get('nd').getInfo()
                    
                    indices = {
                        "Vigor Vegetal (Promedio)": f"{val_ndvi:.2f}" if val_ndvi else "Sin Datos",
                        "Superficie del Polígono": f"{area:.2f} ha",
                        "Sensor Utilizado": "Sentinel-2 MSI",
                        "Estado de Cumplimiento": "Analizado"
                    }
                    
                    pdf_bytes = generar_pdf(nombre_cliente, tipo_proyecto, area, indices)
                    st.download_button("📥 Descargar PDF", pdf_bytes, f"BioCore_{nombre_cliente}.pdf", "application/pdf")
                    st.success("Reporte listo para firma.")
        else:
            st.info("Dibuje un polígono en el mapa para habilitar el reporte.")

else:
    st.info("Inicie sesión para acceder al sistema BioCore Intelligence.")
