import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from fpdf import FPDF
import json
import base64
from datetime import datetime

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="BioCore Intelligence", layout="wide")

# --- CONEXIÓN A GOOGLE SHEETS ---
try:
    creds_dict = json.loads(st.secrets["GEE_JSON"])
    SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    CREDS = Credentials.from_service_account_info(creds_dict, scopes=SCOPE)
    G_CLIENT = gspread.authorize(CREDS)
except:
    st.error("Error: Revisa las credenciales en Streamlit Secrets.")
    st.stop()

# --- TU BASE DE DATOS DE PROYECTOS ---
CLIENTES_DB = {
    "Pascua Lama (Cordillera)": {
        "sheet_id": "1UTrDs939rPlVIR1OTIwbJ6rM3FazgjX43YnJdue-Dmc",
        "pestaña": "ID_CARPETA_2"
    }
}

# --- MOTOR DE INFORME MEJORADO ---
class BioCorePDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 15)
        self.cell(0, 10, 'BIOCORE INTELLIGENCE - REPORTE TECNICO', 0, 1, 'C')
        self.set_font('Arial', 'I', 10)
        self.cell(0, 10, f'Generado el: {datetime.now().strftime("%d/%m/%Y %H:%M")}', 0, 1, 'R')
        self.ln(5)

def generar_informe_completo(df, proyecto):
    pdf = BioCorePDF()
    pdf.add_page()
    
    # Resumen del Proyecto
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, f"PROYECTO: {proyecto}", 0, 1)
    pdf.set_font("Arial", size=10)
    pdf.multi_cell(0, 8, "Este documento presenta el análisis multiespectral y de índices ambientales procesados mediante sensores remotos para el área de estudio.")
    pdf.ln(5)

    # Tabla de Datos
    pdf.set_font("Arial", 'B', 9)
    # Definir columnas a imprimir (limitado al ancho de página)
    cols = ["Fecha", "SAVI", "NDWI", "SWIR", "Arcillas", "Deficit"]
    cols_presentes = [c for c in cols if c in df.columns]
    
    # Encabezados
    w = 185 / len(cols_presentes)
    for col in cols_presentes:
        pdf.cell(w, 10, col, 1, 0, 'C')
    pdf.ln()

    # Filas
    pdf.set_font("Arial", size=8)
    for _, row in df.iterrows():
        for col in cols_presentes:
            val = row[col]
            if col == "Fecha":
                txt = val.strftime('%d/%m/%Y') if hasattr(val, 'strftime') else str(val)
            else:
                txt = f"{val:.4f}" if isinstance(val, (int, float)) and val != 0 else str(val)
            pdf.cell(w, 8, txt, 1, 0, 'C')
        pdf.ln()
    
    return pdf.output(dest='S').encode('latin-1')

# --- INTERFAZ BIOCORE ---
with st.sidebar:
    st.title("🌿 BioCore Admin")
    menu = st.radio("Menú", ["📊 Panel de Auditoría", "➕ Datos del Cliente"])

if menu == "📊 Panel de Auditoría":
    proyecto_sel = st.selectbox("Seleccione Proyecto:", list(CLIENTES_DB.keys()))
    config = CLIENTES_DB[proyecto_sel]
    
    st.header(f"Auditoría de Datos: {proyecto_sel}")

    if st.button("🔄 Sincronizar y Recuperar Datos"):
        with st.spinner("Procesando base de datos..."):
            try:
                hoja = G_CLIENT.open_by_key(config["sheet_id"]).worksheet(config["pestaña"])
                df = pd.DataFrame(hoja.get_all_records())
                
                # Unificación de formatos de fecha
                df['Fecha'] = pd.to_datetime(df['Fecha'], errors='coerce')
                df = df.dropna(subset=['Fecha'])
                
                # Quitar duplicados exactos pero mantener historial
                df = df.drop_duplicates().sort_values('Fecha', ascending=False)
                
                st.session_state["data_final"] = df
                st.success(f"Se recuperaron {len(df)} registros correctamente.")
            except Exception as e:
                st.error(f"Error al conectar: {e}")

    if "data_final" in st.session_state:
        df_display = st.session_state["data_final"]
        st.subheader("Registros en Nube")
        st.dataframe(df_display, use_container_width=True)

        st.markdown("---")
        if st.button("📄 GENERAR INFORME TÉCNICO COMPLETO"):
            pdf_bytes = generar_informe_completo(df_display, proyecto_sel)
            b64 = base64.b64encode(pdf_bytes).decode()
            href = f'<a href="data:application/pdf;base64,{b64}" download="Reporte_BioCore_{proyecto_sel}.pdf" style="padding:15px; background-color:#2E7D32; color:white; border-radius:8px; text-decoration:none;">📥 DESCARGAR REPORTE PDF</a>'
            st.markdown(href, unsafe_allow_html=True)

else:
    st.header("Gestión de Datos del Cliente")
    with st.form("form_cliente"):
        col1, col2 = st.columns(2)
        with col1:
            nombre = st.text_input("Nombre del Proyecto / Cliente")
            tipo = st.selectbox("Rubro", ["Minería", "Forestal", "Agrícola"])
        with col2:
            sheet_id = st.text_input("ID del Google Sheet")
            pestaña = st.text_input("Nombre de la Pestaña", value="Hoja 1")
        
        if st.form_submit_button("Guardar Perfil de Cliente"):
            st.success("Perfil configurado. Copia estos datos en tu CLIENTES_DB.")
            st.code(f"'{nombre}': {{ 'sheet_id': '{sheet_id}', 'pestaña': '{pestaña}' }}")
