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

# --- 1. CONFIGURACIÓN E IDENTIDAD VISUAL ---
st.set_page_config(page_title="BioCore Intelligence", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; border-left: 5px solid #183654; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    .report-title { color: #183654; font-weight: bold; font-size: 24px; }
    </style>
    """, unsafe_allow_html=True)

try:
    creds_dict = json.loads(st.secrets["GEE_JSON"])
    SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    CREDS = Credentials.from_service_account_info(creds_dict, scopes=SCOPE)
    G_CLIENT = gspread.authorize(CREDS)
except Exception as e:
    st.error(f"Fallo en la conexión: {e}")
    st.stop()

# --- 2. BASE DE DATOS DE CLIENTES CORREGIDA ---
CLIENTES_DB = {
    "Pascua Lama (Cordillera)": {
        "sheet_id": "1UTrDs939rPlVIR1OTIwbJ6rM3FazgjX43YnJdue-Dmc",
        "pestaña": "ID_CARPETA_2",
        "lat": -29.3200, "lon": -70.0200,
        "rubro": "Minería",
        "region": "Atacama / San Juan",  # CLAVE AGREGADA PARA EVITAR KEYERROR
        "contacto": "Gerencia Medio Ambiente",
        "sensores": "Sentinel-1 (SAR), Sentinel-2 (Óptico), Landsat 8/9"
    }
}

# --- 3. PROCESAMIENTO TÉCNICO DE DATOS ---
def obtener_datos_audit(sheet_id, pestaña):
    try:
        hoja = G_CLIENT.open_by_key(sheet_id).worksheet(pestaña)
        df = pd.DataFrame(hoja.get_all_records())
        
        df['Fecha'] = pd.to_datetime(df['Fecha'], errors='coerce')
        df = df.dropna(subset=['Fecha']).sort_values('Fecha')
        
        columnas_tecnicas = ["SAVI", "NDSI", "NDWI", "SWIR", "Deficit", "Arcillas", "VV", "VH"]
        presentes = []
        
        for col in columnas_tecnicas:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
                df[col] = df[col].interpolate().fillna(0)
                presentes.append(col)
        
        return df, presentes
    except Exception as e:
        st.error(f"Error al leer la base de datos: {e}")
        return pd.DataFrame(), []

# --- 4. MOTOR DE GRÁFICOS ---
def generar_graficos_cascada(df, columnas):
    n = len(columnas)
    fig, axs = plt.subplots(n, 1, figsize=(10, 3.5 * n))
    if n == 1: axs = [axs]
    
    colores = {"SAVI": "#2E7D32", "NDSI": "#0077b6", "NDWI": "#1565C0", "Deficit": "#C62828"}
    
    for i, col in enumerate(columnas):
        axs[i].plot(df['Fecha'], df[col], color=colores.get(col, "#455A64"), linewidth=2, marker='o', markersize=4)
        axs[i].set_title(f"TENDENCIA: {col}", fontsize=11, fontweight='bold', loc='left', color='#183654')
        axs[i].grid(True, linestyle='--', alpha=0.6)
    
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150)
    return buf

# --- 5. REPORTE TÉCNICO PDF ---
class BioCoreReport(FPDF):
    def header(self):
        self.set_fill_color(24, 54, 84)
        self.rect(0, 0, 210, 40, 'F')
        self.set_text_color(255, 255, 255)
        self.set_font("Arial", 'B', 16)
        self.cell(0, 20, "AUDITORÍA DE CUMPLIMIENTO AMBIENTAL", 0, 1, 'C')

def crear_pdf_final(df, proyecto_nombre, cols):
    info = CLIENTES_DB[proyecto_nombre]
    pdf = BioCoreReport()
    pdf.add_page()
    pdf.ln(30)
    
    pdf.set_font("Arial", 'B', 12)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(0, 10, f"PROYECTO: {proyecto_nombre.upper()}", 0, 1)
    pdf.set_font("Arial", '', 10)
    pdf.multi_cell(0, 6, f"Localización: {info['region']}\nCoordenadas: {info['lat']}, {info['lon']}")
    
    buf_g = generar_graficos_cascada(df, cols)
    with open("report_graf.png", "wb") as f: f.write(buf_g.getbuffer())
    pdf.image("report_graf.png", x=15, y=80, w=180)
    
    return pdf.output(dest='S').encode('latin-1')

# --- 6. INTERFAZ PRINCIPAL ---
st.sidebar.title("Panel BioCore")
menu = st.sidebar.radio("Navegación:", ["Dashboard Auditoría", "Registro de Clientes"])

if menu == "Dashboard Auditoría":
    st.markdown('<p class="report-title">🌿 BioCore Intelligence: Auditoría Satelital</p>', unsafe_allow_html=True)
    
    proyecto_sel = st.sidebar.selectbox("Seleccione Proyecto:", list(CLIENTES_DB.keys()))
    info = CLIENTES_DB[proyecto_sel]

    col_map, col_data = st.columns([2, 1])

    with col_data:
        st.subheader("Ficha del Proyecto")
        st.write(f"**Región:** {info['region']}") # Ya no dará error
        st.write(f"**Rubro:** {info['rubro']}")
        st.write(f"**Sensores:** {info['sensores']}")
        
    with col_map:
        # Mapa Satelital blindado
        m = folium.Map(location=[info['lat'], info['lon']], zoom_start=13, 
                       tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
                       attr='Esri World Imagery')
        folium.Marker([info['lat'], info['lon']], popup=proyecto_sel).add_to(m)
        folium_static(m)

    if st.button("🚀 EJECUTAR AUDITORÍA"):
        df_final, cols_final = obtener_datos_audit(info['sheet_id'], info['pestaña'])
        if not df_final.empty:
            st.image(generar_graficos_cascada(df_final, cols_final))
            pdf_bytes = crear_pdf_final(df_final, proyecto_sel, cols_final)
            b64 = base64.b64encode(pdf_bytes).decode()
            href = f'<a href="data:application/pdf;base64,{b64}" download="Reporte_{proyecto_sel}.pdf" style="text-decoration:none;"><div style="text-align:center; padding:15px; background-color:#183654; color:white; border-radius:10px; font-weight:bold;">📥 DESCARGAR REPORTE (PDF)</div></a>'
            st.markdown(href, unsafe_allow_html=True)

elif menu == "Registro de Clientes":
    st.subheader("📝 Gestión de Datos del Cliente")
    with st.form("registro"):
        st.text_input("Nombre del Proyecto")
        st.form_submit_button("Guardar")
