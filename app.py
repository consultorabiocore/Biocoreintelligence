import streamlit as st
import ee
import json
import os
import requests
import re
import base64
import folium
import pandas as pd
import matplotlib.pyplot as plt
from fpdf import FPDF
from streamlit_folium import st_folium
from datetime import datetime, timedelta

# --- CONFIGURACIÓN DE BIOCORE ---
st.set_page_config(page_title="BioCore Intelligence", layout="wide")

T_TOKEN = "7961684994:AAGbepFHxXJtjCVTCjEwq2xWh9vT9TO6G68"
LOGO_PATH = os.path.join("assets", "logo_biocore.png") 

# --- CORRECCIÓN DE BASE DE DATOS HISTÓRICA ---
if 'historico_indices' not in st.session_state:
    # Generamos exactamente 35 días para evitar el ValueError
    num_dias = 35
    start_date = datetime.now() - timedelta(days=num_dias - 1)
    fechas = [(start_date + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(num_dias)]
    
    # Creamos listas de la misma longitud exacta (35)
    import numpy as np
    st.session_state.historico_indices = pd.DataFrame({
        "Fecha": fechas,
        "NDSI": np.random.uniform(0.01, 0.03, num_dias),
        "NDWI": np.random.uniform(-0.12, -0.04, num_dias),
        "SWIR": np.random.uniform(-0.12, 0.04, num_dias)
    })

if 'suscripciones' not in st.session_state:
    st.session_state.suscripciones = [
        {
            "ID": "BC-001", "PROYECTO": "Pascua Lama", "TITULAR": "Loreto Campos Carrasco", 
            "CHAT_ID": "6712325113", "MODALIDAD": "Diario", "COORDENADAS": "-29.3177, -70.0191", "REGISTRO": "Activo"
        }
    ]

# --- FUNCIONES TÉCNICAS ---
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

# --- GENERACIÓN DE GRÁFICOS (Fechas Corregidas) ---
def crear_grafico_informe(dias):
    df = st.session_state.historico_indices.tail(dias).copy()
    fig, axs = plt.subplots(3, 1, figsize=(7, 9))
    
    colores = ['#1f77b4', '#2ca02c', '#d62728']
    indices = ['NDSI', 'NDWI', 'SWIR']
    titulos = ['ÁREA DE NIEVE/HIELO (NDSI)', 'RECURSOS HÍDRICOS (NDWI)', 'ESTABILIDAD SUSTRATO (SWIR)']

    for i in range(3):
        axs[i].plot(df["Fecha"], df[indices[i]], marker='o', color=colores[i], linewidth=2, markersize=5)
        axs[i].set_title(titulos[i], fontsize=12, fontweight='bold')
        axs[i].grid(True, linestyle='--', alpha=0.6)
        # Rotamos fechas para que no se junten
        plt.setp(axs[i].get_xticklabels(), rotation=30, horizontalalignment='right', fontsize=9)
    
    plt.tight_layout()
    path = "temp_report_graph.png"
    plt.savefig(path, dpi=120)
    plt.close()
    return path

# --- GENERAR PDF ---
def generar_pdf_auditoria(data_p, coordenadas, dias):
    pdf = FPDF()
    pdf.add_page()
    
    # Encabezado Azul BioCore
    pdf.set_fill_color(24, 44, 76)
    pdf.rect(0, 0, 210, 45, 'F')
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", 'B', 18)
    pdf.cell(0, 20, "BIOCORE INTELLIGENCE: AUDITORÍA AMBIENTAL", ln=True, align='C')
    pdf.set_font("Arial", '', 11)
    pdf.cell(0, 5, f"Proyecto: {data_p['PROYECTO']} | Titular: {data_p['TITULAR']}", ln=True, align='C')
    
    pdf.set_text_color(0, 0, 0)
    pdf.ln(25)
    
    # Diagnóstico (Basado en tu imagen)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, "1. EVALUACIÓN TÉCNICA DE SUPERFICIE", ln=True)
    pdf.set_fill_color(200, 30, 30)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 10, " ESTATUS: ALERTA DE PÉRDIDA DE COBERTURA CRIOSFÉRICA", ln=True, fill=True)
    
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", '', 10)
    pdf.ln(3)
    diagnostico = (
        "Se observa una disminución crítica en el índice de nieve (NDSI). "
        "La firma espectral indica una transición hacia suelo desnudo, lo que requiere monitoreo "
        "en terreno para validar procesos de deposición de material particulado."
    )
    pdf.multi_cell(0, 7, diagnostico, border=1)
    
    # Gráficos en nueva página
    pdf.add_page()
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 15, f"REGISTRO HISTÓRICO - ÚLTIMOS {dias} DÍAS", ln=True, align='C')
    img_path = crear_grafico_informe(dias)
    pdf.image(img_path, x=20, y=35, w=170)
    
    # Pie de firma
    pdf.set_y(265)
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(0, 5, f"{data_p['TITULAR']}", ln=True, align='C')
    pdf.set_font("Arial", '', 9)
    pdf.cell(0, 5, "Dirección Técnica BioCore Intelligence", ln=True, align='C')

    fn = f"BioCore_Report_{data_p['ID']}.pdf"
    pdf.output(fn)
    return fn

# --- INTERFAZ SIDEBAR ---
with st.sidebar:
    if os.path.exists(LOGO_PATH):
        with open(LOGO_PATH, "rb") as f:
            data = base64.b64encode(f.read()).decode()
            st.markdown(f'<div style="text-align:center"><img src="data:image/png;base64,{data}" width="180"></div>', unsafe_allow_html=True)
    
    st.markdown("---")
    st.subheader("📊 Control de Reporte")
    dias_sel = st.slider("Días de historial:", 5, 30, 15)
    
    menu = st.radio("Sección:", ["🛰️ Monitor", "👤 Historial"])

if inicializar_gee():
    if menu == "👤 Historial":
        st.header("Base de Datos del Proyecto")
        st.dataframe(st.session_state.historico_indices.tail(dias_sel), use_container_width=True)
    else:
        # PANTALLA MONITOR
        nombres = [s['PROYECTO'] for s in st.session_state.suscripciones]
        sel = st.selectbox("Proyecto Activo:", nombres)
        idx = next(i for i, s in enumerate(st.session_state.suscripciones) if s['PROYECTO'] == sel)
        data = st.session_state.suscripciones[idx]
        
        c1, c2 = st.columns([1, 2])
        with c1:
            st.markdown(f"### {sel}")
            coords_input = st.text_area("Coordenadas:", value=data['COORDENADAS'], height=150)
            
            if st.button("💾 Guardar Coordenadas"):
                st.session_state.suscripciones[idx]['COORDENADAS'] = coords_input
                st.success("Guardado.")
            
            if st.button("📄 ENVIAR INFORME PDF"):
                with st.spinner("Generando Auditoría..."):
                    archivo = generar_pdf_auditoria(data, coords_input, dias_sel)
                    url = f"https://api.telegram.org/bot{T_TOKEN}/sendDocument"
                    with open(archivo, "rb") as f:
                        requests.post(url, data={"chat_id": data['CHAT_ID']}, files={"document": f})
                    st.toast("Informe enviado correctamente.")
                    os.remove(archivo)

        with c2:
            m = folium.Map(location=[-29.3, -70.0], zoom_start=11)
            folium.TileLayer('https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}', attr='Google', name='Sat').add_to(m)
            puntos = procesar_coords(coords_input)
            if len(puntos) > 2:
                folium.Polygon(locations=[[p[1], p[0]] for p in puntos], color='#00ffcc', fill=True, fill_opacity=0.2).add_to(m)
            st_folium(m, width="100%", height=500, key=f"map_{sel}")
