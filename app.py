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

# --- 1. CONFIGURACIÓN Y CREDENCIALES ---
st.set_page_config(page_title="BioCore Audit System", layout="wide")

try:
    creds_dict = json.loads(st.secrets["GEE_JSON"])
    SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    CREDS = Credentials.from_service_account_info(creds_dict, scopes=SCOPE)
    G_CLIENT = gspread.authorize(CREDS)
except Exception as e:
    st.error(f"Error de Conexión: {e}")
    st.stop()

# --- 2. CONFIGURACIÓN TÉCNICA ---
UMBRAL_CRITICO = 0.40
CLIENTES_DB = {
    "Pascua Lama (Cordillera)": {
        "sheet_id": "1UTrDs939rPlVIR1OTIwbJ6rM3FazgjX43YnJdue-Dmc",
        "pestaña": "ID_CARPETA_2"
    }
}

# --- 3. PROCESAMIENTO DE DATOS ---
def obtener_datos(sheet_id, pestaña):
    try:
        hoja = G_CLIENT.open_by_key(sheet_id).worksheet(pestaña)
        df = pd.DataFrame(hoja.get_all_records())
        df['Fecha'] = pd.to_datetime(df['Fecha'], errors='coerce')
        df = df.dropna(subset=['Fecha']).sort_values('Fecha')
        
        # Limpieza de columnas técnicas
        cols_interes = ["SAVI", "NDWI", "SWIR", "Arcillas", "Deficit"]
        presentes = []
        for c in cols_interes:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors='coerce').interpolate().fillna(0)
                presentes.append(c)
        return df, presentes
    except:
        return pd.DataFrame(), []

# --- 4. MOTOR DE GRÁFICOS (ESTILO AUDITORÍA) ---
def crear_graficos_audit(df, columnas):
    fig, axs = plt.subplots(len(columnas), 1, figsize=(10, 3 * len(columnas)))
    if len(columnas) == 1: axs = [axs]
    
    colores = {"SAVI": "#143654", "NDWI": "#2E7D32", "SWIR": "#555555", "Deficit": "#C62828"}
    
    for i, col in enumerate(columnas):
        axs[i].plot(df['Fecha'], df[col], marker='.', color=colores.get(col, "black"), linewidth=1)
        axs[i].set_title(f"MONITOREO: {col}", fontsize=10, fontweight='bold', loc='left')
        axs[i].grid(True, linestyle=':', alpha=0.5)
        axs[i].tick_params(labelsize=8)
    
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150)
    return buf

# --- 5. REPORTE PDF PROFESIONAL ---
class BioCorePDF(FPDF):
    def header(self):
        self.set_fill_color(24, 54, 84) # Azul Marino BioCore
        self.rect(0, 0, 210, 35, 'F')
        self.set_text_color(255, 255, 255)
        self.set_font("Arial", 'B', 14)
        self.cell(0, 15, "AUDITORÍA DE CUMPLIMIENTO AMBIENTAL", 0, 1, 'C')
        self.set_font("Arial", 'I', 9)
        self.cell(0, 5, "Responsable Técnica: Loreto Campos Carrasco | BioCore Intelligence", 0, 1, 'C')

def exportar_pdf(df, proyecto, columnas):
    ultimo_val = df.iloc[-1].get('SAVI', 0)
    es_alerta = ultimo_val < UMBRAL_CRITICO
    
    pdf = BioCorePDF()
    pdf.add_page()
    pdf.ln(25)
    
    # ESTATUS
    status_txt = "ALERTA TÉCNICA: PÉRDIDA DE COBERTURA" if es_alerta else "NORMAL / CUMPLIMIENTO"
    pdf.set_fill_color(200, 0, 0) if es_alerta else pdf.set_fill_color(0, 100, 0)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, f"  ESTATUS: {status_txt}", 0, 1, 'L', True)
    
    # HALLAZGOS
    pdf.ln(5)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(0, 10, "DIAGNÓSTICO TÉCNICO:", 0, 1)
    pdf.set_font("Arial", size=10)
    
    diag = (f"Se detecta un valor de {ultimo_val:.4f}. "
            "Este registro indica una desviación crítica respecto al umbral de control ambiental." if es_alerta 
            else f"El valor de {ultimo_val:.4f} se mantiene estable.")
    
    pdf.multi_cell(0, 7, f"1. HALLAZGO: {diag}", border=1)
    pdf.multi_cell(0, 7, "2. RIESGO: Posible incumplimiento de RCA por alteración de masa criosférica.", border=1)

    # GRÁFICOS
    pdf.add_page()
    pdf.ln(20)
    buf = crear_graficos_audit(df, columnas)
    with open("temp.png", "wb") as f:
        f.write(buf.getbuffer())
    pdf.image("temp.png", x=15, w=180)
    
    return pdf.output(dest='S').encode('latin-1')

# --- 6. INTERFAZ ---
st.title("🛡️ BioCore Audit System")
sel = st.selectbox("Seleccione Proyecto:", list(CLIENTES_DB.keys()))

if st.button("🚀 Ejecutar Auditoría"):
    conf = CLIENTES_DB[sel]
    with st.spinner("Sincronizando con Google Sheets..."):
        df_data, cols_data = obtener_datos(conf["sheet_id"], conf["pestaña"])
        
        if not df_data.empty:
            st.success("Datos cargados correctamente.")
            st.image(crear_graficos_audit(df_data, cols_data))
            
            pdf_bytes = exportar_pdf(df_data, sel, cols_data)
            b64 = base64.b64encode(pdf_bytes).decode()
            href = f'<a href="data:application/pdf;base64,{b64}" download="Auditoria_{sel}.pdf" style="display:block; text-align:center; padding:15px; background-color:#183654; color:white; border-radius:5px; text-decoration:none; font-weight:bold;">📄 DESCARGAR REPORTE DE AUDITORÍA</a>'
            st.markdown(href, unsafe_allow_html=True)
        else:
            st.error("No se pudieron cargar los datos. Revisa el Excel.")
