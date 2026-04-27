import streamlit as st
import ee
import json
import folium
import pandas as pd
import io
import matplotlib.pyplot as plt
from streamlit_folium import st_folium
from fpdf import FPDF
from datetime import datetime, timedelta

# --- CONFIGURACIÓN DE MARCA ---
LOGO_URL = "https://cdn-icons-png.flaticon.com/512/2092/2092031.png" 
COLOR_BIOCORE = (20, 50, 80)
COLOR_PELIGRO = (255, 0, 0)

st.set_page_config(page_title="BioCore Intelligence v2.0", layout="wide")

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

# --- MOTOR DE ALERTAS TEMPRANAS (NASA FIRMS) ---
def detectar_fuego_reciente(geom):
    """Detecta anomalías térmicas en las últimas 48 horas (NASA FIRMS)"""
    hoy = datetime.now()
    hace_2_dias = hoy - timedelta(days=2)
    fuego = ee.ImageCollection("FIRMS").filterBounds(geom).filterDate(hace_2_dias.strftime('%Y-%m-%d'), hoy.strftime('%Y-%m-%d'))
    return fuego.size().getInfo() > 0

# --- MOTOR DE RADAR (SENTINEL-1) ---
def obtener_radar_sar(geom):
    """Detecta cambios en el terreno mediante Radar (Atraviesa nubes)"""
    s1 = ee.ImageCollection('COPERNICUS/S1_GRD') \
        .filterBounds(geom) \
        .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV')) \
        .sort('system:time_start', False).first()
    return s1

# --- GENERADOR DE INFORME ESTRATÉGICO ---
def generar_reporte_proactivo(cliente, proyecto, df_hist, alerta_fuego, alerta_desvio):
    pdf = FPDF()
    pdf.add_page()
    
    # Cabecera de Poder
    pdf.set_fill_color(*COLOR_BIOCORE)
    pdf.rect(0, 0, 210, 45, 'F')
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("helvetica", "B", 16)
    pdf.cell(0, 15, clean("BIOCORE INTELLIGENCE - AUDITORÍA PREVENTIVA"), align="C", ln=1)
    pdf.set_font("helvetica", "B", 10)
    pdf.cell(0, 5, clean(f"SISTEMA DE ALERTA TEMPRANA MULTI-CONSTELACIÓN (ESA / NASA)"), align="C", ln=1)
    
    pdf.ln(30); pdf.set_text_color(0, 0, 0)
    pdf.set_font("helvetica", "B", 12); pdf.cell(0, 10, clean(f"CLIENTE: {cliente} | ESTATUS DE RIESGO:"), ln=1)
    
    # CUADRO DE ALERTAS PREVENTIVAS
    pdf.set_font("helvetica", "B", 10)
    if alerta_fuego:
        pdf.set_fill_color(255, 200, 200); pdf.cell(0, 10, clean(" 🚨 ALERTA DE INCENDIO: Anomalía térmica detectada por NASA FIRMS."), border=1, ln=1, fill=True)
    if alerta_desvio:
        pdf.set_fill_color(255, 230, 150); pdf.cell(0, 10, clean(" ⚠️ ALERTA DE CUMPLIMIENTO: El índice actual rompió la línea de base histórica."), border=1, ln=1, fill=True)
    if not alerta_fuego and not alerta_desvio:
        pdf.set_fill_color(200, 255, 200); pdf.cell(0, 10, clean(" ✅ ÁREA SEGURA: No se detectan anomalías en el perímetro."), border=1, ln=1, fill=True)

    # Metodología de Fusión
    pdf.ln(5); pdf.set_font("helvetica", "B", 10); pdf.cell(0, 7, clean("METODOLOGÍA DE PROTECCIÓN LEGAL:"), ln=1)
    pdf.set_font("helvetica", "", 9)
    pdf.multi_cell(0, 5, clean("Utilizamos Sentinel-1 (Radar) para monitoreo bajo nubosidad, Sentinel-2 para salud vegetal, "
                               "y NASA Landsat para la reconstrucción histórica decadal. Las alertas térmicas se "
                               "sincronizan con el sistema de respuesta temprana para prevenir multas por daño irreversible."))

    # Gráfico Histórico
    plt.figure(figsize=(10, 4))
    df_hist['fecha'] = pd.to_datetime(df_hist['fecha'])
    plt.plot(df_hist['fecha'], df_hist['ndvi'], color='#143250', linewidth=1.5)
    plt.title("Análisis Retrospectivo Decadal (NASA/ESA)")
    plt.savefig("hist_final.png", dpi=150)
    pdf.image("hist_final.png", x=15, y=120, w=180)
    
    pdf.set_y(250); pdf.set_font("helvetica", "B", 11); pdf.cell(0, 5, clean("Loreto Campos Carrasco"), align="C", ln=1)
    pdf.set_font("helvetica", "I", 10); pdf.cell(0, 5, clean("Directora Técnica - BioCore Intelligence"), align="C", ln=1)
    
    return pdf.output(dest='S').encode('latin-1')

# --- INTERFAZ ---
with st.sidebar:
    st.image(LOGO_URL, width=100)
    if st.session_state.get('auth', False):
        st.success("🛰️ Fusión NASA/ESA Activa")
        cliente = st.text_input("Titular", "Mandante_RCA")
        tipo_p = st.selectbox("Categoría:", ["Minería", "Humedales", "Forestal", "Energía"])
        
        # EL SELECTOR SOLICITADO
        rango_anios = st.slider("Selector de Línea de Base (Años):", 5, 40, 20)
        
        input_coords = st.text_area("Coordenadas del Proyecto:")
        
        if st.button("Salir"): st.session_state.auth = False; st.rerun()
    else:
        u, p = st.text_input("User"), st.text_input("Pass", type="password")
        if st.button("Acceder"): 
            if u == "admin" and p == "loreto2026": st.session_state.auth = True; st.rerun()

if st.session_state.get('auth', False):
    st.title("BioCore Intelligence: Plataforma Proactiva de Riesgos")
    
    if input_coords:
        try:
            data = io.StringIO(input_coords.strip()); df_p = pd.read_csv(data, names=['lat', 'lon'])
            geom = ee.Geometry.Polygon(df_p[['lon', 'lat']].values.tolist())
            
            col_m, col_r = st.columns([2, 1])
            with col_m:
                m = folium.Map(location=[df_p['lat'].mean(), df_p['lon'].mean()], zoom_start=13)
                if conectado:
                    # Visualización Radar (S1) por defecto para demostrar poder
                    s1_img = obtener_radar_sar(geom)
                    map_id = s1_img.getMapId({'min': -25, 'max': 0})
                    folium.TileLayer(tiles=map_id['tile_fetcher'].url_format, attr='ESA S1', name='Radar SAR').add_to(m)
                folium.GeoJson(geom.getInfo()).add_to(m)
                st_folium(m, width="100%", height=500)
            
            with col_r:
                st.subheader("Auditoría en Tiempo Real")
                if st.button(f"🔍 Escaneo Decadal ({rango_anios} años)"):
                    with st.spinner("Consultando NASA FIRMS y Fusión ESA..."):
                        # Detección de Fuego (Preventiva)
                        fuego_activo = detectar_fuego_reciente(geom)
                        if fuego_activo: st.error("🔥 PELIGRO: Fuego detectado en el perímetro.")
                        
                        # Histórico Largo con Selector
                        df_hist = obtener_historico_profundo(geom, rango_anios) # Usa la función anterior
                        
                        alerta_desvio = df_hist['ndvi'].iloc[-1] < (df_hist['ndvi'].mean() * 0.75)
                        
                        pdf = generar_reporte_proactivo(cliente, tipo_p, df_hist, fuego_activo, alerta_desvio)
                        st.download_button("📥 Descargar Reporte de Blindaje", pdf, f"BioCore_Alerta_{cliente}.pdf")
                        st.info("Escaneo completado. Radar SAR y Térmico NASA sincronizados.")
        except: st.error("Error en datos.")
