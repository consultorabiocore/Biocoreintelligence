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
    st.error("Error crítico: Credenciales GEE_JSON no encontradas en Streamlit Secrets.")
    st.stop()

# --- 2. BASE DE DATOS ESTRUCTURADA (Aquí guardas tus clientes) ---
CLIENTES_DB = {
    "Pascua Lama (Cordillera)": {
        "sheet_id": "1UTrDs939rPlVIR1OTIwbJ6rM3FazgjX43YnJdue-Dmc",
        "pestaña": "ID_CARPETA_2",
        "lat": -29.3200,
        "lon": -70.0200,
        "sensores": "Sentinel-1 (SAR), Sentinel-2 (Óptico), Landsat 8/9"
    }
}

# --- 3. MOTOR DE LIMPIEZA Y PROCESAMIENTO (Arregla el Excel automáticamente) ---
def procesar_datos_sucios(sheet_id, pestaña):
    try:
        hoja = G_CLIENT.open_by_key(sheet_id).worksheet(pestaña)
        df = pd.DataFrame(hoja.get_all_records())
        
        if df.empty:
            return df

        # Convertir fechas y eliminar lo que no sea fecha válida
        df['Fecha'] = pd.to_datetime(df['Fecha'], errors='coerce')
        df = df.dropna(subset=['Fecha'])

        # LIMPIEZA DE TEXTOS (Ej: "Muy Alto" -> NaN -> 0)
        # Esto evita el error de "could not convert string to float"
        cols_tecnicas = ["SAVI", "NDWI", "SWIR", "Arcillas", "Deficit", "VV", "VH"]
        for col in cols_tecnicas:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)

        # Eliminar filas donde todos los índices sean 0 (datos basura)
        df = df[(df[cols_tecnicas].T != 0).any()]

        # Quitar duplicados por fecha (deja el registro más reciente)
        df = df.sort_values('Fecha').drop_duplicates(subset=['Fecha'], keep='last')
        
        return df
    except Exception as e:
        st.error(f"Error al leer la base de datos: {e}")
        return pd.DataFrame()

# --- 4. GENERADOR DE GRÁFICOS TÉCNICOS ---
def crear_grafico_biocore(df):
    plt.style.use('dark_background')
    fig, ax = plt.subplots(figsize=(10, 5))
    
    # Colores BioCore
    colores = {"SAVI": "#00FF00", "NDWI": "#00D4FF", "SWIR": "#FF9800", "Arcillas": "#E91E63", "Deficit": "#F44336"}
    
    for col in colores.keys():
        if col in df.columns and not (df[col] == 0).all():
            ax.plot(df['Fecha'], df[col], marker='o', label=col, color=colores[col], linewidth=2, markersize=4)
    
    ax.set_title("Evolución Temporal de Índices Multiespectrales", fontsize=12, pad=20)
    ax.legend(loc='upper left', bbox_to_anchor=(1, 1), frameon=False)
    plt.grid(True, alpha=0.1)
    plt.xticks(rotation=35)
    plt.tight_layout()
    
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150, facecolor='#0e1117')
    plt.close()
    return buf

# --- 5. GENERADOR DE INFORME PDF (Resultados + Coordenadas) ---
def generar_pdf_ejecutivo(df, proyecto_sel):
    info = CLIENTES_DB[proyecto_sel]
    pdf = FPDF()
    pdf.add_page()
    
    # Encabezado Corporativo
    pdf.set_fill_color(18, 38, 20) 
    pdf.rect(0, 0, 210, 45, 'F')
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", 'B', 22)
    pdf.cell(0, 25, "BIOCORE INTELLIGENCE", 0, 1, 'C')
    pdf.set_font("Arial", 'I', 10)
    pdf.cell(0, 5, "Reporte de Monitoreo Ambiental Multi-Satelital", 0, 1, 'C')
    
    # Ficha Técnica con Coordenadas
    pdf.set_text_color(0, 0, 0)
    pdf.ln(25)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, f"RESUMEN EJECUTIVO: {proyecto_sel.upper()}", 0, 1)
    pdf.set_font("Arial", size=10)
    pdf.cell(0, 6, f"GEOLOCALIZACIÓN: Lat {info['lat']} / Lon {info['lon']}", 0, 1)
    pdf.cell(0, 6, f"CONSTELACIONES: {info['sensores']}", 0, 1)
    pdf.cell(0, 6, f"FECHA DE EMISIÓN: {datetime.now().strftime('%d/%m/%Y')}", 0, 1)
    
    # Resultados (Sin tablas, solo resultados clave)
    pdf.ln(10)
    pdf.set_font("Arial", 'B', 14)
    pdf.set_text_color(18, 38, 20)
    pdf.cell(0, 10, "1. RESULTADOS DETECTADOS (PROMEDIOS)", 0, 1)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", size=10)
    
    promedios = df.tail(10).mean(numeric_only=True)
    for idx, val in promedios.items():
        if val != 0:
            pdf.cell(0, 7, f"   > {idx}: {val:.4f}", 0, 1)

    # Gráfico
    pdf.ln(10)
    pdf.set_font("Arial", 'B', 14)
    pdf.set_text_color(18, 38, 20)
    pdf.cell(0, 10, "2. ANÁLISIS VISUAL DE TENDENCIAS", 0, 1)
    
    graf_buf = crear_grafico_biocore(df)
    with open("temp_report.png", "wb") as f:
        f.write(graf_buf.getbuffer())
    pdf.image("temp_report.png", x=10, w=190)
    
    # Nota técnica
    pdf.set_y(-25)
    pdf.set_font("Arial", 'I', 8)
    pdf.multi_cell(0, 5, "Los datos integran procesamiento SAR (Sentinel-1) y Óptico (S2/L8). Corrección atmosférica aplicada. Prohibida su reproducción sin autorización de BioCore.", align='C')

    return pdf.output(dest='S').encode('latin-1')

# --- 6. INTERFAZ DE USUARIO (DASHBOARD) ---
st.title("🌿 BioCore Intelligence")
st.markdown("---")

with st.sidebar:
    st.header("Configuración de Auditoría")
    sel = st.selectbox("Seleccione el Proyecto:", list(CLIENTES_DB.keys()))
    info = CLIENTES_DB[sel]
    st.write(f"**Lat:** {info['lat']}")
    st.write(f"**Lon:** {info['lon']}")
    st.write(f"**Sensores:** {info['sensores']}")

if st.button("🚀 SINCRONIZAR SENSORES Y PROCESAR"):
    with st.spinner("Analizando datos satelitales y limpiando registros..."):
        df_final = procesar_datos_sucios(info["sheet_id"], info["pestaña"])
        
        if not df_final.empty:
            st.success(f"Sincronización exitosa. Se procesaron {len(df_final)} registros únicos.")
            
            # Vista en App
            col1, col2 = st.columns([2, 1])
            with col1:
                st.image(crear_grafico_biocore(df_final))
            with col2:
                st.write("**Últimos Resultados:**")
                st.dataframe(df_final.tail(5).drop(columns=['Fecha']))

            # Botón de Descarga PDF
            pdf_bytes = generar_pdf_ejecutivo(df_final, sel)
            b64 = base64.b64encode(pdf_bytes).decode()
            href = f'<a href="data:application/pdf;base64,{b64}" download="BioCore_Reporte_{sel}.pdf" style="display:block; text-align:center; padding:20px; background-color:#1B5E20; color:white; border-radius:10px; text-decoration:none; font-weight:bold; font-size:18px;">📥 DESCARGAR REPORTE TÉCNICO (PDF)</a>'
            st.markdown(href, unsafe_allow_html=True)
        else:
            st.warning("No se encontraron datos válidos en el Google Sheet.")
