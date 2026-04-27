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
# Buscamos el logo dentro de la carpeta assets
LOGO_LOCAL = os.path.join("assets", "logo_biocore.png")
LOGO_NUBE = "https://cdn-icons-png.flaticon.com/512/2092/2092031.png"

# Verificación de existencia del logo
if os.path.exists(LOGO_LOCAL):
    LOGO_FINAL = LOGO_LOCAL
else:
    LOGO_FINAL = LOGO_NUBE # Respaldo por si la carpeta assets no carga

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

# --- MOTOR DE REPORTES PDF CON LOGO ---
def generar_reporte_biocore(cliente, proyecto, df_hist, alerta_fuego, alerta_desvio):
    pdf = FPDF()
    pdf.add_page()
    
    # Franja Corporativa
    pdf.set_fill_color(*COLOR_BIOCORE)
    pdf.rect(0, 0, 210, 40, 'F')
    
    # Inserción de Logo desde assets en el PDF
    try:
        pdf.image(LOGO_FINAL, x=10, y=8, h=22)
    except: pass
    
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("helvetica", "B", 18)
    pdf.set_xy(45, 12)
    pdf.cell(0, 10, clean("BIOCORE INTELLIGENCE"), ln=1)
    pdf.set_font("helvetica", "B", 10)
    pdf.set_x(45)
    pdf.cell(0, 5, clean("SISTEMA DE AUDITORÍA Y PREVENCIÓN DE MULTAS"), ln=1)
    
    pdf.ln(25); pdf.set_text_color(0, 0, 0)
    pdf.set_font("helvetica", "B", 12); pdf.cell(0, 10, clean(f"TITULAR: {cliente}"), ln=1)
    
    # ALERTAS NASA / ESA
    if alerta_fuego:
        pdf.set_fill_color(255, 200, 200)
        pdf.set_font("helvetica", "B", 11)
        pdf.cell(0, 10, clean(" !!! ALERTA DE INCENDIO DETECTADA (NASA FIRMS) !!!"), border=1, ln=1, fill=True)
    
    if alerta_desvio:
        pdf.set_fill_color(255, 240, 150)
        pdf.set_font("helvetica", "B", 11)
        pdf.cell(0, 10, clean(" !!! RIESGO DE INCUMPLIMIENTO: Anomalía en Línea de Base !!!"), border=1, ln=1, fill=True)

    # Gráfico de Tendencia Histórica
    if not df_hist.empty:
        plt.figure(figsize=(10, 4))
        df_hist['fecha'] = pd.to_datetime(df_hist['fecha'])
        df_hist = df_hist.sort_values('fecha')
        plt.plot(df_hist['fecha'], df_hist['ndvi'], color='#143250', linewidth=1.5)
        plt.title(f"Evolución Histórica Decadal (Multisensor)")
        plt.grid(True, alpha=0.2)
        plt.savefig("grafico_reporte.png", dpi=150)
        pdf.ln(10)
        pdf.image("grafico_reporte.png", x=15, y=110, w=180)
        plt.close()

    # Firma de Directora
    pdf.set_y(250); pdf.set_font("helvetica", "B", 11)
    pdf.cell(0, 5, clean("Loreto Campos Carrasco"), align="C", ln=1)
    pdf.set_font("helvetica", "I", 10)
    pdf.cell(0, 5, clean("Directora Técnica - BioCore Intelligence"), align="C", ln=1)
    
    return pdf.output(dest='S').encode('latin-1')

# --- LÓGICA DE NEGOCIO ---
with st.sidebar:
    # Logo en la barra lateral
    st.image(LOGO_FINAL, width=180)
    st.markdown("---")
    
    if st.session_state.get('auth', False):
        st.success("🛰️ Conexión NASA/ESA Activa")
        cliente = st.text_input("Titular RCA", "Mandante_Pascua_Lama")
        tipo_p = st.selectbox("Categoría Ambiental:", ["Minería", "Humedales", "Forestal"])
        anios = st.slider("Años Históricos (NASA):", 5, 40, 20)
        input_coords = st.text_area("Coordenadas del Proyecto:")
        if st.button("Cerrar Sesión"): st.session_state.auth = False; st.rerun()
    else:
        u, p = st.text_input("Usuario"), st.text_input("Clave", type="password")
        if st.button("Entrar"):
            if u == "admin" and p == "loreto2026":
                st.session_state.auth = True; st.rerun()

if st.session_state.get('auth', False):
    st.title("Plataforma de Prevención de Multas Ambientales")
    
    if input_coords:
        try:
            data = io.StringIO(input_coords.strip())
            df_p = pd.read_csv(data, names=['lat', 'lon'])
            puntos = df_p[['lon', 'lat']].values.tolist()
            geom = ee.Geometry.Polygon(puntos)
            
            col_map, col_res = st.columns([2, 1])
            
            with col_map:
                m = folium.Map(location=[df_p['lat'].mean(), df_p['lon'].mean()], zoom_start=13)
                if conectado:
                    # Capa Sentinel-1 (Radar) para ver a través de nubes
                    s1 = ee.ImageCollection('COPERNICUS/S1_GRD').filterBounds(geom).first()
                    if s1:
                        map_id = s1.getMapId({'min': -25, 'max': 0})
                        folium.TileLayer(tiles=map_id['tile_fetcher'].url_format, attr='Radar ESA').add_to(m)
                folium.GeoJson(geom.getInfo()).add_to(m)
                st_folium(m, width="100%", height=500)
            
            with col_res:
                st.subheader("Auditoría de Blindaje")
                if st.button(f"🔍 Escaneo de {anios} Años"):
                    with st.spinner("Analizando FIRMS NASA y ESA..."):
                        # Detección de fuego 48h
                        fuego = ee.ImageCollection("FIRMS").filterBounds(geom).filterDate((datetime.now()-timedelta(days=2)).strftime('%Y-%m-%d'), datetime.now().strftime('%Y-%m-%d')).size().getInfo() > 0
                        
                        # Histórico optimizado
                        coleccion = ee.ImageCollection("LANDSAT/LC08/C02/T1_L2").filterBounds(geom).filter(ee.Filter.lt('CLOUD_COVER', 10)).limit(anios * 2)
                        datos = coleccion.map(lambda img: ee.Feature(None, {
                            'fecha': img.date().format('YYYY-MM'),
                            'ndvi': img.normalizedDifference(['SR_B5', 'SR_B4']).reduceRegion(ee.Reducer.mean(), geom, 60).get('nd')
                        })).getInfo()
                        
                        df_hist = pd.DataFrame([f['properties'] for f in datos['features'] if f['properties']['ndvi'] is not None])
                        
                        alerta_desvio = False
                        if not df_hist.empty:
                            alerta_desvio = df_hist['ndvi'].iloc[-1] < (df_hist['ndvi'].mean() * 0.7)
                        
                        pdf = generar_reporte_biocore(cliente, tipo_p, df_hist, fuego, alerta_desvio)
                        st.download_button("📥 Descargar Informe Preventivo", pdf, f"BioCore_{cliente}.pdf")
                        
                        if fuego: st.error("🔥 Fuego detectado en el perímetro.")
                        st.success("Auditoría completada exitosamente.")
        except:
            st.error("Error: Verifique el formato de las coordenadas.")
