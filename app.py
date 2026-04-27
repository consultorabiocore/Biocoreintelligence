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

# --- BASE DE DATOS DE SESIÓN (Ahora guarda coordenadas por cliente) ---
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

# --- FUNCIÓN GENERAR PDF CON DATOS TÉCNICOS ---
def generar_pdf_avanzado(data_p, coordenadas):
    pdf = FPDF()
    pdf.add_page()
    
    # Encabezado con Estética de Auditoría
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(200, 10, "BIOCORE: INFORME DE FISCALIZACIÓN AMBIENTAL", ln=True, align='C')
    pdf.set_font("Arial", 'I', 10)
    pdf.cell(200, 10, f"Reporte técnico emitido el: {datetime.now().strftime('%d/%m/%Y')}", ln=True, align='C')
    pdf.ln(10)
    
    # 1. FICHA TÉCNICA
    pdf.set_fill_color(33, 37, 41)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, " 1. DATOS DEL TITULAR Y PROYECTO", ln=True, fill=True)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", '', 11)
    pdf.cell(0, 8, f"Titular Responsable: {data_p['TITULAR']}", ln=True)
    pdf.cell(0, 8, f"Proyecto ID: {data_p['ID']} | Nombre: {data_p['PROYECTO']}", ln=True)
    pdf.cell(0, 8, f"Régimen de Monitoreo: {data_p['MODALIDAD']}", ln=True)
    pdf.ln(5)

    # 2. ANÁLISIS HISTÓRICO (Simulación de Gráfico mediante Tabla)
    pdf.set_fill_color(33, 37, 41)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 10, " 2. ANÁLISIS DE ÍNDICES SATELITALES (RETROSPECTIVO)", ln=True, fill=True)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", 'B', 10)
    pdf.ln(2)
    pdf.cell(60, 8, "Período (Mes)", 1, 0, 'C')
    pdf.cell(60, 8, "Promedio NDVI", 1, 0, 'C')
    pdf.cell(60, 8, "Variación %", 1, 1, 'C')
    
    pdf.set_font("Arial", '', 10)
    # Datos que luego vendrán de GEE
    meses = [("Marzo 2026", "0.68", "+2.1%"), ("Abril 2026", "0.65", "-0.4%")]
    for m, v, d in meses:
        pdf.cell(60, 8, m, 1)
        pdf.cell(60, 8, v, 1)
        pdf.cell(60, 8, d, 1, 1)
    
    pdf.ln(10)
    # 3. POLÍGONO
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(0, 10, "COORDENADAS GEORREFERENCIADAS DEL ÁREA:", ln=True)
    pdf.set_font("Courier", '', 8)
    pdf.multi_cell(0, 5, coordenadas)

    filename = f"BioCore_{data_p['ID']}_Report.pdf"
    pdf.output(filename)
    return filename

# --- PROCESADORES ---
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

# --- INTERFAZ ---
with st.sidebar:
    if os.path.exists(LOGO_PATH):
        with open(LOGO_PATH, "rb") as f:
            st.markdown(f'<div style="text-align:center"><img src="data:image/png;base64,{base64.b64encode(f.read()).decode()}" width="180"></div>', unsafe_allow_html=True)
    menu = st.radio("Módulo:", ["🛰️ Monitor de Auditoría", "👤 Gestión de Clientes"])

if inicializar_gee():

    if menu == "👤 Gestión de Clientes":
        st.header("Directorio de Proyectos")
        st.dataframe(pd.DataFrame(st.session_state.suscripciones), use_container_width=True, hide_index=True)
        
        with st.form("new_reg"):
            st.subheader("Registrar Nuevo Titular")
            c1, c2 = st.columns(2)
            with c1:
                p_nom = st.text_input("Proyecto")
                p_tit = st.text_input("Titular")
            with c2:
                p_cid = st.text_input("Chat ID Telegram")
                p_mod = st.selectbox("Modalidad", ["Diario", "Semanal", "Mensual"])
            if st.form_submit_button("Guardar en Base de Datos"):
                st.session_state.suscripciones.append({
                    "ID": f"BC-{len(st.session_state.suscripciones)+1:03}",
                    "PROYECTO": p_nom, "TITULAR": p_tit, "CHAT_ID": p_cid, 
                    "MODALIDAD": p_mod, "COORDENADAS": "", "REGISTRO": "Activo"
                })
                st.rerun()

    else:
        # PANTALLA MONITOR CON GUARDADO DE COORDENADAS
        proyectos = [s['PROYECTO'] for s in st.session_state.suscripciones]
        sel = st.selectbox("Seleccione Proyecto a Monitorear:", proyectos)
        
        # Obtener el índice para guardar cambios
        idx = next(i for i, s in enumerate(st.session_state.suscripciones) if s['PROYECTO'] == sel)
        data = st.session_state.suscripciones[idx]
        
        st.title(f"Centro de Mando: {sel}")
        c1, c2 = st.columns([1, 2])
        
        with c1:
            st.markdown(f"**Titular Responsable:** {data['TITULAR']}")
            
            # --- GUARDADO DINÁMICO DE COORDENADAS ---
            # El valor por defecto es lo que ya está guardado para ese cliente
            txt_coords = st.text_area("Coordenadas del Proyecto:", value=data['COORDENADAS'], height=200)
            
            col_save, col_pdf = st.columns(2)
            with col_save:
                if st.button("💾 Guardar Coords"):
                    st.session_state.suscripciones[idx]['COORDENADAS'] = txt_coords
                    st.toast("Coordenadas guardadas para este proyecto.", icon="💾")
            
            with col_pdf:
                puntos = procesar_coords(txt_coords) if txt_coords else []
                geom = ee.Geometry.Polygon(puntos) if len(puntos) > 2 else None
                if geom and st.button("📄 Enviar Informe PDF"):
                    with st.spinner("Generando PDF con Historial..."):
                        archivo = generar_pdf_avanzado(data, txt_coords)
                        url = f"https://api.telegram.org/bot{T_TOKEN}/sendDocument"
                        with open(archivo, "rb") as f:
                            requests.post(url, data={"chat_id": data['CHAT_ID']}, files={"document": f})
                        st.toast("Informe enviado al titular.", icon="🚀")
                        os.remove(archivo)

        with c2:
            m = folium.Map(location=[-37, -72], zoom_start=5)
            if geom:
                m = folium.Map(location=[puntos[0][1], puntos[0][0]], zoom_start=14)
                folium.GeoJson(data=geom.getInfo(), style_function=lambda x: {'color': '#00ffcc', 'weight': 2}).add_to(m)
            folium.TileLayer('https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}', attr='Google', name='Sat').add_to(m)
            st_folium(m, width="100%", height=500)
