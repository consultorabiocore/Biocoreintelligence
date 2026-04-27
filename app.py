import streamlit as st
import ee
import json
import folium
import pandas as pd
import io
import matplotlib.pyplot as plt
import os
from streamlit_folium import st_folium
from fpdf import FPDF
from datetime import datetime, timedelta

# --- CONFIGURACIÓN DE MARCA Y ASSETS ---
LOGO_LOCAL = os.path.join("assets", "logo_biocore.png")
LOGO_NUBE = "https://cdn-icons-png.flaticon.com/512/2092/2092031.png"
LOGO_FINAL = LOGO_LOCAL if os.path.exists(LOGO_LOCAL) else LOGO_NUBE

COLOR_BIOCORE = (20, 50, 80) 

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
    except: return False

conectado = iniciar_gee()

# --- MOTOR DE REPORTES PDF (DISEÑO AJUSTADO) ---
def generar_reporte_biocore(cliente, proyecto, df_hist, alerta_fuego, alerta_desvio):
    pdf = FPDF()
    pdf.add_page()
    
    # Franja Corporativa
    pdf.set_fill_color(*COLOR_BIOCORE)
    pdf.rect(0, 0, 210, 40, 'F')
    
    # Logo en el PDF: Más pequeño y posicionado
    try:
        pdf.image(LOGO_FINAL, x=15, y=10, h=18)
    except: pass
    
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("helvetica", "B", 16)
    pdf.set_xy(45, 12)
    pdf.cell(0, 10, clean("BIOCORE INTELLIGENCE"), ln=1)
    pdf.set_font("helvetica", "B", 9)
    pdf.set_x(45)
    pdf.cell(0, 5, clean("AUDITORÍA SATELITAL Y PREVENCIÓN DE RIESGOS"), ln=1)
    
    pdf.ln(25); pdf.set_text_color(0, 0, 0)
    pdf.set_font("helvetica", "B", 12); pdf.cell(0, 10, clean(f"TITULAR: {cliente}"), ln=1)
    
    # Alertas
    if alerta_fuego or alerta_desvio:
        pdf.set_fill_color(255, 230, 230)
        pdf.set_font("helvetica", "B", 10)
        msg = "NOTIFICACIÓN DE RIESGO ACTIVA" if alerta_fuego else "ANOMALÍA EN LÍNEA DE BASE"
        pdf.cell(0, 10, clean(f" STATUS: {msg}"), border=1, ln=1, fill=True)

    # Gráfico
    if not df_hist.empty:
        plt.figure(figsize=(10, 4))
        df_hist['fecha'] = pd.to_datetime(df_hist['fecha'])
        df_hist = df_hist.sort_values('fecha')
        plt.plot(df_hist['fecha'], df_hist['ndvi'], color='#143250', linewidth=1.2)
        plt.title("Tendencia Histórica Decadal")
        plt.savefig("grafico_temp.png", dpi=150)
        pdf.image("grafico_temp.png", x=15, y=100, w=180)
        plt.close()

    pdf.set_y(250); pdf.set_font("helvetica", "B", 10)
    pdf.cell(0, 5, clean("Loreto Campos Carrasco"), align="C", ln=1)
    pdf.set_font("helvetica", "I", 9)
    pdf.cell(0, 5, clean("Directora Técnica - BioCore Intelligence"), align="C", ln=1)
    
    return pdf.output(dest='S').encode('latin-1')

# --- INTERFAZ ---
with st.sidebar:
    # Centrar logo pequeño con columnas
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.image(LOGO_FINAL, width=100) # Tamaño reducido a 100px
    
    st.markdown("<h3 style='text-align: center;'>BioCore Intelligence</h3>", unsafe_allow_html=True)
    st.markdown("---")
    
    if st.session_state.get('auth', False):
        cliente = st.text_input("Titular RCA", "Mandante_Proyecto")
        tipo_p = st.selectbox("Sector:", ["Minería", "Humedales", "Forestal", "Energía"])
        anios = st.slider("Años Históricos:", 5, 40, 20)
        input_coords = st.text_area("Coordenadas:")
        if st.button("Cerrar Sesión"): st.session_state.auth = False; st.rerun()
    else:
        u = st.text_input("Usuario")
        p = st.text_input("Clave", type="password")
        if st.button("Entrar"):
            if u == "admin" and p == "loreto2026":
                st.session_state.auth = True; st.rerun()

if st.session_state.get('auth', False):
    st.title("Monitoreo de Cumplimiento Ambiental")
    
    if input_coords:
        try:
            data = io.StringIO(input_coords.strip())
            df_p = pd.read_csv(data, names=['lat', 'lon'])
            geom = ee.Geometry.Polygon(df_p[['lon', 'lat']].values.tolist())
            
            col_map, col_res = st.columns([2, 1])
            with col_map:
                m = folium.Map(location=[df_p['lat'].mean(), df_p['lon'].mean()], zoom_start=13)
                if conectado:
                    s1 = ee.ImageCollection('COPERNICUS/S1_GRD').filterBounds(geom).first()
                    if s1:
                        mid = s1.getMapId({'min': -25, 'max': 0})
                        folium.TileLayer(tiles=mid['tile_fetcher'].url_format, attr='ESA').add_to(m)
                folium.GeoJson(geom.getInfo()).add_to(m)
                st_folium(m, width="100%", height=500)
            
            with col_res:
                if st.button(f"🔍 Auditoría {anios} Años"):
                    with st.spinner("Procesando..."):
                        # Fuego y Histórico
                        fuego = ee.ImageCollection("FIRMS").filterBounds(geom).filterDate((datetime.now()-timedelta(days=2)).strftime('%Y-%m-%d'), datetime.now().strftime('%Y-%m-%d')).size().getInfo() > 0
                        
                        col = ee.ImageCollection("LANDSAT/LC08/C02/T1_L2").filterBounds(geom).filter(ee.Filter.lt('CLOUD_COVER', 10)).limit(anios*2)
                        datos = col.map(lambda img: ee.Feature(None, {
                            'fecha': img.date().format('YYYY-MM'),
                            'ndvi': img.normalizedDifference(['SR_B5', 'SR_B4']).reduceRegion(ee.Reducer.mean(), geom, 60).get('nd')
                        })).getInfo()
                        
                        df_hist = pd.DataFrame([f['properties'] for f in datos['features'] if f['properties']['ndvi'] is not None])
                        alerta_desv = not df_hist.empty and df_hist['ndvi'].iloc[-1] < (df_hist['ndvi'].mean() * 0.7)
                        
                        pdf = generar_reporte_biocore(cliente, tipo_p, df_hist, fuego, alerta_desv)
                        st.download_button("📥 Descargar Informe", pdf, f"BioCore_{cliente}.pdf")
                        st.success("Análisis preventivo finalizado.")
        except:
            st.error("Error en coordenadas.")
