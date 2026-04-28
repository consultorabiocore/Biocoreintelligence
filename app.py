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
st.set_page_config(page_title="BioCore Intelligence Admin", layout="wide")

try:
    creds_dict = json.loads(st.secrets["GEE_JSON"])
    SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    CREDS = Credentials.from_service_account_info(creds_dict, scopes=SCOPE)
    G_CLIENT = gspread.authorize(CREDS)
except:
    st.error("Error: Configura las credenciales en Streamlit Secrets.")
    st.stop()

CLIENTES_DB = {
    "Pascua Lama (Cordillera)": {
        "sheet_id": "1UTrDs939rPlVIR1OTIwbJ6rM3FazgjX43YnJdue-Dmc",
        "pestaña": "ID_CARPETA_2",
        "lat": -29.32, "lon": -70.02,
        "sensores": "Sentinel-1 (SAR), Sentinel-2 (Óptico), Landsat 8/9"
    }
}

# --- 2. PROCESAMIENTO AVANZADO ---
def procesar_datos_completos(sheet_id, pestaña):
    try:
        hoja = G_CLIENT.open_by_key(sheet_id).worksheet(pestaña)
        df = pd.DataFrame(hoja.get_all_records())
        if df.empty: return df, []

        df['Fecha'] = pd.to_datetime(df['Fecha'], errors='coerce')
        df = df.dropna(subset=['Fecha'])

        # Todos los índices que BioCore debe monitorear
        indices = ["SAVI", "NDWI", "SWIR", "Arcillas", "Deficit", "VV", "VH"]
        cols_finales = []
        
        for col in indices:
            if col in df.columns:
                # Convertimos a número y tratamos los errores (como "Muy Alto")
                df[col] = pd.to_numeric(df[col], errors='coerce')
                # Si la columna tiene al menos un dato válido, la incluimos
                if df[col].notna().any():
                    cols_finales.append(col)

        df = df.sort_values('Fecha').drop_duplicates('Fecha')
        # Llenamos vacíos con el promedio para no romper la línea del gráfico
        df = df.interpolate(method='linear').fillna(0)
        
        return df, cols_finales
    except Exception as e:
        st.error(f"Error en procesamiento: {e}")
        return pd.DataFrame(), []

# --- 3. MOTOR DE GRÁFICOS DE ALTO IMPACTO ---
def generar_grafico_premium(df, columnas):
    # Paleta de colores BioCore (Verdes, Azules, Tierras)
    colores = {
        "SAVI": "#27ae60", "NDWI": "#2980b9", "SWIR": "#f39c12", 
        "Arcillas": "#a04000", "Deficit": "#c0392b", "VV": "#7f8c8d", "VH": "#34495e"
    }
    
    plt.figure(figsize=(11, 5))
    # Fondo gris muy claro para elegancia
    ax = plt.axes()
    ax.set_facecolor("#fdfdfd")
    
    for col in columnas:
        color = colores.get(col, "#000000")
        plt.plot(df['Fecha'], df[col], marker='s', markersize=4, label=col, color=color, linewidth=2, alpha=0.8)
    
    plt.title("SERIE TEMPORAL: ANÁLISIS MULTIESPECTRAL INTEGRADO", fontsize=13, fontweight='bold', color='#1e3d1e', pad=20)
    plt.legend(loc='upper left', bbox_to_anchor=(1, 1), frameon=True, fontsize=9)
    plt.grid(True, linestyle='--', alpha=0.5)
    plt.xticks(rotation=35, fontsize=9)
    plt.tight_layout()
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=200)
    return buf

# --- 4. REPORTE PDF CON IDENTIDAD VISUAL ---
def crear_pdf_biocore(df, proyecto, columnas):
    info = CLIENTES_DB[proyecto]
    pdf = FPDF()
    pdf.add_page()
    
    # 1. ENCABEZADO CON MARCA
    pdf.set_fill_color(30, 60, 30) 
    pdf.rect(0, 0, 210, 50, 'F')
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", 'B', 26)
    pdf.cell(0, 25, "BIOCORE INTELLIGENCE", 0, 1, 'C')
    pdf.set_font("Arial", 'I', 11)
    pdf.cell(0, 5, "Consultoría Ambiental y Análisis Geoespacial Avanzado", 0, 1, 'C')
    
    # 2. DATOS DEL PROYECTO
    pdf.set_text_color(40, 40, 40)
    pdf.ln(30)
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, f"REPORTE TÉCNICO: {proyecto.upper()}", 0, 1)
    pdf.set_font("Arial", size=10)
    pdf.set_fill_color(240, 245, 240)
    pdf.cell(0, 8, f" Coordenadas de Control: {info['lat']}, {info['lon']}", 0, 1, fill=True)
    pdf.cell(0, 8, f" Constelaciones Activas: {info['sensores']}", 0, 1)
    pdf.cell(0, 8, f" Fecha de Análisis: {datetime.now().strftime('%d/%m/%Y %H:%M')}", 0, 1, fill=True)
    
    # 3. EL GRÁFICO (CENTRAL)
    pdf.ln(10)
    pdf.set_font("Arial", 'B', 12)
    pdf.set_text_color(30, 60, 30)
    pdf.cell(0, 10, "1. VISUALIZACIÓN DE TENDENCIAS AMBIENTALES", 0, 1)
    
    buf = generar_grafico_premium(df, columnas)
    with open("temp_p.png", "wb") as f:
        f.write(buf.getbuffer())
    pdf.image("temp_p.png", x=10, w=190)
    
    # 4. TABLA DE RESULTADOS CLAVE
    pdf.ln(10)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, "2. VALORES PROMEDIO DEL PERIODO", 0, 1)
    
    pdf.set_font("Arial", 'B', 10)
    pdf.set_fill_color(220, 230, 220)
    pdf.cell(90, 8, " Indicador Ambiental", 1, 0, 'L', fill=True)
    pdf.cell(90, 8, " Valor Promedio", 1, 1, 'C', fill=True)
    
    pdf.set_font("Arial", size=10)
    promedios = df[columnas].mean()
    for idx, val in promedios.items():
        pdf.cell(90, 8, f" {idx}", 1)
        pdf.cell(90, 8, f"{val:.4f}", 1, 1, 'C')

    # Pie de página
    pdf.set_y(-20)
    pdf.set_font("Arial", 'I', 8)
    pdf.cell(0, 10, "Este documento es confidencial y propiedad de BioCore Intelligence. Datos procesados vía Google Earth Engine API.", 0, 0, 'C')

    return pdf.output(dest='S').encode('latin-1')

# --- 5. INTERFAZ DASHBOARD ---
st.title("🌿 BioCore Intelligence")
st.caption("Panel de Gestión de Datos Satelitales")

sel = st.selectbox("Proyecto Seleccionado:", list(CLIENTES_DB.keys()))

if st.button("📊 Sincronizar y Generar Reporte"):
    with st.spinner("Conectando con base de datos y procesando índices..."):
        config = CLIENTES_DB[sel]
        df, cols = procesar_datos_completos(config["sheet_id"], config["pestaña"])
        
        if not df.empty:
            st.success("Análisis completado con éxito.")
            # Mostrar gráfico en la app
            st.image(generar_grafico_premium(df, cols))
            
            # Descarga del PDF
            pdf_bytes = crear_pdf_biocore(df, sel, cols)
            b64 = base64.b64encode(pdf_bytes).decode()
            href = f'<a href="data:application/pdf;base64,{b64}" download="BioCore_Reporte_{sel}.pdf" style="display:block; text-align:center; padding:15px; background-color:#1B5E20; color:white; border-radius:8px; text-decoration:none; font-weight:bold; font-size:18px; margin-top:20px;">📥 DESCARGAR INFORME TÉCNICO PDF</a>'
            st.markdown(href, unsafe_allow_html=True)
