import streamlit as st
import ee
import json
import pandas as pd
import os
import base64
import requests
import matplotlib.pyplot as plt
from fpdf import FPDF
from datetime import datetime, timedelta

# --- CONFIGURACIÓN DE BIOCORE ---
T_TOKEN = "7961684994:AAGbepFHxXJtjCVTCjEwq2xWh9vT9TO6G68"
T_ID = "6712325113"
LOGO_PATH = os.path.join("assets", "logo_biocore.png")
COLOR_BIOCORE = (20, 50, 80)

st.set_page_config(page_title="BioCore Intelligence | Reporte Diario", layout="wide")

# --- AUTENTICACIÓN SEGURA DE GEE ---
def inicializar_gee():
    """Inicializa GEE de forma segura para Streamlit"""
    try:
        if 'gee_auth' not in st.session_state:
            info = json.loads(st.secrets["GEE_JSON"])
            creds = ee.ServiceAccountCredentials(info['client_email'], key_data=info['private_key'].replace("\\n", "\n"))
            ee.Initialize(creds)
            st.session_state.gee_auth = True
        return True
    except Exception as e:
        st.error(f"Error de autenticación GEE: {e}")
        return False

# --- FUNCIONES TÉCNICAS ---
def clean(text): return str(text).encode('latin-1', 'replace').decode('latin-1')

def enviar_telegram(mensaje):
    url = f"https://api.telegram.org/bot{T_TOKEN}/sendMessage"
    try: requests.post(url, data={"chat_id": T_ID, "text": mensaje, "parse_mode": "Markdown"})
    except: pass

# --- MOTOR DE CÁLCULO (Sustituye al Droplet) ---
def obtener_data_diaria(geom, sector):
    # Escaneamos los últimos 6 meses para dar contexto al reporte
    fin = datetime.now()
    ini = fin - timedelta(days=180)
    
    col = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')\
        .filterBounds(geom)\
        .filterDate(ini.strftime('%Y-%m-%d'), fin.strftime('%Y-%m-%d'))\
        .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20))

    def procesar(img):
        # Lógica de índices BioCore (SAVI, NDSI, SWIR)
        savi = img.expression('((B8-B4)/(B8+B4+0.5))*1.5', {
            'B8': img.select('B8'), 'B4': img.select('B4')
        }).rename('savi')
        # MN es el índice dual para Nieve/Agua (B3 y B11)
        mn = img.normalizedDifference(['B3', 'B11']).rename('mn')
        swir = img.select('B11').divide(10000).rename('swir')
        
        return ee.Feature(None, {
            'fecha': img.date().format('YYYY-MM-DD'),
            'savi': savi.reduceRegion(ee.Reducer.median(), geom, 30).get('savi'),
            'mn': mn.reduceRegion(ee.Reducer.median(), geom, 30).get('mn'),
            'swir': swir.reduceRegion(ee.Reducer.median(), geom, 30).get('swir')
        })

    datos = col.map(procesar).getInfo()
    df = pd.DataFrame([f['properties'] for f in datos['features'] if f['properties']['savi'] is not None])
    if not df.empty:
        df['fecha'] = pd.to_datetime(df['fecha'])
        df = df.sort_values('fecha')
    return df

# --- GENERADOR DE PDF ---
def generar_pdf_diario(df, proy, sector, estado, diag):
    pdf = FPDF()
    pdf.add_page()
    
    # Encabezado estilo BioCore
    pdf.set_fill_color(*COLOR_BIOCORE)
    pdf.rect(0, 0, 210, 40, 'F')
    if os.path.exists(LOGO_PATH): pdf.image(LOGO_PATH, x=10, y=10, h=20)
    
    pdf.set_text_color(255, 255, 255); pdf.set_font("helvetica", "B", 15)
    pdf.set_xy(45, 15); pdf.cell(0, 10, clean(f"REPORTE DIARIO: {proy.upper()}"), ln=1)
    
    # Diagnóstico y Estado
    pdf.ln(25); pdf.set_text_color(0, 0, 0)
    color_bg = (200, 0, 0) if "ALERTA" in estado else (0, 100, 0)
    pdf.set_fill_color(*color_bg); pdf.set_text_color(255, 255, 255)
    pdf.set_font("helvetica", "B", 11)
    pdf.cell(0, 10, clean(f"  ESTADO: {estado}"), ln=1, fill=True)
    
    pdf.ln(5); pdf.set_text_color(0, 0, 0); pdf.set_font("helvetica", "", 10)
    pdf.multi_cell(0, 7, clean(f"DIAGNÓSTICO BIOCORE:\n{diag}"), border=1)

    # Gráfico de tendencia histórica (Extraído de GEE)
    if not df.empty:
        plt.figure(figsize=(10, 4))
        plt.plot(df['fecha'], df['mn'], color='#2980b9', label='Índice Criósfera/Hídrico', marker='o')
        plt.grid(True, alpha=0.3); plt.legend()
        plt.savefig("temp_plot.png", dpi=150)
        pdf.image("temp_plot.png", x=15, y=110, w=180)
        plt.close()

    pdf.set_y(260); pdf.set_font("helvetica", "B", 10); pdf.cell(0, 5, "Loreto Campos Carrasco", align="C", ln=1)
    return pdf.output(dest='S').encode('latin-1')

# --- INTERFAZ PRINCIPAL ---
if inicializar_gee():
    with st.sidebar:
        if os.path.exists(LOGO_PATH):
            with open(LOGO_PATH, "rb") as f:
                st.markdown(f'<div style="text-align:center"><img src="data:image/png;base64,{base64.b64encode(f.read()).decode()}" width="120"></div>', unsafe_allow_html=True)
        st.markdown("---")
        if st.session_state.get('auth', False):
            proy = st.text_input("Nombre Proyecto", "Pascua Lama")
            sec = st.selectbox("Sector", ["Minería", "Humedales", "Glaciares"])
            coords = st.text_area("Coordenadas (JSON)")
            if st.button("Cerrar Sesión"): st.session_state.auth = False; st.rerun()
        else:
            u, p = st.text_input("Usuario"), st.text_input("Clave", type="password")
            if st.button("Entrar"):
                if u == "admin" and p == "loreto2026": st.session_state.auth = True; st.rerun()

    if st.session_state.get('auth', False):
        st.title(f"BioCore Intelligence: Auditoría {proy}")
        
        if coords:
            try:
                geom = ee.Geometry.Polygon(json.loads(coords))
                if st.button("🚀 GENERAR REPORTE DIARIO"):
                    with st.spinner("Escaneando satélites..."):
                        df = obtener_data_diaria(geom, sec)
                        if not df.empty:
                            actual = df.iloc[-1]
                            estado = "🟢 BAJO CONTROL"
                            diag = "Sin anomalías detectadas en el polígono."
                            
                            if (sec in ["Minería", "Glaciares"]) and actual['mn'] < 0.35:
                                estado = "🔴 ALERTA TÉCNICA"
                                diag = f"Pérdida de masa criosférica detectada (Valor: {actual['mn']:.2f})."
                            
                            # Procesos de salida
                            pdf_bytes = generar_pdf_diario(df, proy, sec, estado, diag)
                            enviar_telegram(f"🛰 **BIOCORE DIARIO**\nProyecto: {proy}\nEstado: {estado}\nNDSI: `{actual['mn']:.2f}`")
                            
                            st.success("✅ Reporte generado y aviso enviado.")
                            st.download_button("📥 Descargar Reporte PDF", pdf_bytes, f"BioCore_{proy}.pdf")
                            st.line_chart(df.set_index('fecha')[['mn', 'savi']])
            except Exception as e: st.error(f"Error: {e}")
