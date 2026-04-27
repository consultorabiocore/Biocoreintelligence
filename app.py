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

# --- CONFIGURACIÓN DE BIOCORE Intelligence ---
st.set_page_config(page_title="BioCore Intelligence", layout="wide", initial_sidebar_state="expanded")

T_TOKEN = "7961684994:AAGbepFHxXJtjCVTCjEwq2xWh9vT9TO6G68"
# Asegúrate de que esta ruta sea correcta en tu GitHub/servidor
LOGO_PATH = os.path.join("assets", "logo_biocore.png") 

# --- BASE DE DATOS HISTÓRICA (Simulada) ---
if 'historico_indices' not in st.session_state:
    # Generamos datos sintéticos para los últimos 35 días para la prueba
    start_date = datetime.now() - timedelta(days=35)
    fechas = [(start_date + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(35)]
    st.session_state.historico_indices = pd.DataFrame({
        "Fecha": fechas,
        "NDSI": [0.020, 0.022, 0.015, 0.025, 0.018, 0.014, 0.005, 0.017, 0.012, 0.010, 0.021, 0.019, 0.016, 0.023, 0.020] * 3,
        "NDWI": [-0.11, -0.11, -0.10, -0.12, -0.11, -0.11, -0.04, -0.11, -0.11, -0.11, -0.10, -0.12, -0.11, -0.11, -0.10] * 3,
        "SWIR": [0.01, -0.05, -0.08, 0.02, -0.01, -0.02, 0.04, -0.03, -0.12, -0.11, 0.03, -0.04, -0.07, 0.01, -0.02] * 3
    }).tail(35) # Nos quedamos con los últimos 35

# --- BASE DE DATOS DE SESIÓN ---
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

# --- FUNCIONES TÉCNICAS (EE, Coords) ---
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

# --- GENERACIÓN DE GRÁFICOS PULIDOS ---
def crear_grafico_pulido(dias):
    # Filtrar datos según los días elegidos
    df = st.session_state.historico_indices.tail(dias).copy()
    
    fig, axs = plt.subplots(3, 1, figsize=(6, 8))
    
    # NDSI
    axs[0].plot(df["Fecha"], df["NDSI"], marker='o', color='#1f77b4', linestyle='-', linewidth=1.5, markersize=4)
    axs[0].set_title("ÁREA DE NIEVE/HIELO (NDSI)", fontsize=10, fontweight='bold')
    axs[0].grid(True, alpha=0.3)
    axs[0].tick_params(axis='x', rotation=45, labelsize=8) # Rotar fechas
    axs[0].set_ylabel("Valor", fontsize=8)

    # NDWI
    axs[1].plot(df["Fecha"], df["NDWI"], marker='o', color='#2ca02c', linestyle='-', linewidth=1.5, markersize=4)
    axs[1].set_title("RECURSOS HÍDRICOS (NDWI)", fontsize=10, fontweight='bold')
    axs[1].grid(True, alpha=0.3)
    axs[1].tick_params(axis='x', rotation=45, labelsize=8) # Rotar fechas
    axs[1].set_ylabel("Valor", fontsize=8)

    # SWIR
    axs[2].plot(df["Fecha"], df["SWIR"], marker='o', color='#7f7f7f', linestyle='-', linewidth=1.5, markersize=4)
    axs[2].set_title("ESTABILIDAD DE SUSTRATO (SWIR)", fontsize=10, fontweight='bold')
    axs[2].grid(True, alpha=0.3)
    axs[2].tick_params(axis='x', rotation=45, labelsize=8) # Rotar fechas
    axs[2].set_ylabel("Valor", fontsize=8)

    plt.tight_layout()
    graph_fn = "temp_biocore_graph.png"
    plt.savefig(graph_fn, dpi=100) # dpi=100 para un tamaño razonable en PDF
    plt.close()
    return graph_fn

# --- FUNCIÓN GENERAR PDF PROFESIONAL (Basado en tu imagen) ---
def generar_pdf_auditoria_completa(data_p, coordenadas, dias):
    pdf = FPDF()
    pdf.add_page()
    
    # 1. Encabezado Técnico (Franja Azul Oscuro)
    pdf.set_fill_color(24, 44, 76) # Color corporativo
    pdf.rect(0, 0, 210, 40, 'F')
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 20, f"AUDITORÍA DE CUMPLIMIENTO AMBIENTAL - {data_p['PROYECTO'].upper()}", ln=True, align='C')
    pdf.set_font("Arial", 'I', 10)
    pdf.cell(0, 5, f"Responsable Técnica: {data_p['TITULAR']} | BioCore Intelligence", ln=True, align='C')
    
    pdf.set_text_color(0, 0, 0)
    pdf.ln(20)
    
    # 2. Diagnóstico Técnico
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, "DIAGNÓSTICO TÉCNICO DE CRIÓSFERA Y ALTA MONTAÑA", ln=True)
    pdf.set_fill_color(200, 0, 0) # Rojo Alerta
    pdf.set_text_color(255, 255, 255)
    # Mostramos el valor actual simulado
    pdf.cell(0, 8, " ESTATUS: ALERTA TÉCNICA: PÉRDIDA DE COBERTURA", ln=True, fill=True)
    
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", '', 10)
    pdf.ln(2)
    # Texto tal cual tu imagen de Pascua Lama
    diagnostico_txt = (
        "1. ESTADO DE GLACIARES: El índice NDSI actual (0.01) se encuentra bajo el umbral crítico de presencia de hielo/nieve perenne (0.40). Esto indica una exposición del suelo desnudo.\n"
        "2. RIESGO TÉCNICO-LEGAL: La ausencia de firma espectral de hielo constituye un hallazgo crítico. Ante una fiscalización, esto no permite generar una prueba de descargo por estabilidad.\n"
        "3. RECOMENDACIÓN: Se sugiere inspección inmediata para descartar que el bajo albedo se deba exclusivamente a la acumulación de material particulado sedimentado."
    )
    pdf.multi_cell(0, 6, diagnostico_txt, border=1)
    
    # 3. Gráficos Históricos (Nueva Página)
    pdf.add_page()
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, f"REGISTRO HISTÓRICO DE ÍNDICES (ÚLTIMOS {dias} DÍAS)", ln=True)
    grafico_path = crear_grafico_pulido(dias)
    pdf.image(grafico_path, x=25, y=30, w=160)
    
    # 4. Firma Final
    pdf.set_y(260)
    pdf.set_font("Arial", 'BI', 10)
    pdf.cell(0, 10, f"{data_p['TITULAR']}", ln=True, align='C')
    pdf.set_font("Arial", '', 9)
    pdf.cell(0, 5, "Directora Técnica - BioCore Intelligence", ln=True, align='C')

    pdf_filename = f"Informe_BioCore_{data_p['PROYECTO']}.pdf"
    pdf.output(pdf_filename)
    return pdf_filename

# --- INTERFAZ STREAMLIT ---
with st.sidebar:
    # --- LOGO RECUPERADO ---
    if os.path.exists(LOGO_PATH):
        with open(LOGO_PATH, "rb") as f:
            data = base64.b64encode(f.read()).decode()
            st.markdown(f'<div style="text-align:center"><img src="data:image/png;base64,{data}" width="180"></div>', unsafe_allow_html=True)
    
    st.markdown("---")
    # --- SELECTOR DE RANGO DE DÍAS (MEJORA) ---
    st.subheader("⚙️ Configuración del Historial")
    rango_dias = st.selectbox("Días a Visualizar en Informe:", [7, 15, 30], index=1)
    st.markdown("---")
    
    menu = st.radio("Módulo Principal:", ["🛰️ Monitor de Auditoría", "👤 Registro Histórico"])
    st.markdown("---")
    st.caption("BioCore Intelligence v3.5")

if inicializar_gee():
    if menu == "👤 Registro Histórico":
        st.header("Gestión de Datos Históricos")
        st.write(f"Mostrando los últimos {rango_dias} días registrados:")
        # Mostrar solo los días seleccionados
        df_mostrar = st.session_state.historico_indices.tail(rango_dias)
        st.dataframe(df_mostrar, use_container_width=True)
        
        if st.button("🗑️ Limpiar Historial Completo"):
            st.session_state.historico_indices = st.session_state.historico_indices.iloc[0:0]
            st.rerun()

    else:
        # Pantalla de Monitor de Auditoría
        proyectos = [s['PROYECTO'] for s in st.session_state.suscripciones]
        sel = st.selectbox("Seleccione Proyecto:", proyectos)
        idx = next(i for i, s in enumerate(st.session_state.suscripciones) if s['PROYECTO'] == sel)
        data = st.session_state.suscripciones[idx]
        
        c1, c2 = st.columns([1, 2])
        with c1:
            st.markdown(f"### Proyecto: {sel}")
            st.write(f"**Titular:** {data['TITULAR']}")
            coords = st.text_area("Coordenadas Guardadas:", value=data['COORDENADAS'], height=150)
            
            # --- BOTONES DE ACCIÓN ---
            st.write("---")
            b_c1, b_c2 = st.columns(2)
            with b_c1:
                if st.button("💾 Guardar y Actualizar"):
                    st.session_state.suscripciones[idx]['COORDENADAS'] = coords
                    st.toast("Coordenadas guardadas.", icon="💾")
            
            with b_c2:
                if st.button("📄 ENVIAR INFORME PDF"):
                    with st.spinner("Procesando histórico y generando informe..."):
                        # Generamos el PDF pasando el rango de días elegido
                        archivo = generar_pdf_auditoria_completa(data, coords, rango_dias)
                        
                        # Envío a Telegram
                        url = f"https://api.telegram.org/bot{T_TOKEN}/sendDocument"
                        with open(archivo, "rb") as f:
                            res = requests.post(url, data={"chat_id": data['CHAT_ID']}, files={"document": f})
                        
                        if res.status_code == 200:
                            st.toast("Informe transmitido con éxito.", icon="🚀")
                        else: st.error("Fallo de envío a Telegram.")
                        
                        os.remove(archivo) # Limpiar temporal

        with c2:
            # MAPA DE CONTROL
            m = folium.Map(location=[-29.3, -70.0], zoom_start=12)
            folium.TileLayer('https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}', attr='Google', name='Sat').add_to(m)
            puntos = procesar_coords(coords)
            if len(puntos) > 2:
                folium.Polygon(locations=[[p[1], p[0]] for p in puntos], color='#00ffcc', weight=2, fillOpacity=0.1).add_to(m)
            st_folium(m, width="100%", height=500)
