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
    st.error("Error de credenciales en Streamlit Secrets.")
    st.stop()

CLIENTES_DB = {
    "Pascua Lama (Cordillera)": {
        "sheet_id": "1UTrDs939rPlVIR1OTIwbJ6rM3FazgjX43YnJdue-Dmc",
        "pestaña": "ID_CARPETA_2",
        "lat": -29.32, "lon": -70.02,
        "sensores": "Sentinel-1/2 & Landsat"
    }
}

# --- 2. PROCESAMIENTO TOLERANTE (SOLUCIÓN AL ERROR) ---
def procesar_datos_seguro(sheet_id, pestaña):
    try:
        hoja = G_CLIENT.open_by_key(sheet_id).worksheet(pestaña)
        df = pd.DataFrame(hoja.get_all_records())
        
        if df.empty: return df

        # Limpiar fechas
        df['Fecha'] = pd.to_datetime(df['Fecha'], errors='coerce')
        df = df.dropna(subset=['Fecha'])

        # Lista de columnas que queremos, pero procesadas una por una para evitar errores
        indices_objetivo = ["SAVI", "NDWI", "SWIR", "Arcillas", "Deficit", "VV", "VH"]
        columnas_reales = []

        for col in indices_objetivo:
            if col in df.columns:
                # Convierte "Muy Alto" a número o NaN sin romperse
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
                columnas_reales.append(col)

        df = df.sort_values('Fecha').drop_duplicates('Fecha')
        return df, columnas_reales
    except Exception as e:
        st.error(f"Error técnico: {e}")
        return pd.DataFrame(), []

# --- 3. GRÁFICOS Y PDF ---
def crear_grafico(df, columnas):
    plt.style.use('dark_background')
    fig, ax = plt.subplots(figsize=(10, 4))
    for col in columnas:
        if not (df[col] == 0).all():
            ax.plot(df['Fecha'], df[col], marker='o', label=col)
    ax.legend(loc='upper left', bbox_to_anchor=(1, 1))
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150)
    return buf

def generar_pdf(df, proyecto, columnas):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, f"REPORTE BIOCORE: {proyecto}", 0, 1, 'C')
    pdf.set_font("Arial", size=10)
    pdf.ln(10)
    
    # Resumen de promedios solo de las columnas que existen
    pdf.cell(0, 10, "Resumen de Indices detectados:", 0, 1)
    promedios = df[columnas].mean()
    for idx, val in promedios.items():
        pdf.cell(0, 7, f"- {idx}: {val:.4f}", 0, 1)

    return pdf.output(dest='S').encode('latin-1')

# --- 4. INTERFAZ ---
st.title("🌿 BioCore Intelligence")
sel = st.selectbox("Proyecto:", list(CLIENTES_DB.keys()))

if st.button("🚀 Sincronizar"):
    config = CLIENTES_DB[sel]
    df, cols_encontradas = procesar_datos_seguro(config["sheet_id"], config["pestaña"])
    
    if not df.empty:
        st.success(f"Datos cargados. Columnas detectadas: {', '.join(cols_encontradas)}")
        st.image(crear_grafico(df, cols_encontradas))
        
        pdf_bytes = generar_pdf(df, sel, cols_encontradas)
        b64 = base64.b64encode(pdf_bytes).decode()
        href = f'<a href="data:application/pdf;base64,{b64}" download="Reporte_{sel}.pdf" style="text-decoration:none; background-color:#1e4620; color:white; padding:15px; border-radius:5px;">📥 DESCARGAR REPORTE</a>'
        st.markdown(href, unsafe_allow_html=True)
    else:
        st.warning("Asegúrate de que el Excel tenga al menos las columnas 'Fecha' y algún índice.")
