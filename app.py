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
st.set_page_config(page_title="BioCore Admin", layout="wide")

try:
    creds_dict = json.loads(st.secrets["GEE_JSON"])
    SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    CREDS = Credentials.from_service_account_info(creds_dict, scopes=SCOPE)
    G_CLIENT = gspread.authorize(CREDS)
except:
    st.error("Revisa las credenciales en Streamlit Secrets.")
    st.stop()

CLIENTES_DB = {
    "Pascua Lama (Cordillera)": {
        "sheet_id": "1UTrDs939rPlVIR1OTIwbJ6rM3FazgjX43YnJdue-Dmc",
        "pestaña": "ID_CARPETA_2",
        "lat": -29.32, "lon": -70.02,
        "sensores": "Sentinel-1 (SAR), Sentinel-2 (Óptico), Landsat 8/9"
    }
}

# --- 2. PROCESAMIENTO INTELIGENTE ---
def procesar_datos_biocore(sheet_id, pestaña):
    try:
        hoja = G_CLIENT.open_by_key(sheet_id).worksheet(pestaña)
        df = pd.DataFrame(hoja.get_all_records())
        if df.empty: return df, []

        df['Fecha'] = pd.to_datetime(df['Fecha'], errors='coerce')
        df = df.dropna(subset=['Fecha'])

        indices = ["SAVI", "NDWI", "SWIR", "Arcillas", "Deficit", "VV", "VH"]
        cols_presentes = []
        for col in indices:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
                cols_presentes.append(col)

        df = df.sort_values('Fecha').drop_duplicates('Fecha')
        return df, cols_presentes
    except Exception as e:
        st.error(f"Error en base de datos: {e}")
        return pd.DataFrame(), []

# --- 3. MOTOR DE GRÁFICOS ---
def generar_visualizacion(df, columnas):
    plt.style.use('dark_background')
    fig, ax = plt.subplots(figsize=(10, 5))
    colores = {"SAVI": "#2ecc71", "NDWI": "#3498db", "SWIR": "#f1c40f", "Deficit": "#e74c3c"}
    
    for col in columnas:
        if col in colores and not (df[col] == 0).all():
            ax.plot(df['Fecha'], df[col], marker='o', label=col, color=colores[col], linewidth=2)
    
    ax.set_title("ANÁLISIS TEMPORAL DE ÍNDICES AMBIENTALES", fontsize=12, pad=20)
    ax.legend(loc='upper left', bbox_to_anchor=(1, 1), frameon=False)
    plt.xticks(rotation=30)
    plt.grid(True, alpha=0.1)
    plt.tight_layout()
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150)
    return buf

# --- 4. EL NUEVO REPORTE PDF (NO ESCUETO) ---
def crear_pdf_profesional(df, proyecto, columnas):
    info = CLIENTES_DB[proyecto]
    pdf = FPDF()
    pdf.add_page()
    
    # Header Estilo BioCore
    pdf.set_fill_color(30, 60, 30) # Verde Oscuro
    pdf.rect(0, 0, 210, 40, 'F')
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", 'B', 24)
    pdf.cell(0, 20, "BIOCORE INTELLIGENCE", 0, 1, 'C')
    pdf.set_font("Arial", 'I', 10)
    pdf.cell(0, 5, "Monitoreo Satelital Avanzado y Análisis de Biodiversidad", 0, 1, 'C')
    
    # Cuerpo e Información
    pdf.set_text_color(40, 40, 40)
    pdf.ln(25)
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, f"INFORME TÉCNICO: {proyecto.upper()}", 0, 1)
    pdf.set_font("Arial", size=10)
    pdf.cell(0, 6, f"Coordenadas de Control: {info['lat']}, {info['lon']}", 0, 1)
    pdf.cell(0, 6, f"Sensores Integrados: {info['sensores']}", 0, 1)
    pdf.cell(0, 6, f"Fecha de Generación: {datetime.now().strftime('%d/%m/%Y %H:%M')}", 0, 1)
    
    # Gráfico
    pdf.ln(10)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, "1. Tendencia de Índices Monitoreados", 0, 1)
    
    graf_buf = generar_visualizacion(df, columnas)
    with open("temp_graf.png", "wb") as f:
        f.write(graf_buf.getbuffer())
    pdf.image("temp_graf.png", x=10, w=190)
    
    # Tabla de Promedios
    pdf.ln(10)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, "2. Resumen Estadístico de Valores Recientes", 0, 1)
    pdf.set_font("Arial", size=10)
    
    promedios = df[columnas].tail(10).mean()
    for idx, val in promedios.items():
        pdf.cell(50, 8, f"Promedio {idx}:", 1)
        pdf.cell(50, 8, f"{val:.4f}", 1, 1)

    return pdf.output(dest='S').encode('latin-1')

# --- 5. INTERFAZ ---
st.title("🌿 BioCore Intelligence")
sel = st.selectbox("Seleccione Proyecto Activo:", list(CLIENTES_DB.keys()))

if st.button("🔄 Sincronizar y Generar Informe"):
    with st.spinner("Procesando datos de constelaciones satelitales..."):
        config = CLIENTES_DB[sel]
        df, cols = procesar_datos_biocore(config["sheet_id"], config["pestaña"])
        
        if not df.empty:
            st.success("Análisis Multi-satelital Completado.")
            st.image(generar_visualizacion(df, cols))
            
            pdf_bytes = crear_pdf_profesional(df, sel, cols)
            b64 = base64.b64encode(pdf_bytes).decode()
            href = f'<a href="data:application/pdf;base64,{b64}" download="BioCore_{sel}.pdf" style="display:block; text-align:center; padding:15px; background-color:#2E7D32; color:white; border-radius:10px; text-decoration:none; font-weight:bold;">📥 DESCARGAR INFORME TÉCNICO COMPLETO</a>'
            st.markdown(href, unsafe_allow_html=True)
