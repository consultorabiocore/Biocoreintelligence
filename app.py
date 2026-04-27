import streamlit as st
import ee
import json
import pandas as pd
import io
import os
import base64
import requests
import matplotlib.pyplot as plt
from fpdf import FPDF
from datetime import datetime, timedelta

# --- CREDENCIALES CRÍTICAS (BOT TELEGRAM) ---
T_TOKEN = "7961684994:AAGbepFHxXJtjCVTCjEwq2xWh9vT9TO6G68"
T_ID = "6712325113"
LOGO_PATH = os.path.join("assets", "logo_biocore.png")
COLOR_BIOCORE = (20, 50, 80)

st.set_page_config(page_title="BioCore Intelligence | Reporte Diario", layout="wide")

# --- FUNCIONES DE UTILIDAD ---
def clean(text): return str(text).encode('latin-1', 'replace').decode('latin-1')

def enviar_telegram(mensaje):
    url = f"https://api.telegram.org/bot{T_TOKEN}/sendMessage"
    try: requests.post(url, data={"chat_id": T_ID, "text": mensaje, "parse_mode": "Markdown"})
    except: pass

def get_base64_logo():
    if os.path.exists(LOGO_PATH):
        with open(LOGO_PATH, "rb") as f: return base64.b64encode(f.read()).decode()
    return None

# --- MOTOR DE CÁLCULO Y CONSULTA HISTÓRICA (SIN SHEETS) ---
def generar_analisis_diario(geom, dias_atras=180):
    """Calcula el estado de hoy y recupera el historial para el gráfico del PDF"""
    fin = datetime.now()
    ini = fin - timedelta(days=dias_atras)
    
    # Colección Sentinel-2 (Lógica Droplet mejorada)
    col = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')\
        .filterBounds(geom)\
        .filterDate(ini.strftime('%Y-%m-%d'), fin.strftime('%Y-%m-%d'))\
        .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20))

    def calc_indices(img):
        # Índices técnicos BioCore
        savi = img.expression('((B8-B4)/(B8+B4+0.5))*1.5', {
            'B8': img.select('B8'), 'B4': img.select('B4')
        }).rename('savi')
        ndsi_ndwi = img.normalizedDifference(['B3', 'B11']).rename('mn') # Dual: Nieve/Agua
        swir = img.select('B11').divide(10000).rename('swir')
        
        return ee.Feature(None, {
            'fecha': img.date().format('YYYY-MM-DD'),
            'savi': savi.reduceRegion(ee.Reducer.median(), geom, 30).get('savi'),
            'mn': ndsi_ndwi.reduceRegion(ee.Reducer.median(), geom, 30).get('mn'),
            'swir': swir.reduceRegion(ee.Reducer.median(), geom, 30).get('swir')
        })

    datos = col.map(calc_indices).getInfo()
    df = pd.DataFrame([f['properties'] for f in datos['features'] if f['properties']['savi'] is not None])
    if not df.empty:
        df['fecha'] = pd.to_datetime(df['fecha'])
        df = df.sort_values('fecha')
    return df

# --- GENERADOR DE REPORTE PDF (ESTILO PROFESIONAL) ---
def crear_pdf_reporte(df, proy, sector, estado, diagnostico):
    pdf = FPDF()
    pdf.add_page()
    
    # Encabezado BioCore
    pdf.set_fill_color(*COLOR_BIOCORE)
    pdf.rect(0, 0, 210, 40, 'F')
    if os.path.exists(LOGO_PATH): pdf.image(LOGO_PATH, x=10, y=10, h=20)
    
    pdf.set_text_color(255, 255, 255); pdf.set_font("helvetica", "B", 15)
    pdf.set_xy(40, 15); pdf.cell(0, 10, clean(f"REPORTE DIARIO DE AUDITORÍA: {proy}"), ln=1)
    pdf.set_font("helvetica", "I", 9); pdf.set_xy(40, 22)
    pdf.cell(0, 10, clean("Responsable Técnica: Loreto Campos Carrasco | BioCore Intelligence"), ln=1)
    
    # Estatus y Diagnóstico
    pdf.ln(25); pdf.set_text_color(0, 0, 0)
    color_status = (200, 0, 0) if "ALERTA" in estado else (0, 100, 0)
    pdf.set_fill_color(*color_status); pdf.set_text_color(255, 255, 255)
    pdf.set_font("helvetica", "B", 11)
    pdf.cell(0, 10, clean(f"  ESTADO ACTUAL: {estado}"), ln=1, fill=True)
    
    pdf.ln(5); pdf.set_text_color(0, 0, 0); pdf.set_font("helvetica", "", 10)
    pdf.multi_cell(0, 6, clean(f"DIAGNÓSTICO TÉCNICO:\n{diagnostico}"), border=1)

    # Gráfico de Tendencia
    if not df.empty:
        plt.figure(figsize=(10, 5))
        plt.plot(df['fecha'], df['mn'], color='#1f77b4', label='NDSI/NDWI (Nieve/Agua)', marker='o')
        plt.plot(df['fecha'], df['savi'], color='#2ca02c', label='SAVI (Vigor Vegetal)', marker='s')
        plt.title(f"Evolución Histórica - {proy}")
        plt.legend(); plt.grid(True, alpha=0.3)
        plt.savefig("plot_diario.png", dpi=150)
        pdf.image("plot_diario.png", x=15, y=120, w=180)
        plt.close()

    pdf.set_y(265); pdf.set_font("helvetica", "B", 10); pdf.cell(0, 5, "Loreto Campos Carrasco", align="C", ln=1)
    return pdf.output(dest='S').encode('latin-1')

# --- INTERFAZ STREAMLIT ---
if not ee.data._credentials: # Iniciar GEE si no está
    try:
        info = json.loads(st.secrets["GEE_JSON"])
        ee.Initialize(ee.ServiceAccountCredentials(info['client_email'], key_data=info['private_key'].replace("\\n", "\n")))
    except: st.error("Error GEE")

with st.sidebar:
    logo_b64 = get_base64_logo()
    if logo_b64: st.markdown(f'<div style="text-align:center"><img src="data:image/png;base64,{logo_b64}" width="120"></div>', unsafe_allow_html=True)
    st.markdown("---")
    if st.session_state.get('auth', False):
        proy_name = st.text_input("Proyecto", "Pascua Lama")
        tipo_sec = st.selectbox("Sector:", ["Minería", "Glaciares", "Humedales"])
        coords_json = st.text_area("Polígono (Coordenadas):")
        if st.button("Log Out"): st.session_state.auth = False; st.rerun()
    else:
        u, p = st.text_input("User"), st.text_input("Pass", type="password")
        if st.button("Entrar"):
            if u == "admin" and p == "loreto2026": st.session_state.auth = True; st.rerun()

if st.session_state.get('auth', False):
    st.title("BioCore Intelligence: Generación de Reportes Diarios")
    
    if coords_json:
        try:
            geom_auditoria = ee.Geometry.Polygon(json.loads(coords_json))
            if st.button("🚀 GENERAR REPORTE COMPLETO Y NOTIFICAR"):
                with st.spinner("Escaneando satélites y construyendo histórico..."):
                    df = generar_analisis_diario(geom_auditoria)
                    
                    if not df.empty:
                        actual = df.iloc[-1]
                        # Lógica de diagnóstico legal
                        estado = "🟢 BAJO CONTROL"
                        diagnostico = "Sin variaciones anómalas respecto al historial."
                        if tipo_sec in ["Minería", "Glaciares"] and actual['mn'] < 0.35:
                            estado = "🔴 ALERTA TÉCNICA"
                            diagnostico = f"Pérdida crítica de cobertura (NDSI: {actual['mn']:.2f}). Se requiere inspección."
                        
                        # PDF y Telegram
                        pdf_reporte = crear_pdf_reporte(df, proy_name, tipo_sec, estado, diagnostico)
                        
                        msg_tel = (f"🛰 **REPORTE DIARIO BIOCORE**\n**{proy_name}**\n"
                                   f"Estatus: {estado}\nNDSI: `{actual['mn']:.2f}`\nSAVI: `{actual['savi']:.2f}`\n"
                                   f"✅ Reporte PDF generado.")
                        enviar_telegram(msg_tel)
                        
                        st.success("✅ Reporte Diario generado con éxito.")
                        st.download_button("📥 DESCARGAR REPORTE TÉCNICO (PDF)", pdf_reporte, f"BioCore_{proy_name}_{datetime.now().strftime('%Y%m%d')}.pdf")
                        st.line_chart(df.set_index('fecha')[['mn', 'savi']])
        except Exception as e: st.error(f"Error: {e}")
