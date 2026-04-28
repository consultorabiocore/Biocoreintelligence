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

# --- 1. CONFIGURACIÓN E IDENTIDAD ---
st.set_page_config(page_title="BioCore Admin System", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; border-left: 5px solid #183654; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    .section-header { color: #183654; font-weight: bold; font-size: 22px; margin-bottom: 20px; }
    </style>
    """, unsafe_allow_html=True)

# Autenticación
try:
    creds_dict = json.loads(st.secrets["GEE_JSON"])
    SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    CREDS = Credentials.from_service_account_info(creds_dict, scopes=SCOPE)
    G_CLIENT = gspread.authorize(CREDS)
except Exception as e:
    st.error(f"Error de conexión: {e}")
    st.stop()

# --- 2. BASE DE DATOS DE CLIENTES (Simulada en Session State para persistencia en la sesión) ---
if 'clientes_db' not in st.session_state:
    st.session_state.clientes_db = {
        "Pascua Lama (Cordillera)": {
            "sheet_id": "1UTrDs939rPlVIR1OTIwbJ6rM3FazgjX43YnJdue-Dmc",
            "pestaña": "ID_CARPETA_2",
            "lat": -29.3200, "lon": -70.0200,
            "region": "Atacama / San Juan",
            "contacto": "Gerencia Medio Ambiente",
            "rubro": "Minería"
        }
    }

# --- 3. FUNCIONES TÉCNICAS ---
def procesar_datos_silencioso(sheet_id, pestaña):
    try:
        hoja = G_CLIENT.open_by_key(sheet_id).worksheet(pestaña)
        df = pd.DataFrame(hoja.get_all_records())
        df['Fecha'] = pd.to_datetime(df['Fecha'], errors='coerce')
        df = df.dropna(subset=['Fecha']).sort_values('Fecha')
        
        columnas = ["SAVI", "NDSI", "NDWI", "SWIR", "Deficit"]
        for col in columnas:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').interpolate().fillna(0)
        return df
    except:
        return pd.DataFrame()

def generar_graficos_informe(df):
    columnas = [c for c in ["SAVI", "NDSI", "NDWI", "Deficit"] if c in df.columns]
    fig, axs = plt.subplots(len(columnas), 1, figsize=(8, 3 * len(columnas)))
    if len(columnas) == 1: axs = [axs]
    for i, col in enumerate(columnas):
        axs[i].plot(df['Fecha'], df[col], color="#183654", linewidth=1.5)
        axs[i].set_title(f"Análisis Histórico: {col}", fontsize=10, fontweight='bold')
        axs[i].grid(True, alpha=0.3)
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=120)
    return buf

def crear_pdf_auditoria(df, nombre_proyecto):
    info = st.session_state.clientes_db[nombre_proyecto]
    pdf = FPDF()
    pdf.add_page()
    
    # Encabezado
    pdf.set_fill_color(24, 54, 84)
    pdf.rect(0, 0, 210, 35, 'F')
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 15, "INFORME DE AUDITORÍA AMBIENTAL", 0, 1, 'C')
    
    # Datos Cliente
    pdf.set_text_color(0, 0, 0)
    pdf.ln(25)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, f"PROYECTO: {nombre_proyecto}", 0, 1)
    pdf.set_font("Arial", '', 10)
    pdf.cell(0, 7, f"Ubicación: {info['region']} | Rubro: {info['rubro']}", 0, 1)
    
    # Gráficos (Solo en el PDF)
    pdf.ln(10)
    grafico_buf = generar_graficos_informe(df)
    with open("temp_graf.png", "wb") as f: f.write(grafico_buf.getbuffer())
    pdf.image("temp_graf.png", x=15, w=180)
    
    return pdf.output(dest='S').encode('latin-1')

# --- 4. NAVEGACIÓN ---
st.sidebar.title("BioCore Intelligence")
menu = st.sidebar.radio("Ir a:", ["Dashboard de Auditoría", "Gestión de Clientes"])

if menu == "Dashboard de Auditoría":
    st.markdown('<p class="section-header">🛡️ Panel de Auditoría Satelital</p>', unsafe_allow_html=True)
    
    proyecto_sel = st.selectbox("Seleccione el Proyecto para Auditar:", list(st.session_state.clientes_db.keys()))
    info = st.session_state.clientes_db[proyecto_sel]
    
    col1, col2 = st.columns([1, 2])
    with col1:
        st.write(f"**Ubicación:** {info['region']}")
        st.write(f"**Coordenadas:** {info['lat']}, {info['lon']}")
        if st.button("🚀 Ejecutar Auditoría y Generar Reporte"):
            with st.spinner("Procesando datos..."):
                df_audit = procesar_datos_silencioso(info['sheet_id'], info['pestaña'])
                if not df_audit.empty:
                    st.success("Análisis completado.")
                    # Métricas rápidas
                    m1, m2 = st.columns(2)
                    m1.metric("Último SAVI", f"{df_audit.iloc[-1]['SAVI']:.4f}")
                    m2.metric("Déficit Hídrico", f"{df_audit.iloc[-1]['Deficit']:.2f}")
                    
                    # Descarga de PDF
                    pdf_bytes = crear_pdf_auditoria(df_audit, proyecto_sel)
                    b64 = base64.b64encode(pdf_bytes).decode()
                    href = f'<a href="data:application/pdf;base64,{b64}" download="Auditoria_{proyecto_sel}.pdf" style="text-decoration:none;"><div style="text-align:center; padding:10px; background-color:#183654; color:white; border-radius:5px;">📥 DESCARGAR INFORME PDF</div></a>'
                    st.markdown(href, unsafe_allow_html=True)
    
    with col2:
        m = folium.Map(location=[info['lat'], info['lon']], zoom_start=12)
        folium.Marker([info['lat'], info['lon']], popup=proyecto_sel).add_to(m)
        folium_static(m)

elif menu == "Gestión de Clientes":
    st.markdown('<p class="section-header">📝 Registro y Gestión de Clientes</p>', unsafe_allow_html=True)
    
    # Formulario para nuevo ingreso
    with st.expander("➕ Registrar Nuevo Proyecto"):
        with st.form("nuevo_cliente"):
            nombre = st.text_input("Nombre del Proyecto")
            sid = st.text_input("ID de Google Sheet")
            pest = st.text_input("Nombre de la Pestaña")
            reg = st.text_input("Región")
            rub = st.selectbox("Rubro", ["Minería", "Agrícola", "Energía", "Forestal"])
            c_lat = st.number_input("Latitud", format="%.4f")
            c_lon = st.number_input("Longitud", format="%.4f")
            
            if st.form_submit_button("Guardar Proyecto"):
                st.session_state.clientes_db[nombre] = {
                    "sheet_id": sid, "pestaña": pest, "lat": c_lat, "lon": c_lon, 
                    "region": reg, "rubro": rub, "contacto": "Pendiente"
                }
                st.success(f"Proyecto {nombre} registrado correctamente.")

    # Tabla de visualización de todos los clientes
    st.markdown("### Base de Datos de Clientes Activos")
    df_clientes = pd.DataFrame.from_dict(st.session_state.clientes_db, orient='index')
    st.dataframe(df_clientes, use_container_width=True)
