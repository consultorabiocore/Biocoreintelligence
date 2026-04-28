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
import re

# --- 1. CONFIGURACIÓN DE INTERFAZ ---
st.set_page_config(page_title="BioCore Intelligence Admin", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stButton>button { background-color: #183654; color: white; border-radius: 8px; font-weight: bold; height: 3.5em; }
    .section-header { color: #183654; font-weight: bold; font-size: 24px; border-bottom: 2px solid #183654; padding-bottom: 10px; }
    </style>
    """, unsafe_allow_html=True)

# Conexión Segura
try:
    creds_dict = json.loads(st.secrets["GEE_JSON"])
    SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    CREDS = Credentials.from_service_account_info(creds_dict, scopes=SCOPE)
    G_CLIENT = gspread.authorize(CREDS)
except:
    st.error("Error crítico: Revisa las credenciales GEE_JSON en Secrets.")
    st.stop()

if 'clientes_db' not in st.session_state:
    st.session_state.clientes_db = {}

# --- 2. LÓGICA DE PROCESAMIENTO ---
def obtener_datos_final(sheet_id, pestaña):
    try:
        sh = G_CLIENT.open_by_key(sheet_id.strip())
        
        # DEBUG: Mostrar pestañas disponibles si falla
        pestañas_reales = [h.title for h in sh.worksheets()]
        if pestaña.strip() not in pestañas_reales:
            st.error(f"❌ Pestaña '{pestaña}' no encontrada. En el Excel se llaman: {pestañas_reales}")
            return pd.DataFrame()

        hoja = sh.worksheet(pestaña.strip())
        registros = hoja.get_all_records()
        
        if not registros:
            st.warning("⚠️ El archivo se conectó, pero la pestaña está vacía.")
            return pd.DataFrame()
            
        df = pd.DataFrame(registros)
        df.columns = [c.strip() for c in df.columns]
        df['Fecha'] = pd.to_datetime(df['Fecha'], dayfirst=True, errors='coerce')
        df = df.dropna(subset=['Fecha']).sort_values('Fecha')
        
        indices = ["SAVI", "NDSI", "NDWI", "SWIR", "Deficit"]
        for col in indices:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        return df
    except Exception as e:
        st.error(f"❌ Error de conexión: {str(e)}")
        return pd.DataFrame()

# --- 3. REPORTE PDF ---
class BioCorePDF(FPDF):
    def header(self):
        self.set_fill_color(24, 54, 84)
        self.rect(0, 0, 210, 35, 'F')
        self.set_text_color(255, 255, 255)
        self.set_font("Arial", 'B', 15)
        self.cell(0, 15, "AUDITORÍA DE CUMPLIMIENTO AMBIENTAL", 0, 1, 'C')

def generar_reporte_pdf(df, p_nombre):
    pdf = BioCorePDF()
    pdf.add_page()
    pdf.ln(30)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, f"PROYECTO: {p_nombre.upper()}", 0, 1)
    
    # Gráficos (Resumen simple para evitar fallos de memoria)
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(df['Fecha'], df['NDSI'], label='NDSI (Nieve)', color='#00B0F0')
    ax.legend()
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    plt.close()
    
    with open("temp.png", "wb") as f: f.write(buf.getbuffer())
    pdf.image("temp.png", x=15, w=180)
    return pdf.output(dest='S').encode('latin-1')

# --- 4. INTERFAZ NAVEGABLE ---
menu = st.sidebar.radio("Navegación", ["Panel Auditoría", "Gestión Clientes"])

if menu == "Panel Auditoría":
    st.markdown('<p class="section-header">🛡️ Auditoría BioCore</p>', unsafe_allow_html=True)
    if not st.session_state.clientes_db:
        st.info("No hay proyectos. Ve a 'Gestión Clientes' e ingresa el ID real del Excel.")
    else:
        p_sel = st.selectbox("Seleccione Proyecto:", list(st.session_state.clientes_db.keys()))
        info = st.session_state.clientes_db[p_sel]
        
        if st.button("🚀 GENERAR INFORME"):
            df_final = obtener_datos_final(info['sheet_id'], info['pestaña'])
            if not df_final.empty:
                pdf_bytes = generar_reporte_pdf(df_final, p_sel)
                b64 = base64.b64encode(pdf_bytes).decode()
                st.markdown(f'<a href="data:application/pdf;base64,{b64}" download="BioCore_{p_sel}.pdf" style="text-decoration:none;"><div style="text-align:center; padding:15px; background-color:#183654; color:white; border-radius:8px; font-weight:bold;">📥 DESCARGAR PDF</div></a>', unsafe_allow_html=True)

        m = folium.Map(location=info['coords'][0], zoom_start=14)
        folium.Polygon(locations=info['coords'], color="#183654", fill=True).add_to(m)
        folium_static(m)

else:
    st.markdown('<p class="section-header">📁 Gestión de Proyectos</p>', unsafe_allow_html=True)
    with st.form("registro"):
        nom = st.text_input("Nombre Proyecto")
        sid = st.text_input("ID del Sheet (Cópialo de la URL del navegador)")
        pes = st.text_input("Pestaña", value="Hoja 1")
        raw_c = st.text_area("Coordenadas (Pégalas como vengan)")
        
        if st.form_submit_button("Guardar Proyecto"):
            # Extractor inteligente de números para coordenadas
            nums = re.findall(r"[-+]?\d*\.\d+|[-+]?\d+", raw_c)
            coords = [[float(nums[i]), float(nums[i+1])] for i in range(0, len(nums), 2) if i+1 < len(nums)]
            
            if len(coords) >= 3 and sid != "ID_CARPETA_2":
                st.session_state.clientes_db[nom] = {
                    "sheet_id": sid, "pestaña": pes, "coords": coords
                }
                st.success(f"✅ Proyecto '{nom}' guardado.")
            else:
                st.error("Error: Pocas coordenadas o sigues usando 'ID_CARPETA_2'.")

    st.write("Historial:", st.session_state.clientes_db)
