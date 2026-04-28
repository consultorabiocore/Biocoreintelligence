import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from fpdf import FPDF
import json
import base64
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import io

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="BioCore Intelligence", layout="wide")

try:
    creds_dict = json.loads(st.secrets["GEE_JSON"])
    SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    CREDS = Credentials.from_service_account_info(creds_dict, scopes=SCOPE)
    G_CLIENT = gspread.authorize(CREDS)
except:
    st.error("Error de credenciales. Revisa Streamlit Secrets.")
    st.stop()

# --- 2. BASE DE DATOS (Con Sentinel-1 incluido) ---
CLIENTES_DB = {
    "Pascua Lama (Cordillera)": {
        "sheet_id": "1UTrDs939rPlVIR1OTIwbJ6rM3FazgjX43YnJdue-Dmc",
        "pestaña": "ID_CARPETA_2",
        "lat": -29.32,
        "lon": -70.02,
        "sensores": "Sentinel-1 (SAR), Sentinel-2 (Optico), Landsat 8/9"
    }
}

# --- 3. MOTOR DE GRÁFICOS TÉCNICOS ---
def generar_grafico_avanzado(df):
    plt.style.use('dark_background') # Estilo mas técnico
    fig, ax = plt.subplots(figsize=(10, 5))
    
    # Definimos colores para cada satelite/indice
    colores = {"SAVI": "#00ff00", "NDWI": "#00f2ff", "SWIR": "#ff9900", "Arcillas": "#ff00ff", "VV/VH": "#ffffff"}
    
    for col in ["SAVI", "NDWI", "SWIR", "Arcillas"]:
        if col in df.columns:
            ax.plot(df['Fecha'], df[col], marker='o', label=f"{col} (Optico)", color=colores.get(col), linewidth=1.5)
    
    # Si tienes datos de Sentinel-1 (VV o VH)
    if "VV" in df.columns:
        ax.plot(df['Fecha'], df['VV'], ls='--', label="Sentinel-1 (Radar SAR)", color="#ffffff", alpha=0.7)

    ax.set_title("Analisis Multiespectral y de Radar", fontsize=12, color='white')
    ax.legend(loc='upper left', bbox_to_anchor=(1, 1), fontsize=8)
    plt.xticks(rotation=35)
    plt.grid(True, alpha=0.2)
    plt.tight_layout()
    
    img_buf = io.BytesIO()
    plt.savefig(img_buf, format='png', dpi=150, facecolor='#0e1117')
    plt.close()
    return img_buf

# --- 4. MOTOR DE INFORME EJECUTIVO ---
def crear_pdf_biocore(df, proyecto_sel):
    info = CLIENTES_DB[proyecto_sel]
    pdf = FPDF()
    pdf.add_page()
    
    # Encabezado Corporativo
    pdf.set_fill_color(20, 40, 20) 
    pdf.rect(0, 0, 210, 45, 'F')
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", 'B', 22)
    pdf.cell(0, 25, "BIOCORE INTELLIGENCE", 0, 1, 'C')
    pdf.set_font("Arial", 'I', 10)
    pdf.cell(0, 5, "Sistemas de Monitoreo Multi-Constelacion (SAR & Optico)", 0, 1, 'C')
    
    # Ficha Tecnica
    pdf.set_text_color(0, 0, 0)
    pdf.ln(25)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 8, f"REPORTE: {proyecto_sel.upper()}", 0, 1)
    pdf.set_font("Arial", size=10)
    pdf.cell(0, 6, f"GEOLOCALIZACION: Lat {info['lat']} / Lon {info['lon']}", 0, 1)
    pdf.cell(0, 6, f"FUSION DE DATOS: {info['sensores']}", 0, 1)
    pdf.cell(0, 6, f"ESTADO: Monitoreo Activo", 0, 1)
    
    # Analisis Estadistico
    pdf.ln(10)
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, "1. RESULTADOS CONSOLIDADOS", 0, 1)
    pdf.line(10, pdf.get_y(), 200, pdf.get_y())
    pdf.ln(5)
    
    resumen = df.tail(10).mean(numeric_only=True)
    pdf.set_font("Arial", size=10)
    for index, val in resumen.items():
        pdf.cell(95, 8, f"Promedio detectado {index}:", 0, 0)
        pdf.set_font("Arial", 'B', 10)
        pdf.cell(0, 8, f"{val:.4f}", 0, 1)
        pdf.set_font("Arial", size=10)

    # Grafico de Satelite
    pdf.ln(10)
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, "2. ANALISIS DE TENDENCIAS TEMPORALES", 0, 1)
    
    img_data = generar_grafico_avanzado(df)
    with open("radar_graph.png", "wb") as f:
        f.write(img_data.getbuffer())
    pdf.image("radar_graph.png", x=10, w=190)
    
    # Pie de pagina legal
    pdf.set_y(-30)
    pdf.set_font("Arial", 'I', 8)
    pdf.multi_cell(0, 5, "Este informe integra datos de las constelaciones Copernicus (Sentinel-1/2) y USGS/NASA (Landsat). Los resultados SAR han sido corregidos por terreno (RTC) y los datos opticos por reflectancia atmosferica (BOA).", align='C')

    return pdf.output(dest='S').encode('latin-1')

# --- 5. INTERFAZ ---
st.title("🌿 BioCore Intelligence")
st.caption("Fusion de Datos Satelitales SAR & Opticos")

with st.sidebar:
    sel = st.selectbox("Seleccione Proyecto:", list(CLIENTES_DB.keys()))
    st.markdown(f"**Lat:** `{CLIENTES_DB[sel]['lat']}`")
    st.markdown(f"**Lon:** `{CLIENTES_DB[sel]['lon']}`")

if st.button("🔄 Sincronizar Sensores y Generar Reporte"):
    config = CLIENTES_DB[sel]
    with st.spinner("Fusionando datos de Sentinel-1, Sentinel-2 y Landsat..."):
        try:
            hoja = G_CLIENT.open_by_key(config["sheet_id"]).worksheet(config["pestaña"])
            df = pd.DataFrame(hoja.get_all_records())
            df['Fecha'] = pd.to_datetime(df['Fecha'], errors='coerce')
            df = df.dropna(subset=['Fecha']).sort_values('Fecha').drop_duplicates('Fecha')
            
            if not df.empty:
                st.success("Analisis Multi-satelital Completado.")
                st.image(generar_grafico_avanzado(df))
                
                # Descarga
                pdf_bytes = crear_pdf_biocore(df, sel)
                b64 = base64.b64encode(pdf_bytes).decode()
                href = f'<a href="data:application/pdf;base64,{b64}" download="BioCore_Reporte_{sel}.pdf" style="display:block; text-align:center; padding:15px; background-color:#004d40; color:white; border-radius:8px; text-decoration:none; font-weight:bold; font-size:16px;">📥 DESCARGAR INFORME TÉCNICO (PDF)</a>'
                st.markdown(href, unsafe_allow_html=True)
        except Exception as e:
            st.error(f"Fallo en la sincronizacion: {e}")
