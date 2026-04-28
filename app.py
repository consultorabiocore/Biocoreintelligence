import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from fpdf import FPDF
import json
import base64
import gspread
from google.oauth2.service_account import Credentials
import io
import folium
from streamlit_folium import folium_static
from datetime import datetime

# --- 1. CONFIGURACIÓN Y ESTILO ---
st.set_page_config(page_title="BioCore Intelligence Admin", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .sidebar .sidebar-content { background-color: #183654; }
    .section-header { color: #183654; font-weight: bold; font-size: 24px; margin-bottom: 20px; }
    </style>
    """, unsafe_allow_html=True)

# Conexión Segura
try:
    creds_dict = json.loads(st.secrets["GEE_JSON"])
    SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    CREDS = Credentials.from_service_account_info(creds_dict, scopes=SCOPE)
    G_CLIENT = gspread.authorize(CREDS)
except:
    st.error("Error de configuración de credenciales.")
    st.stop()

# Base de Datos de Clientes con Polígonos
if 'clientes_db' not in st.session_state:
    st.session_state.clientes_db = {
        "Pascua Lama (Cordillera)": {
            "sheet_id": "1UTrDs939rPlVIR1OTIwbJ6rM3FazgjX43YnJdue-Dmc",
            "pestaña": "ID_CARPETA_2",
            "coords": [[-29.32, -70.02], [-29.32, -70.01], [-29.33, -70.01], [-29.33, -70.02]],
            "region": "Atacama",
            "sensores": "Sentinel-1/2, Landsat 8/9"
        }
    }

# --- 2. FUNCIONES TÉCNICAS ---
def obtener_datos_limpios(sheet_id, pestaña):
    try:
        hoja = G_CLIENT.open_by_key(sheet_id).worksheet(pestaña)
        df = pd.DataFrame(hoja.get_all_records())
        df['Fecha'] = pd.to_datetime(df['Fecha'], errors='coerce')
        df = df.dropna(subset=['Fecha']).sort_values('Fecha')
        for col in ["SAVI", "NDSI", "NDWI", "SWIR", "Deficit"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').interpolate().fillna(0)
        return df
    except: return pd.DataFrame()

def generar_graficos_informe(df):
    fig, axs = plt.subplots(4, 1, figsize=(8, 12))
    temas = [("NDSI", "ÁREA DE NIEVE/HIELO"), ("NDWI", "RECURSOS HÍDRICOS"), 
             ("SWIR", "ESTABILIDAD DE SUSTRATO"), ("Deficit", "DEPÓSITO DE MATERIAL")]
    for i, (col, titulo) in enumerate(temas):
        if col in df.columns:
            axs[i].plot(df['Fecha'], df[col], color="#1565C0", lw=1.5, marker='o', markersize=3)
            axs[i].set_title(titulo, fontsize=10, fontweight='bold')
            axs[i].grid(True, alpha=0.2)
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150)
    return buf

# --- 3. GENERADOR DE INFORME TÉCNICO (PDF REPARADO) ---
class BioCoreReport(FPDF):
    def header(self):
        self.set_fill_color(24, 54, 84)
        self.rect(0, 0, 210, 35, 'F')
        self.set_text_color(255, 255, 255)
        self.set_font("Arial", 'B', 15)
        self.cell(0, 15, "AUDITORÍA DE CUMPLIMIENTO AMBIENTAL", 0, 1, 'C')
        self.set_font("Arial", 'I', 8)
        self.cell(0, 5, "Responsable Técnica: Loreto Campos Carrasco | BioCore Intelligence", 0, 1, 'C')

def crear_pdf_final(df, nombre_p):
    info = st.session_state.clientes_db[nombre_p]
    ultimo = df.iloc[-1]
    pdf = BioCoreReport()
    pdf.add_page()
    
    # Diagnóstico de Criósfera
    pdf.ln(25)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(0, 10, "DIAGNÓSTICO TÉCNICO DE CRIÓSFERA Y ALTA MONTAÑA", 0, 1)
    
    # Alerta dinámica
    pdf.set_fill_color(200, 0, 0)
    pdf.set_text_color(255, 255, 255)
    status = "ESTATUS: ALERTA TÉCNICA - PÉRDIDA DE COBERTURA" if ultimo.get('NDSI', 0) < 0.4 else "ESTATUS: NORMAL"
    pdf.cell(0, 8, f" {status}", 0, 1, 'L', True)
    
    pdf.ln(5)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", '', 9)
    diagnostico = (
        f"1. ESTADO DE GLACIARES: El índice NDSI actual ({ultimo.get('NDSI', 0):.2f}) indica exposición de suelo.\n"
        f"2. RIESGO TÉCNICO-LEGAL: La firma espectral actual requiere medidas de mitigación inmediatas.\n"
        f"3. RECOMENDACIÓN: Inspección en terreno para evaluar material particulado sedimentado."
    )
    pdf.multi_cell(0, 5, diagnostico, 1)

    # Gráficos Históricos
    pdf.add_page()
    g_buf = generar_graficos_informe(df)
    with open("report_temp.png", "wb") as f: f.write(g_buf.getbuffer())
    pdf.image("report_temp.png", x=15, y=30, w=180)
    
    return pdf.output(dest='S').encode('latin-1')

# --- 4. INTERFAZ PRINCIPAL ---
st.sidebar.title("BioCore Admin")
opcion = st.sidebar.radio("Navegación", ["Dashboard Auditoría", "Gestión de Clientes (Polígonos)"])

if opcion == "Dashboard Auditoría":
    st.markdown('<p class="section-header">🛡️ Panel de Gestión de Clientes</p>', unsafe_allow_html=True)
    p_sel = st.selectbox("Proyecto Seleccionado:", list(st.session_state.clientes_db.keys()))
    info = st.session_state.clientes_db[p_sel]
    
    col1, col2 = st.columns([1, 1.5])
    with col1:
        st.write(f"**Región:** {info['region']}")
        st.write(f"**Sensores:** {info['sensores']}")
        if st.button("🔄 Ejecutar Auditoría y Generar Informe"):
            with st.spinner("Analizando base de datos..."):
                df_final = obtener_datos_limpios(info['sheet_id'], info['pestaña'])
                if not df_final.empty:
                    st.success("Análisis completo. El informe está listo.")
                    pdf_data = crear_pdf_final(df_final, p_sel)
                    b64 = base64.b64encode(pdf_data).decode()
                    st.markdown(f'<a href="data:application/pdf;base64,{b64}" download="Informe_{p_sel}.pdf" style="text-decoration:none;"><div style="text-align:center; padding:12px; background-color:#183654; color:white; border-radius:8px; font-weight:bold;">📥 DESCARGAR INFORME TÉCNICO PDF</div></a>', unsafe_allow_html=True)
    
    with col2:
        # Visualización del Polígono
        m = folium.Map(location=info['coords'][0], zoom_start=14)
        folium.Polygon(locations=info['coords'], color="#183654", fill=True, fill_opacity=0.3).add_to(m)
        folium_static(m)

else:
    st.markdown('<p class="section-header">📁 Registro Histórico de Polígonos</p>', unsafe_allow_html=True)
    
    # Registro de nuevos con 4 coordenadas
    with st.expander("➕ Registrar Nuevo Cliente y Área (Polígono)"):
        with st.form("registro_poligono"):
            nombre = st.text_input("Nombre del Proyecto")
            sid = st.text_input("Google Sheet ID")
            pest = st.text_input("Nombre Pestaña")
            
            st.write("**Coordenadas del Polígono (4 puntos):**")
            c1 = st.columns(2)
            lat1 = c1[0].number_input("Latitud 1", format="%.4f")
            lon1 = c1[1].number_input("Longitud 1", format="%.4f")
            
            c2 = st.columns(2)
            lat2 = c2[0].number_input("Latitud 2", format="%.4f")
            lon2 = c2[1].number_input("Longitud 2", format="%.4f")
            
            c3 = st.columns(2)
            lat3 = c3[0].number_input("Latitud 3", format="%.4f")
            lon3 = c3[1].number_input("Longitud 3", format="%.4f")
            
            c4 = st.columns(2)
            lat4 = c4[0].number_input("Latitud 4", format="%.4f")
            lon4 = c4[1].number_input("Longitud 4", format="%.4f")
            
            if st.form_submit_button("Guardar Proyecto y Polígono"):
                st.session_state.clientes_db[nombre] = {
                    "sheet_id": sid, "pestaña": pest,
                    "coords": [[lat1, lon1], [lat2, lon2], [lat3, lon3], [lat4, lon4]],
                    "region": "Registro Nuevo", "sensores": "Sentinel-2/Landsat"
                }
                st.rerun()

    # Tabla de todos los clientes (Acceso total)
    st.markdown("### Historial de Clientes Registrados")
    df_history = pd.DataFrame.from_dict(st.session_state.clientes_db, orient='index')
    st.dataframe(df_history, use_container_width=True)
