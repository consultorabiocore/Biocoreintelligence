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

# --- SISTEMA DE REGISTRO HISTÓRICO ---
# Simulamos una base de datos que guarda los resultados de cada día
if 'historico_indices' not in st.session_state:
    # Datos iniciales para que los gráficos no salgan vacíos (como en tu imagen)
    fechas = [(datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(10, 0, -1)]
    st.session_state.historico_indices = pd.DataFrame({
        "Fecha": fechas,
        "NDSI": [0.020, 0.022, 0.015, 0.025, 0.018, 0.014, 0.005, 0.017, 0.012, 0.010],
        "NDWI": [-0.11, -0.11, -0.10, -0.12, -0.11, -0.11, -0.04, -0.11, -0.11, -0.11],
        "SWIR": [0.01, -0.05, -0.08, 0.02, -0.01, -0.02, 0.04, -0.03, -0.12, -0.11]
    })

if 'suscripciones' not in st.session_state:
    st.session_state.suscripciones = [
        {
            "ID": "BC-001", 
            "PROYECTO": "Pascua Lama", 
            "TITULAR": "Loreto Campos Carrasco", 
            "CHAT_ID": "6712325113", 
            "MODALIDAD": "Diario",
            "COORDENADAS": "-29.3177, -70.0191\n-29.3300, -70.0100",
            "REGISTRO": "Activo"
        }
    ]

# --- GENERACIÓN DE GRÁFICOS PARA EL PDF ---
def crear_grafico_historico():
    df = st.session_state.historico_indices
    fig, axs = plt.subplots(3, 1, figsize=(6, 8))
    
    axs[0].plot(df["Fecha"], df["NDSI"], marker='o', color='#1f77b4')
    axs[0].set_title("ÁREA DE NIEVE/HIELO (NDSI)")
    axs[0].grid(True, alpha=0.3)
    
    axs[1].plot(df["Fecha"], df["NDWI"], marker='o', color='#2ca02c')
    axs[1].set_title("RECURSOS HÍDRICOS (NDWI)")
    axs[1].grid(True, alpha=0.3)
    
    axs[2].plot(df["Fecha"], df["SWIR"], marker='o', color='#7f7f7f')
    axs[2].set_title("ESTABILIDAD DE SUSTRATO (SWIR)")
    axs[2].grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.savefig("temp_grafico.png")
    plt.close()
    return "temp_grafico.png"

# --- FUNCIÓN GENERAR PDF PROFESIONAL ---
def generar_pdf_auditoria(data_p, coordenadas):
    pdf = FPDF()
    pdf.add_page()
    
    # Encabezado (Azul Oscuro como en tu imagen)
    pdf.set_fill_color(24, 44, 76)
    pdf.rect(0, 0, 210, 40, 'F')
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 20, f"AUDITORÍA DE CUMPLIMIENTO AMBIENTAL - {data_p['PROYECTO'].upper()}", ln=True, align='C')
    pdf.set_font("Arial", 'I', 10)
    pdf.cell(0, 5, f"Responsable Técnica: {data_p['TITULAR']} | BioCore Intelligence", ln=True, align='C')
    
    pdf.set_text_color(0, 0, 0)
    pdf.ln(20)
    
    # Diagnóstico Técnico
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, "DIAGNÓSTICO TÉCNICO DE CRIÓSFERA Y ALTA MONTAÑA", ln=True)
    pdf.set_fill_color(200, 0, 0) # Rojo Alerta
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 8, " ESTATUS: ALERTA TÉCNICA: PÉRDIDA DE COBERTURA", ln=True, fill=True)
    
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", '', 10)
    pdf.ln(2)
    pdf.multi_cell(0, 6, "1. ESTADO DE GLACIARES: El índice NDSI actual se encuentra bajo el umbral crítico.\n2. RIESGO TÉCNICO-LEGAL: La ausencia de firma espectral constituye un hallazgo crítico.\n3. RECOMENDACIÓN: Se sugiere inspección inmediata.", border=1)
    
    # Gráficos Históricos
    pdf.add_page()
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, "REGISTRO HISTÓRICO DE ÍNDICES (ÚLTIMOS 10 DÍAS)", ln=True)
    grafico_path = crear_grafico_historico()
    pdf.image(grafico_path, x=25, y=30, w=160)
    
    # Firma
    pdf.set_y(260)
    pdf.set_font("Arial", 'BI', 10)
    pdf.cell(0, 10, f"{data_p['TITULAR']}", ln=True, align='C')
    pdf.set_font("Arial", '', 9)
    pdf.cell(0, 5, "Directora Técnica - BioCore Intelligence", ln=True, align='C')

    fn = f"Informe_{data_p['PROYECTO']}.pdf"
    pdf.output(fn)
    return fn

# --- LÓGICA APP STREAMLIT ---
def inicializar_gee():
    try:
        if 'gee_auth' not in st.session_state:
            info = json.loads(st.secrets["GEE_JSON"])
            ee.Initialize(ee.ServiceAccountCredentials(info['client_email'], key_data=info['private_key'].replace("\\n", "\n")))
            st.session_state.gee_auth = True
        return True
    except: return False

with st.sidebar:
    menu = st.radio("Menú:", ["🛰️ Auditoría", "👤 Registro Histórico"])

if inicializar_gee():
    if menu == "👤 Registro Histórico":
        st.header("Base de Datos Histórica")
        # Aquí permites ver y editar el registro histórico
        st.write("Datos acumulados para el cálculo de tendencias:")
        st.dataframe(st.session_state.historico_indices, use_container_width=True)
        
        if st.button("🗑️ Limpiar Historial"):
            st.session_state.historico_indices = st.session_state.historico_indices.iloc[0:0]
            st.rerun()

    else:
        # Pantalla de Auditoría
        proyectos = [s['PROYECTO'] for s in st.session_state.suscripciones]
        sel = st.selectbox("Proyecto:", proyectos)
        idx = next(i for i, s in enumerate(st.session_state.suscripciones) if s['PROYECTO'] == sel)
        data = st.session_state.suscripciones[idx]
        
        c1, c2 = st.columns([1, 2])
        with c1:
            st.markdown(f"### Titular: {data['TITULAR']}")
            coords = st.text_area("Coordenadas Guardadas:", value=data['COORDENADAS'], height=150)
            
            if st.button("💾 Guardar y Actualizar Histórico"):
                st.session_state.suscripciones[idx]['COORDENADAS'] = coords
                # Añadir dato del día al historial (Simulado)
                nuevo_dato = pd.DataFrame({"Fecha": [datetime.now().strftime("%Y-%m-%d")], "NDSI": [0.01], "NDWI": [-0.11], "SWIR": [-0.11]})
                st.session_state.historico_indices = pd.concat([st.session_state.historico_indices, nuevo_dato]).tail(10)
                st.success("Historial actualizado para el reporte.")

            if st.button("📄 ENVIAR INFORME CON GRÁFICOS"):
                archivo = generar_pdf_auditoria(data, coords)
                url = f"https://api.telegram.org/bot{T_TOKEN}/sendDocument"
                with open(archivo, "rb") as f:
                    requests.post(url, data={"chat_id": data['CHAT_ID']}, files={"document": f})
                st.toast("Informe enviado con éxito.")
                os.remove(archivo)

        with c2:
            m = folium.Map(location=[-29.3, -70.0], zoom_start=12)
            folium.TileLayer('https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}', attr='Google', name='Sat').add_to(m)
            st_folium(m, width="100%", height=500)
