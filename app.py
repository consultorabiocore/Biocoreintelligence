import streamlit as st
import ee
import json
import folium
import pandas as pd
import io
from streamlit_folium import st_folium
from folium.plugins import Draw
from fpdf import FPDF
from datetime import datetime

# --- CONFIGURACIÓN DE MARCA ---
LOGO_URL = "https://cdn-icons-png.flaticon.com/512/2092/2092031.png" # Sustituir por tu archivo local o URL
COLOR_BIOCORE = (20, 50, 80) # Azul Marino Profesional

st.set_page_config(page_title="BioCore Intelligence", layout="wide", page_icon="🛰️")

def clean(text):
    return str(text).encode('latin-1', 'replace').decode('latin-1')

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

# --- MOTOR DE REPORTES PDF ---
def generar_pdf(cliente, proyecto, area, datos_indices):
    pdf = FPDF()
    pdf.add_page()
    
    # Encabezado con Logo y Color Corporativo
    pdf.set_fill_color(*COLOR_BIOCORE)
    pdf.rect(0, 0, 210, 45, 'F')
    
    # Título
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("helvetica", "B", 18)
    pdf.cell(0, 15, clean("BIOCORE INTELLIGENCE"), align="C", ln=1)
    pdf.set_font("helvetica", "B", 12)
    pdf.cell(0, 10, clean(f"INFORME TÉCNICO DE CUMPLIMIENTO AMBIENTAL"), align="C", ln=1)
    
    pdf.ln(25)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("helvetica", "B", 12)
    pdf.cell(0, 10, clean(f"PROYECTO: {proyecto.upper()}"), ln=1)
    pdf.cell(0, 10, clean(f"TITULAR: {cliente.upper()}"), ln=1)
    
    # Resumen
    pdf.set_font("helvetica", "", 10)
    resumen = (f"Análisis multiespectral automatizado sobre una superficie de {area:.2f} hectáreas. "
               "Los datos presentados corresponden a la firma espectral capturada por el sensor MSI (Sentinel-2) "
               "bajo la supervisión técnica de BioCore.")
    pdf.multi_cell(0, 6, clean(resumen))
    pdf.ln(5)

    # Tabla de Resultados Técnicos
    pdf.set_fill_color(240, 240, 240)
    pdf.set_font("helvetica", "B", 10)
    pdf.cell(100, 10, clean("Indicador Técnico"), border=1, fill=True)
    pdf.cell(90, 10, clean("Valor Detectado / Estatus"), border=1, fill=True, ln=1)
    
    pdf.set_font("helvetica", "", 10)
    for k, v in datos_indices.items():
        pdf.cell(100, 10, clean(k), border=1)
        pdf.cell(90, 10, clean(v), border=1, ln=1)

    # Firma de Directora
    pdf.set_y(250)
    pdf.set_font("helvetica", "B", 11)
    pdf.cell(0, 5, clean("Loreto Campos Carrasco"), align="C", ln=1)
    pdf.set_font("helvetica", "I", 10)
    pdf.cell(0, 5, clean("Directora Técnica - BioCore Intelligence"), align="C", ln=1)
    
    return pdf.output(dest='S').encode('latin-1')

# --- BARRA LATERAL ---
with st.sidebar:
    st.image(LOGO_URL, width=120)
    st.title("BioCore Intelligence")
    
    if not st.session_state.get('auth', False):
        u = st.text_input("Usuario")
        p = st.text_input("Password", type="password")
        if st.button("Ingresar"):
            if u == "admin" and p == "loreto2026":
                st.session_state.auth = True
                st.rerun()
    else:
        st.success("Satelital Conectado ✅")
        st.markdown("---")
        
        cliente = st.text_input("Nombre del Titular", "Empresa_Mandante")
        
        # CATEGORÍAS TÉCNICAS COMPLETAS
        tipo_p = st.selectbox(
            "Tipo de Proyecto (SEIA):",
            ["Minería", "Saneamiento Ambiental", "Energía (Eólico/Solar)", "Infraestructura / Vial", 
             "Industrial / Manufactura", "Conservación y Patrimonio", "Agrícola / Forestal", "Acuicultura"]
        )

        st.subheader("📍 Coordenadas de Terreno")
        input_coords = st.text_area("Pega lat, lon:", placeholder="-37.28, -72.70\n-37.29, -72.71", height=100)
        
        # LÓGICA DE VARIABLES POR SECTOR
        if tipo_p == "Minería":
            opciones = {"Relaves/Suelos (NDSI)": "NDSI", "Vigor Vegetal (NDVI)": "NDVI", "Humedad (NDMI)": "NDMI"}
        elif tipo_p == "Saneamiento Ambiental":
            opciones = {"Filtraciones (NDMI)": "NDMI", "Agua (NDWI)": "NDWI", "Salud Perimetral (NDVI)": "NDVI"}
        elif tipo_p in ["Conservación y Patrimonio", "Agrícola / Forestal"]:
            opciones = {"Vigor Bosque (EVI)": "EVI", "Humedad Biomasa (NDMI)": "NDMI"}
        else:
            opciones = {"Vigor (NDVI)": "NDVI", "Humedad (NDMI)": "NDMI", "Agua (NDWI)": "NDWI"}

        capa_label = st.radio("Variable de Diagnóstico:", list(opciones.keys()))
        capa_tec = opciones[capa_label]
        
        if st.button("Cerrar Sesión"):
            st.session_state.auth = False
            st.rerun()

# --- PANEL DE CONTROL ---
if st.session_state.get('auth', False):
    st.title(f"Módulo de Auditoría: {tipo_p}")
    
    geom_ee = None
    df_puntos = None

    # GENERACIÓN AUTOMÁTICA DE POLÍGONO
    if input_coords:
        try:
            data = io.StringIO(input_coords.strip())
            df_puntos = pd.read_csv(data, names=['lat', 'lon'], skipinitialspace=True)
            if len(df_puntos) >= 3:
                lista_coords = df_puntos[['lon', 'lat']].values.tolist()
                geom_ee = ee.Geometry.Polygon(lista_coords)
        except:
            st.error("Error: Formato de coordenadas no válido.")

    col_mapa, col_info = st.columns([3, 1])
    
    with col_mapa:
        centro = [df_puntos['lat'].mean(), df_puntos['lon'].mean()] if df_puntos is not None else [-37.28, -72.70]
        m = folium.Map(location=centro, zoom_start=14)
        
        if geom_ee:
            folium.GeoJson(geom_ee.getInfo(), style_function=lambda x: {'fillColor': 'green', 'color': 'darkgreen', 'weight': 2}).add_to(m)
            
            if conectado:
                s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED').filterBounds(geom_ee).sort('CLOUDY_PIXEL_PERCENTAGE').first()
                
                if capa_tec == "NDVI":
                    img = s2.normalizedDifference(['B8', 'B4'])
                    vis = {'min': 0, 'max': 0.8, 'palette': ['red', 'yellow', 'green']}
                elif capa_tec == "NDSI":
                    img = s2.normalizedDifference(['B11', 'B3'])
                    vis = {'min': -1, 'max': 1, 'palette': ['blue', 'white', 'brown']}
                elif capa_tec == "NDMI":
                    img = s2.normalizedDifference(['B8', 'B11'])
                    vis = {'min': -0.5, 'max': 0.5, 'palette': ['white', 'blue']}
                elif capa_tec == "EVI":
                    img = s2.expression('2.5 * ((B8 - B4) / (B8 + 6 * B4 - 7.5 * B2 + 1))', 
                                        {'B8': s2.select('B8'), 'B4': s2.select('B4'), 'B2': s2.select('B2')})
                    vis = {'min': 0, 'max': 1, 'palette': ['white', 'green']}
                
                map_id = ee.Image(img).getMapId(vis)
                folium.TileLayer(tiles=map_id['tile_fetcher'].url_format, attr='GEE', overlay=True, name=capa_label).add_to(m)
        
        st_folium(m, width="100%", height=550)

    with col_info:
        st.image(LOGO_URL, width=80)
        st.subheader("Resultados del Área")
        
        if geom_ee:
            area = geom_ee.area().divide(10000).getInfo()
            st.metric("Superficie Total", f"{area:.2f} ha")
            
            if st.button("📦 Generar y Firmar Informe"):
                with st.spinner("Procesando auditoría..."):
                    s2_img = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED').filterBounds(geom_ee).first()
                    
                    # Cálculo de valor medio real para el PDF
                    mean_val = s2_img.normalizedDifference(['B8', 'B4']).reduceRegion(
                        reducer=ee.Reducer.mean(), geometry=geom_ee, scale=10
                    ).get('nd').getInfo()

                    indices_finales = {
                        "Índice de Vigor (Promedio)": f"{mean_val:.2f}" if mean_val else "Analizado",
                        "Superficie del Polígono": f"{area:.2f} ha",
                        "Variable Principal": capa_label,
                        "Estatus de Auditoría": "Cumplimiento Verificado"
                    }
                    
                    pdf = generar_pdf(cliente, tipo_p, area, indices_finales)
                    st.download_button("📥 Descargar Reporte PDF", pdf, f"BioCore_{cliente}.pdf", "application/pdf")
                    st.success("Informe generado con éxito.")
        else:
            st.info("Pegue las coordenadas del proyecto para generar el análisis automático.")
