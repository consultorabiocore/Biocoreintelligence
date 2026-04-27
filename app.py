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

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="BioCore Intelligence", layout="wide")

def clean(text):
    return text.encode('latin-1', 'replace').decode('latin-1')

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

# --- LÓGICA DE REPORTE PDF ---
def generar_pdf(cliente, proyecto, area, datos_indices):
    pdf = FPDF()
    pdf.add_page()
    
    # Encabezado Estilo BioCore
    pdf.set_fill_color(20, 50, 80)
    pdf.rect(0, 0, 210, 40, 'F')
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("helvetica", "B", 16)
    pdf.cell(0, 20, clean(f"REPORTE DE CUMPLIMIENTO: {cliente.upper()}"), align="C", ln=1)
    pdf.set_font("helvetica", "I", 10)
    pdf.cell(0, 5, clean(f"Consultora: BioCore Intelligence | Fecha: {datetime.now().strftime('%d/%m/%Y')}"), align="C", ln=1)
    
    pdf.ln(25)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("helvetica", "B", 12)
    pdf.cell(0, 10, clean(f"DIAGNÓSTICO TÉCNICO: {proyecto}"), ln=1)
    
    # Cuerpo del Informe
    pdf.set_font("helvetica", "", 11)
    pdf.multi_cell(0, 7, clean(
        f"Se ha realizado un análisis espectral multivariable sobre una superficie de {area:.2f} hectáreas. "
        "A continuación se detallan los hallazgos críticos basados en sensores remotos Sentinel-2."
    ))
    
    pdf.ln(5)
    # Tabla de Índices
    pdf.set_font("helvetica", "B", 10)
    pdf.cell(95, 10, clean("Indicador"), border=1)
    pdf.cell(95, 10, clean("Estado Detectado"), border=1, ln=1)
    
    pdf.set_font("helvetica", "", 10)
    for k, v in datos_indices.items():
        pdf.cell(95, 10, clean(k), border=1)
        pdf.cell(95, 10, clean(v), border=1, ln=1)

    # Firma
    pdf.set_y(250)
    pdf.set_font("helvetica", "B", 10)
    pdf.cell(0, 5, clean("Loreto Campos Carrasco"), align="C", ln=1)
    pdf.set_font("helvetica", "I", 9)
    pdf.cell(0, 5, clean("Directora Técnica - BioCore Intelligence"), align="C", ln=1)
    
    return pdf.output(dest='S').encode('latin-1')

# --- INTERFAZ ---
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
        st.success("Sessión Iniciada")
        cliente = st.text_input("Nombre del Cliente", "Titular_Proyecto")
        tipo_proyecto = st.selectbox("Categoría:", ["Minería", "Saneamiento", "Energía", "Industrial", "Inmobiliario"])
        input_coords = st.text_area("Coordenadas (lat, lon):", placeholder="-37.28, -72.70", height=80)
        capa_select = st.radio("Variable de Mapa:", ["NDVI (Vegetación)", "NDWI (Agua)", "NDSI (Suelo/Nieve)", "NDMI (Humedad)"])
        if st.button("Cerrar Sesión"):
            st.session_state.auth = False
            st.rerun()

if st.session_state.get('auth', False):
    st.title(f"Panel BioCore: {tipo_proyecto}")
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        # Lógica de Mapa y GEE (Similar a las anteriores)
        lat_c, lon_c = -37.28, -72.70 # Default
        m = folium.Map(location=[lat_c, lon_c], zoom_start=13)
        Draw(export=True).add_to(m)
        salida = st_folium(m, width="100%", height=500)

    with col2:
        st.subheader("📋 Gestión de Informe")
        
        if salida.get('last_active_drawing'):
            coords = salida['last_active_drawing']['geometry']['coordinates'][0]
            poly = ee.Geometry.Polygon(coords)
            area = poly.area().divide(10000).getInfo()
            
            st.metric("Superficie", f"{area:.2f} ha")
            
            # SIMULACIÓN DE DATOS PARA EL REPORTE (Aquí puedes conectar tus cálculos reales)
            indices_reporte = {
                "Vigor Vegetal (NDVI)": "Estable (0.65)",
                "Recursos Hídricos (NDWI)": "Sin anomalías (-0.12)",
                "Humedad de Suelo (NDMI)": "Alerta: Baja saturación",
                "Suelo Desnudo (NDSI)": "Exposición moderada"
            }
            
            pdf_bytes = generar_pdf(cliente, tipo_proyecto, area, indices_reporte)
            
            st.download_button(
                label="📥 Descargar Informe Ejecutivo (PDF)",
                data=pdf_bytes,
                file_name=f"Informe_BioCore_{cliente}.pdf",
                mime="application/pdf"
            )
            st.info("El informe incluye diagnóstico técnico y firma de la Directora.")
