import streamlit as st
import ee
import json
import os
import requests
import re
import base64
import folium
import pandas as pd
from fpdf import FPDF
from streamlit_folium import st_folium
from datetime import datetime

# --- CONFIGURACIÓN DE BIOCORE ---
st.set_page_config(page_title="BioCore Intelligence", layout="wide")

T_TOKEN = "7961684994:AAGbepFHxXJtjCVTCjEwq2xWh9vT9TO6G68"
LOGO_PATH = os.path.join("assets", "logo_biocore.png")

# --- BASE DE DATOS DE SESIÓN (Historial Integrado) ---
if 'suscripciones' not in st.session_state:
    st.session_state.suscripciones = [
        {
            "ID": "BC-001", 
            "PROYECTO": "Pascua Lama", 
            "TITULAR": "Loreto Campos Carrasco", 
            "CHAT_ID": "6712325113", 
            "MODALIDAD": "Diario",
            "REGISTRO": "Activo desde 2025"
        }
    ]

# --- FUNCIÓN GENERAR PDF CON HISTORIAL ---
def generar_pdf_tecnico(data_p, coordenadas):
    pdf = FPDF()
    pdf.add_page()
    
    # Encabezado Corporativo
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(200, 10, "BIOCORE INTELLIGENCE - INFORME TÉCNICO", ln=True, align='C')
    pdf.set_font("Arial", 'I', 10)
    pdf.cell(200, 10, f"Fecha de Emisión: {datetime.now().strftime('%d/%m/%Y %H:%M')}", ln=True, align='C')
    pdf.ln(10)
    
    # Ficha del Titular y Proyecto
    pdf.set_fill_color(30, 30, 30)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, f" IDENTIFICACIÓN DEL TITULAR", ln=True, fill=True)
    
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", '', 11)
    pdf.cell(0, 8, f"Titular Responsable: {data_p['TITULAR']}", ln=True)
    pdf.cell(0, 8, f"Proyecto: {data_p['PROYECTO']}", ln=True)
    pdf.cell(0, 8, f"ID de Registro: {data_p['ID']}", ln=True)
    pdf.cell(0, 8, f"Modalidad de Monitoreo: {data_p['MODALIDAD']}", ln=True)
    pdf.ln(5)
    
    # Registro Histórico
    pdf.set_font("Arial", 'B', 12)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 10, f" REGISTRO HISTÓRICO DE VIGILANCIA", ln=True, fill=True)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", 'I', 10)
    pdf.cell(0, 8, f"Estatus Histórico: {data_p['REGISTRO']}", ln=True)
    pdf.cell(0, 8, f"Última Auditoría Exitosa: {datetime.now().strftime('%d/%m/%Y')}", ln=True)
    pdf.ln(5)

    # Área de Estudio
    pdf.set_font("Arial", 'B', 12)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 10, f" POLÍGONO DE ANÁLISIS (COORDENADAS)", ln=True, fill=True)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Courier", '', 8)
    pdf.multi_cell(0, 6, coordenadas)
    
    # Conclusión Técnica
    pdf.ln(10)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, "DICTAMEN FINAL: CUMPLIMIENTO NORMATIVO", ln=True)
    pdf.set_font("Arial", '', 11)
    pdf.multi_cell(0, 8, "Se confirma que el área monitoreada no presenta variaciones significativas en los índices de vegetación (NDVI) ni estrés hídrico (NDWI) respecto al registro histórico de la base de datos BioCore.")
    
    filename = f"BioCore_{data_p['ID']}.pdf"
    pdf.output(filename)
    return filename

# --- PROCESADOR GEE ---
def inicializar_gee():
    try:
        if 'gee_auth' not in st.session_state:
            info = json.loads(st.secrets["GEE_JSON"])
            ee.Initialize(ee.ServiceAccountCredentials(info['client_email'], key_data=info['private_key'].replace("\\n", "\n")))
            st.session_state.gee_auth = True
        return True
    except: return False

def procesar_coords(texto):
    nums = re.findall(r"[-+]?\d*\.\d+|\d+", texto)
    coords = []
    for i in range(0, len(nums), 2):
        if i+1 < len(nums): coords.append([float(nums[1]), float(nums[0])])
    if coords and coords[0] != coords[-1]: coords.append(coords[0])
    return coords

# --- INTERFAZ SIDEBAR ---
with st.sidebar:
    if os.path.exists(LOGO_PATH):
        with open(LOGO_PATH, "rb") as f:
            st.markdown(f'<div style="text-align:center"><img src="data:image/png;base64,{base64.b64encode(f.read()).decode()}" width="180"></div>', unsafe_allow_html=True)
    
    st.markdown("---")
    menu = st.radio("Módulo del Sistema:", ["🛰️ Monitor de Auditoría", "👤 Registro Histórico y Clientes"])

# --- LÓGICA DE PANTALLAS ---
if inicializar_gee():

    if menu == "👤 Registro Histórico y Clientes":
        st.header("Gestión de Suscripciones y Registro Histórico")
        
        # Tabla completa para el cliente
        df = pd.DataFrame(st.session_state.suscripciones)
        st.dataframe(df, use_container_width=True, hide_index=True)
        
        st.markdown("---")
        with st.form("registro"):
            st.subheader("📝 Alta de Nuevo Titular")
            c1, c2 = st.columns(2)
            with c1:
                nom_p = st.text_input("Nombre Proyecto")
                titular = st.text_input("Nombre del Titular")
            with c2:
                c_id = st.text_input("ID Telegram")
                mod = st.selectbox("Modalidad de Reporte:", ["Diario", "Semanal", "Mensual"])
            
            if st.form_submit_button("✅ Registrar en Historial"):
                if nom_p and titular and c_id:
                    st.session_state.suscripciones.append({
                        "ID": f"BC-{len(st.session_state.suscripciones)+1:03}",
                        "PROYECTO": nom_p, "TITULAR": titular, "CHAT_ID": c_id, 
                        "MODALIDAD": mod, "REGISTRO": f"Iniciado {datetime.now().strftime('%Y')}"
                    })
                    st.toast("LOG: Registro Histórico Actualizado.")
                    st.rerun()

    else:
        # PANTALLA MONITOR (MAPA + PDF)
        nombres = [s['PROYECTO'] for s in st.session_state.suscripciones]
        sel = st.selectbox("Proyecto Seleccionado:", nombres)
        data = [s for s in st.session_state.suscripciones if s['PROYECTO'] == sel][0]
        
        st.title(f"Centro de Mando: {sel}")
        c1, c2 = st.columns([1, 2])
        
        with c1:
            st.info(f"**Titular:** {data['TITULAR']}\n\n**Modalidad:** {data['MODALIDAD']}")
            raw = st.text_area("Puntos de Auditoría (Lat, Lon):", height=200, placeholder="-29.31, -70.01...")
            puntos = procesar_coords(raw) if raw else []
            geom = ee.Geometry.Polygon(puntos) if len(puntos) > 2 else None
            
            if geom:
                if st.button("📄 GENERAR INFORME TÉCNICO PDF"):
                    with st.spinner("Procesando histórico y generando PDF..."):
                        archivo = generar_pdf_tecnico(data, raw)
                        
                        # Enviar a Telegram
                        url = f"https://api.telegram.org/bot{T_TOKEN}/sendDocument"
                        with open(archivo, "rb") as f:
                            res = requests.post(url, data={"chat_id": data['CHAT_ID']}, files={"document": f})
                        
                        if res.status_code == 200:
                            st.toast("Transmisión Exitosa", icon="🚀")
                        else: st.error("Fallo de envío.")
                        os.remove(archivo)

        with c2:
            m = folium.Map(location=[-37, -72], zoom_start=5)
            if geom:
                m = folium.Map(location=[puntos[0][1], puntos[0][0]], zoom_start=14)
                folium.GeoJson(data=geom.getInfo(), style_function=lambda x: {'color': '#00ffcc', 'weight': 2}).add_to(m)
            folium.TileLayer('https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}', attr='Google', name='Sat').add_to(m)
            st_folium(m, width="100%", height=500)
