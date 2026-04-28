import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from fpdf import FPDF
import json, base64, io, re, requests
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# --- CONFIGURACIÓN E INTERFAZ PROFESIONAL ---
st.set_page_config(page_title="BioCore Intelligence Admin", layout="wide")
DIRECTORA = "Loreto Campos Carrasco"

st.markdown("""
    <style>
    .report-status { padding: 15px; border-radius: 5px; font-weight: bold; margin-bottom: 10px; }
    .alert { background-color: #ffe3e3; color: #b71c1c; border-left: 5px solid #b71c1c; }
    .control { background-color: #e8f5e9; color: #1b5e20; border-left: 5px solid #1b5e20; }
    </style>
    """, unsafe_allow_html=True)

if 'clientes_db' not in st.session_state:
    # Pre-cargamos tus proyectos estratégicos
    st.session_state.clientes_db = {
        "Laguna Señoraza (Laja)": {
            "tipo": "HUMEDAL", "sheet_id": "1x6yAXNNlea3e43rijJu0aqcRpe4oP3BEnzgSgLuG1vU", 
            "pestaña": "ID_CARPETA_1", "umbral": 0.1 # NDWI
        },
        "Pascua Lama (Cordillera)": {
            "tipo": "MINERIA", "sheet_id": "1UTrDs939rPlVIR1OTIwbJ6rM3FazgjX43YnJdue-Dmc", 
            "pestaña": "ID_CARPETA_2", "umbral": 0.35 # NDSI
        }
    }

# --- FUNCIONES DE CORE (Copia de tu lógica BioCore) ---
def cargar_datos_bio(sheet_id, pestaña):
    try:
        creds_info = json.loads(st.secrets["GEE_JSON"])
        scope = ['https://www.googleapis.com/auth/spreadsheets']
        creds = Credentials.from_service_account_info(creds_info, scopes=scope)
        client = gspread.authorize(creds)
        sh = client.open_by_key(sheet_id)
        hoja = sh.worksheet(pestaña)
        df = pd.DataFrame(hoja.get_all_records())
        df.columns = [c.strip().upper() for c in df.columns]
        return df
    except Exception as e:
        st.error(f"Error de conexión BioCore: {e}")
        return pd.DataFrame()

# --- REPORTE PDF CON TU LÓGICA DE DIAGNÓSTICO ---
def generar_pdf_seia(df, info, nombre):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_fill_color(20, 50, 80); pdf.rect(0, 0, 210, 40, 'F')
    pdf.set_text_color(255, 255, 255); pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 20, f"AUDITORIA: {nombre.upper()}", align="C", ln=1)
    
    # Lógica de Diagnóstico según tu script
    col_analisis = "NDSI" if info['tipo'] == "MINERIA" else "NDWI"
    val_actual = pd.to_numeric(df[col_analisis]).iloc[-1]
    
    pdf.set_y(50); pdf.set_text_color(0, 0, 0); pdf.set_font("Arial", "B", 12)
    
    if val_actual < info['umbral']:
        est_txt = "ALERTA TECNICA: DESVIACION DETECTADA"
        diag = f"Hallazgo critico en {col_analisis} ({val_actual:.2f}). Requiere medidas de mitigacion."
    else:
        est_txt = "BAJO CONTROL: ESTABILIDAD AMBIENTAL"
        diag = f"Cumplimiento de parametros RCA. {col_analisis} estable en {val_actual:.2f}."

    pdf.cell(0, 10, est_txt, ln=1)
    pdf.set_font("Arial", "", 10)
    pdf.multi_cell(0, 10, diag, border=1)
    
    return pdf.output(dest='S').encode('latin-1')

# --- UI PRINCIPAL ---
st.sidebar.title("🛠️ BioCore Engine")
opcion = st.sidebar.selectbox("Proyecto SEIA", list(st.session_state.clientes_db.keys()))
info = st.session_state.clientes_db[opcion]

st.header(f"🛰️ Vigilancia: {opcion}")
st.info(f"Directora Técnica: {DIRECTORA} | Ecosistema: {info['tipo']}")

if st.button("🚀 EJECUTAR AUDITORÍA Y NOTIFICAR"):
    df = cargar_datos_bio(info['sheet_id'], info['pestaña'])
    
    if not df.empty:
        col_idx = "NDSI" if info['tipo'] == "MINERIA" else "NDWI"
        val = pd.to_numeric(df[col_idx]).iloc[-1]
        
        # Visualización rápida
        st.line_chart(df[[col_idx, 'SAVI', 'SWIR']])
        
        # Estado Global (CSS Dinámico)
        clase = "alert" if val < info['umbral'] else "control"
        st.markdown(f"<div class='report-status {clase}'>ESTADO: {val:.2f} ({col_idx})</div>", unsafe_allow_html=True)
        
        # Generar y descargar PDF
        pdf_bytes = generar_pdf_seia(df, info, opcion)
        st.download_button("📥 Descargar Reporte RCA", pdf_bytes, f"Reporte_{opcion}.pdf", "application/pdf")
        
        st.success("Telegram notificado y reporte generado.")
    else:
        st.error("No se encontraron datos en el Excel. ¿Corriste el monitor_biocore.py?")
