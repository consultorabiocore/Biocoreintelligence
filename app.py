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

# --- BASE DE DATOS DE SESIÓN ---
if 'suscripciones' not in st.session_state:
    st.session_state.suscripciones = [
        {
            "ID": "BC-001", 
            "PROYECTO": "Pascua Lama", 
            "TITULAR": "Loreto Campos Carrasco", 
            "CHAT_ID": "6712325113", 
            "MODALIDAD": "Diario",
            "COORDENADAS": "-29.3177, -70.0191\n-29.3300, -70.0100\n-29.3400, -70.0300",
            "REGISTRO": "Activo"
        }
    ]

# --- FUNCIÓN GENERAR PDF CON GRÁFICOS TÉCNICOS ---
def generar_pdf_profesional(data_p, coordenadas):
    pdf = FPDF()
    pdf.add_page()
    
    # Encabezado
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(200, 10, "INFORME DE AUDITORÍA SATELITAL - BIOCORE", ln=True, align='C')
    pdf.set_font("Arial", 'I', 9)
    pdf.cell(200, 10, f"ID Reporte: {datetime.now().strftime('%Y%m%d%H%M')}", ln=True, align='C')
    pdf.ln(5)
    
    # Bloque 1: Ficha Técnica
    pdf.set_fill_color(44, 62, 80)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, " 1. IDENTIFICACIÓN DEL PROYECTO", ln=True, fill=True)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", '', 11)
    pdf.cell(0, 8, f"Titular Responsable: {data_p['TITULAR']}", ln=True)
    pdf.cell(0, 8, f"Proyecto: {data_p['PROYECTO']} (ID: {data_p['ID']})", ln=True)
    pdf.cell(0, 8, f"Régimen Contratado: {data_p['MODALIDAD']}", ln=True)
    pdf.ln(5)

    # Bloque 2: Gráficos de Índices (Simulados con Estructura de Datos)
    pdf.set_fill_color(44, 62, 80)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 10, " 2. ANÁLISIS COMPARATIVO DE ÍNDICES AMBIENTALES", ln=True, fill=True)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(2)
    
    # Tabla representativa de Gráfico de Tendencias
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(45, 8, "Fecha", 1, 0, 'C')
    pdf.cell(45, 8, "NDVI (Vigencia)", 1, 0, 'C')
    pdf.cell(45, 8, "NDWI (Agua)", 1, 0, 'C')
    pdf.cell(45, 8, "Estatus", 1, 1, 'C')
    
    pdf.set_font("Arial", '', 10)
    # Datos de ejemplo para el reporte
    analisis = [
        ("Marzo 2026", "0.68", "0.12", "Estable"),
        ("Abril 2026", "0.65", "0.11", "Normal"),
        ("Hoy", "0.67", "0.12", "Óptimo")
    ]
    for f, v, a, e in analisis:
        pdf.cell(45, 8, f, 1)
        pdf.cell(45, 8, v, 1)
        pdf.cell(45, 8, a, 1)
        pdf.cell(45, 8, e, 1, 1)

    pdf.ln(10)
    # Bloque 3: Coordenadas
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(0, 10, "GEOMETRÍA DEL ÁREA DE FISCALIZACIÓN:", ln=True)
    pdf.set_font("Courier", '', 8)
    pdf.multi_cell(0, 5, coordenadas)

    fn = f"Reporte_BioCore_{data_p['ID']}.pdf"
    pdf.output(fn)
    return fn

# --- INICIALIZAR GEE ---
def inicializar_gee():
    try:
        if 'gee_auth' not in st.session_state:
            info = json.loads(st.secrets["GEE_JSON"])
            ee.Initialize(ee.ServiceAccountCredentials(info['client_email'], key_data=info['private_key'].replace("\\n", "\n")))
            st.session_state.gee_auth = True
        return True
    except: return False

def procesar_coords(texto):
    # Extrae números del texto limpiando cualquier carácter raro
    nums = re.findall(r"[-+]?\d*\.\d+|\d+", texto)
    coords = []
    for i in range(0, len(nums), 2):
        if i+1 < len(nums):
            # Formato GEE: [Longitud, Latitud]
            coords.append([float(nums[1]), float(nums[0])])
    # Cerrar polígono
    if coords and coords[0] != coords[-1]:
        coords.append(coords[0])
    return coords

# --- INTERFAZ ---
with st.sidebar:
    if os.path.exists(LOGO_PATH):
        with open(LOGO_PATH, "rb") as f:
            st.markdown(f'<div style="text-align:center"><img src="data:image/png;base64,{base64.b64encode(f.read()).decode()}" width="180"></div>', unsafe_allow_html=True)
    menu = st.radio("Módulo Principal:", ["🛰️ Monitor de Auditoría", "👤 Gestión de Clientes"])

if inicializar_gee():

    if menu == "👤 Gestión de Clientes":
        st.header("Directorio de Suscriptores")
        st.dataframe(pd.DataFrame(st.session_state.suscripciones), use_container_width=True, hide_index=True)
        
        with st.form("registro_new"):
            st.subheader("Vincular Nuevo Titular")
            c1, c2 = st.columns(2)
            with c1:
                p_nom = st.text_input("Nombre del Proyecto")
                p_tit = st.text_input("Titular Responsable")
            with c2:
                p_cid = st.text_input("Chat ID Telegram")
                p_mod = st.selectbox("Frecuencia de Reporte", ["Diario", "Semanal", "Mensual"])
            if st.form_submit_button("Guardar en Sistema"):
                st.session_state.suscripciones.append({
                    "ID": f"BC-{len(st.session_state.suscripciones)+1:03}",
                    "PROYECTO": p_nom, "TITULAR": p_tit, "CHAT_ID": p_cid, 
                    "MODALIDAD": p_mod, "COORDENADAS": "", "REGISTRO": "Activo"
                })
                st.rerun()

    else:
        # PANTALLA MONITOR
        nombres = [s['PROYECTO'] for s in st.session_state.suscripciones]
        sel = st.selectbox("Seleccione Proyecto Activo:", nombres)
        
        idx = next(i for i, s in enumerate(st.session_state.suscripciones) if s['PROYECTO'] == sel)
        data = st.session_state.suscripciones[idx]
        
        st.title(f"Centro de Mando: {sel}")
        c1, c2 = st.columns([1, 2])
        
        with c1:
            st.info(f"**Titular:** {data['TITULAR']} | **ID:** {data['ID']}")
            
            # Entrada de coordenadas (recuerda lo que ya estaba guardado)
            txt_coords = st.text_area("Coordenadas de Auditoría:", value=data['COORDENADAS'], height=200)
            
            cb1, cb2 = st.columns(2)
            with cb1:
                if st.button("💾 Guardar Datos"):
                    st.session_state.suscripciones[idx]['COORDENADAS'] = txt_coords
                    st.toast("Base de datos actualizada.", icon="💾")
            
            with cb2:
                puntos = procesar_coords(txt_coords) if txt_coords else []
                geom = None
                if len(puntos) > 2:
                    try:
                        geom = ee.Geometry.Polygon(puntos)
                    except: st.error("Formato inválido.")
                
                if geom and st.button("📄 Enviar Informe PDF"):
                    with st.spinner("Procesando histórico..."):
                        archivo = generar_pdf_profesional(data, txt_coords)
                        url = f"https://api.telegram.org/bot{T_TOKEN}/sendDocument"
                        with open(archivo, "rb") as f:
                            requests.post(url, data={"chat_id": data['CHAT_ID']}, files={"document": f})
                        st.toast("Reporte enviado.", icon="🚀")
                        os.remove(archivo)

        with c2:
            # MAPA REPARADO
            m = folium.Map(location=[-37, -72], zoom_start=5)
            # Solo si hay geometría válida intentamos centrar y dibujar
            if geom:
                try:
                    # GEE devuelve [Lon, Lat], Folium requiere [Lat, Lon]
                    lat_center = puntos[0][1]
                    lon_center = puntos[0][0]
                    m = folium.Map(location=[lat_center, lon_center], zoom_start=14)
                    
                    # Capa Satélite
                    folium.TileLayer('https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}', 
                                     attr='Google', name='Satélite').add_to(m)
                    
                    # Dibujar polígono asegurando que Folium lea bien el JSON de GEE
                    folium.GeoJson(
                        data=geom.getInfo(), 
                        style_function=lambda x: {'color': '#00ffcc', 'weight': 3, 'fillOpacity': 0.1}
                    ).add_to(m)
                except:
                    st.warning("Ajustando visualización de coordenadas...")

            else:
                folium.TileLayer('https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}', 
                                 attr='Google', name='Satélite').add_to(m)
            
            st_folium(m, width="100%", height=500, key=f"map_{sel}")
