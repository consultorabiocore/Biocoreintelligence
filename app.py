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

# --- 1. CONFIGURACIÓN INICIAL ---
st.set_page_config(page_title="BioCore Intelligence", layout="wide")

try:
    creds_dict = json.loads(st.secrets["GEE_JSON"])
    SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    CREDS = Credentials.from_service_account_info(creds_dict, scopes=SCOPE)
    G_CLIENT = gspread.authorize(CREDS)
except:
    st.error("Error en credenciales. Revisa Streamlit Secrets.")
    st.stop()

# --- 2. BASE DE DATOS DE PROYECTOS ---
CLIENTES_DB = {
    "Pascua Lama (Cordillera)": {
        "sheet_id": "1UTrDs939rPlVIR1OTIwbJ6rM3FazgjX43YnJdue-Dmc",
        "pestaña": "ID_CARPETA_2",
        "lat": -29.32, "lon": -70.02,
        "sensores": "Sentinel-1 (SAR), Sentinel-2 (Óptico), Landsat 8/9"
    }
}

# --- 3. MOTOR DE LIMPIEZA ANTIFALLOS (Arregla el error de interpolación) ---
def procesar_datos_biocore(sheet_id, pestaña):
    try:
        hoja = G_CLIENT.open_by_key(sheet_id).worksheet(pestaña)
        df = pd.DataFrame(hoja.get_all_records())
        if df.empty: return df, []

        # Convertir fecha
        df['Fecha'] = pd.to_datetime(df['Fecha'], errors='coerce')
        df = df.dropna(subset=['Fecha'])

        indices = ["SAVI", "NDWI", "SWIR", "Arcillas", "Deficit", "VV", "VH"]
        cols_presentes = []
        
        for col in indices:
            if col in df.columns:
                # PASO CLAVE: Forzar conversión a número. "Muy Alto" se vuelve NaN automáticamente.
                df[col] = pd.to_numeric(df[col], errors='coerce')
                # Si la columna tiene datos, la consideramos para el gráfico
                if df[col].notna().any():
                    cols_presentes.append(col)

        df = df.sort_values('Fecha').drop_duplicates('Fecha')
        
        # Ahora que son números reales (float), la interpolación NO fallará
        df[cols_presentes] = df[cols_presentes].interpolate(method='linear').fillna(0)
        
        return df, cols_presentes
    except Exception as e:
        st.error(f"Error técnico detectado: {e}")
        return pd.DataFrame(), []

# --- 4. GRÁFICO PROFESIONAL (FONDO CLARO) ---
def generar_grafico_informe(df, columnas):
    colores = {
        "SAVI": "#2E7D32", "NDWI": "#1565C0", "SWIR": "#E65100", 
        "Arcillas": "#6D4C41", "Deficit": "#C62828", "VV": "#455A64", "VH": "#263238"
    }
    
    # Usamos un estilo limpio y fondo blanco para el PDF
    plt.figure(figsize=(10, 5))
    ax = plt.axes()
    ax.set_facecolor("#FFFFFF") 
    
    for col in columnas:
        color = colores.get(col, "#000000")
        plt.plot(df['Fecha'], df[col], marker='o', label=col, color=color, linewidth=2, markersize=5)
    
    plt.title("MONITOREO DE ÍNDICES AMBIENTALES - BIOCORE", fontsize=12, fontweight='bold', pad=15)
    plt.legend(loc='upper left', bbox_to_anchor=(1, 1), frameon=True)
    plt.grid(True, linestyle=':', alpha=0.6)
    plt.xticks(rotation=30)
    plt.tight_layout()
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=200, facecolor='white')
    return buf

# --- 5. REPORTE PDF EJECUTIVO ---
def crear_pdf_final(df, proyecto, columnas):
    info = CLIENTES_DB[proyecto]
    pdf = FPDF()
    pdf.add_page()
    
    # Encabezado BioCore
    pdf.set_fill_color(27, 94, 32) # Verde BioCore
    pdf.rect(0, 0, 210, 45, 'F')
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", 'B', 22)
    pdf.cell(0, 25, "BIOCORE INTELLIGENCE", 0, 1, 'C')
    pdf.set_font("Arial", 'I', 10)
    pdf.cell(0, 5, "Reporte de Análisis Satelital de Alta Precisión", 0, 1, 'C')
    
    # Info Proyecto
    pdf.set_text_color(40, 40, 40)
    pdf.ln(25)
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, f"PROYECTO: {proyecto.upper()}", 0, 1)
    pdf.set_font("Arial", size=10)
    pdf.cell(0, 7, f"Geolocalización: {info['lat']} / {info['lon']}", 0, 1)
    pdf.cell(0, 7, f"Sensores: {info['sensores']}", 0, 1)
    pdf.cell(0, 7, f"Generado el: {datetime.now().strftime('%d/%m/%Y %H:%M')}", 0, 1)
    
    # Imagen del Gráfico
    pdf.ln(5)
    graf_buf = generar_grafico_informe(df, columnas)
    with open("grafico_temp.png", "wb") as f:
        f.write(graf_buf.getbuffer())
    pdf.image("grafico_temp.png", x=10, w=190)
    
    # Tabla de Resultados
    pdf.ln(10)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, "RESUMEN DE RESULTADOS (VALORES PROMEDIO)", 0, 1)
    
    pdf.set_fill_color(230, 230, 230)
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(90, 8, " Indicador", 1, 0, 'L', True)
    pdf.cell(90, 8, " Valor", 1, 1, 'C', True)
    
    pdf.set_font("Arial", size=10)
    promedios = df[columnas].mean()
    for idx, val in promedios.items():
        pdf.cell(90, 8, f" {idx}", 1)
        pdf.cell(90, 8, f"{val:.4f}", 1, 1, 'C')

    return pdf.output(dest='S').encode('latin-1')

# --- 6. INTERFAZ ---
st.title("🌿 BioCore Intelligence")
st.markdown("**Panel de Control de Monitoreo Ambiental**")

sel = st.selectbox("Proyecto Seleccionado:", list(CLIENTES_DB.keys()))

if st.button("🚀 Sincronizar y Generar Informe"):
    with st.spinner("Limpiando datos y renderizando informe..."):
        config = CLIENTES_DB[sel]
        df, cols = procesar_datos_biocore(config["sheet_id"], config["pestaña"])
        
        if not df.empty:
            st.success("Análisis Multi-satelital Completado sin errores.")
            st.image(generar_grafico_informe(df, cols))
            
            pdf_bytes = crear_pdf_final(df, sel, cols)
            b64 = base64.b64encode(pdf_bytes).decode()
            href = f'<a href="data:application/pdf;base64,{b64}" download="Informe_BioCore_{sel}.pdf" style="display:block; text-align:center; padding:15px; background-color:#1B5E20; color:white; border-radius:10px; text-decoration:none; font-weight:bold; font-size:18px;">📥 DESCARGAR INFORME TÉCNICO (PDF)</a>'
            st.markdown(href, unsafe_allow_html=True)
