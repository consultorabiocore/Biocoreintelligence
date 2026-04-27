import streamlit as st
import ee
import json
import folium
import pandas as pd
import io
import matplotlib.pyplot as plt
import os
import base64
from streamlit_folium import st_folium
from fpdf import FPDF
from datetime import datetime, timedelta

# --- CONFIGURACIÓN DE MARCA ---
LOGO_PATH = os.path.join("assets", "logo_biocore.png")
COLOR_BIOCORE = (20, 50, 80)

st.set_page_config(page_title="BioCore Intelligence", layout="wide", page_icon="🛰️")

# Función para convertir imagen local a Base64 (evita que se vea borrosa)
def get_base64_image(path):
    if os.path.exists(path):
        with open(path, "rb") as f:
            data = f.read()
        return base64.b64encode(data).decode()
    return None

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

# --- MOTOR DE REPORTES PDF ---
def generar_reporte_biocore(cliente, proyecto, df_hist, alerta_fuego, alerta_desvio):
    pdf = FPDF()
    pdf.add_page()
    
    # Franja Corporativa
    pdf.set_fill_color(*COLOR_BIOCORE)
    pdf.rect(0, 0, 210, 40, 'F')
    
    if os.path.exists(LOGO_PATH):
        pdf.image(LOGO_PATH, x=15, y=10, h=18)
    
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("helvetica", "B", 16)
    pdf.set_xy(45, 12)
    pdf.cell(0, 10, clean("BIOCORE INTELLIGENCE"), ln=1)
    
    pdf.ln(25); pdf.set_text_color(0, 0, 0)
    pdf.set_font("helvetica", "B", 12); pdf.cell(0, 10, clean(f"INFORME PREVENTIVO: {cliente}"), ln=1)
    
    if alerta_fuego or alerta_desvio:
        pdf.set_fill_color(255, 230, 230)
        pdf.cell(0, 10, clean(" STATUS: ALERTA TÉCNICA ACTIVA"), border=1, ln=1, fill=True)

    if not df_hist.empty:
        plt.figure(figsize=(10, 4))
        df_hist['fecha'] = pd.to_datetime(df_hist['fecha'])
        plt.plot(df_hist['fecha'], df_hist['ndvi'], color='#143250')
        plt.title("Analisis Historico de Linea de Base")
        plt.savefig("temp_pdf_chart.png", dpi=150)
        pdf.image("temp_pdf_chart.png", x=15, y=100, w=180)
        plt.close()

    pdf.set_y(250); pdf.set_font("helvetica", "B", 10)
    pdf.cell(0, 5, clean("Loreto Campos Carrasco"), align="C", ln=1)
    return pdf.output(dest='S').encode('latin-1')

# --- BARRA LATERAL (LOGO NITIDO Y CENTRADO) ---
with st.sidebar:
    logo_b64 = get_base64_image(LOGO_PATH)
    if logo_b64:
        # HTML/CSS para centrar y mantener nitidez
        st.markdown(
            f"""
            <div style="display: flex; justify-content: center; align-items: center; padding: 10px 0;">
                <img src="data:image/png;base64,{logo_b64}" width="100" style="image-rendering: -webkit-optimize-contrast; image-rendering: crisp-edges;">
            </div>
            """,
            unsafe_allow_html=True
        )
    else:
        st.warning("Logo no encontrado en /assets")
    
    st.markdown("<h3 style='text-align: center;'>BioCore Intelligence</h3>", unsafe_allow_html=True)
    st.markdown("---")
    
    if not st.session_state.get('auth', False):
        u = st.text_input("Usuario")
        p = st.text_input("Clave", type="password")
        if st.button("Entrar"):
            if u == "admin" and p == "loreto2026":
                st.session_state.auth = True; st.rerun()
    else:
        st.success("🛰️ Sistema Activo")
        cliente = st.text_input("Titular", "Mandante_Proyecto")
        anios = st.slider("Historial (Años)", 5, 40, 20)
        input_coords = st.text_area("Coordenadas:")
        if st.button("Salir"): st.session_state.auth = False; st.rerun()

# --- PANEL PRINCIPAL ---
if st.session_state.get('auth', False):
    st.title("Plataforma de Prevención de Multas")
    
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
                if st.button(f"🔍 Escaneo {anios} Años"):
                    with st.spinner("Analizando NASA y ESA..."):
                        # Fuego NASA FIRMS
                        fuego = ee.ImageCollection("FIRMS").filterBounds(geom).filterDate((datetime.now()-timedelta(days=2)).strftime('%Y-%m-%d'), datetime.now().strftime('%Y-%m-%d')).size().getInfo() > 0
                        
                        # Histórico Landsat
                        col = ee.ImageCollection("LANDSAT/LC08/C02/T1_L2").filterBounds(geom).filter(ee.Filter.lt('CLOUD_COVER', 10)).limit(anios*2)
                        datos = col.map(lambda img: ee.Feature(None, {
                            'fecha': img.date().format('YYYY-MM'),
                            'ndvi': img.normalizedDifference(['SR_B5', 'SR_B4']).reduceRegion(ee.Reducer.mean(), geom, 60).get('nd')
                        })).getInfo()
                        
                        df_hist = pd.DataFrame([f['properties'] for f in datos['features'] if f['properties']['ndvi'] is not None])
                        alerta_desv = not df_hist.empty and df_hist['ndvi'].iloc[-1] < (df_hist['ndvi'].mean() * 0.75)
                        
                        pdf = generar_reporte_biocore(cliente, "General", df_hist, fuego, alerta_desv)
                        st.download_button("📥 Descargar Reporte de Blindaje", pdf, f"BioCore_{cliente}.pdf")
                        
                        if fuego: st.error("🔥 ALERTA: Fuego detectado por satélites de la NASA.")
                        if alerta_desv: st.warning("⚠️ RIESGO: Desviación detectada en la línea de base.")
        except:
            st.error("Error en el formato de coordenadas.")
