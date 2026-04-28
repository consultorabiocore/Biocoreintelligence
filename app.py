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
import re
from datetime import datetime

# --- 1. CONFIGURACIÓN E INTERFAZ ---
st.set_page_config(page_title="BioCore Intelligence Admin", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stButton>button { background-color: #183654; color: white; border-radius: 8px; font-weight: bold; height: 3.5em; width: 100%; }
    .section-header { color: #183654; font-weight: bold; font-size: 24px; border-bottom: 2px solid #183654; padding-bottom: 10px; }
    </style>
    """, unsafe_allow_html=True)

# Inicializar base de datos de sesión
if 'clientes_db' not in st.session_state:
    st.session_state.clientes_db = {}

# --- 2. CONEXIÓN Y DATOS ---
def obtener_datos_seguros(sheet_id, pestaña):
    try:
        creds_info = json.loads(st.secrets["GEE_JSON"])
        SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        CREDS = Credentials.from_service_account_info(creds_info, scopes=SCOPE)
        client = gspread.authorize(CREDS)
        
        # Limpieza de ID
        id_real = sheet_id.split('/d/')[-1].split('/')[0] if '/d/' in sheet_id else sheet_id.strip()
        
        sh = client.open_by_key(id_real)
        hoja = sh.worksheet(pestaña.strip())
        df = pd.DataFrame(hoja.get_all_records())
        
        if df.empty: return pd.DataFrame()
        
        df.columns = [c.strip() for c in df.columns]
        df['Fecha'] = pd.to_datetime(df['Fecha'], dayfirst=True, errors='coerce')
        df = df.dropna(subset=['Fecha']).sort_values('Fecha')
        
        for col in ["SAVI", "NDSI", "NDWI", "SWIR", "Deficit"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        return df
    except Exception as e:
        st.error(f"Error de lectura: {e}")
        return pd.DataFrame()

# --- 3. REPORTE PDF ---
class BioCorePDF(FPDF):
    def header(self):
        self.set_fill_color(24, 54, 84)
        self.rect(0, 0, 210, 35, 'F')
        self.set_text_color(255, 255, 255)
        self.set_font("Arial", 'B', 15)
        self.cell(0, 15, "AUDITORÍA DE CUMPLIMIENTO AMBIENTAL", 0, 1, 'C')

def generar_pdf(df, p_nombre):
    pdf = BioCorePDF()
    pdf.add_page()
    pdf.ln(30)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, f"PROYECTO: {p_nombre.upper()}", 0, 1)
    
    # Gráfico simple para el PDF
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(df['Fecha'], df['NDSI'], color='#00B0F0', marker='o')
    ax.set_title("Evolución NDSI (Nieve/Hielo)")
    buf = io.BytesIO()
    plt.savefig(buf, format='png')
    plt.close()
    
    with open("temp_pdf.png", "wb") as f: f.write(buf.getbuffer())
    pdf.image("temp_pdf.png", x=15, w=180)
    return pdf.output(dest='S').encode('latin-1')

# --- 4. NAVEGACIÓN ---
menu = st.sidebar.radio("Navegación", ["Dashboard Auditoría", "Gestión de Clientes"])

if menu == "Dashboard Auditoría":
    st.markdown('<p class="section-header">🛡️ Panel de Auditoría Satelital</p>', unsafe_allow_html=True)
    
    if not st.session_state.clientes_db:
        st.info("No hay proyectos registrados. Ve a 'Gestión de Clientes'.")
    else:
        p_sel = st.selectbox("Seleccione Proyecto:", list(st.session_state.clientes_db.keys()))
        info = st.session_state.clientes_db[p_sel]
        
        col1, col2 = st.columns([1, 1.5])
        with col1:
            if st.button("🚀 GENERAR INFORME PDF"):
                df_data = obtener_datos_seguros(info['sheet_id'], info['pestaña'])
                if not df_data.empty:
                    pdf_bytes = generar_pdf(df_data, p_sel)
                    b64 = base64.b64encode(pdf_bytes).decode()
                    href = f'<a href="data:application/pdf;base64,{b64}" download="BioCore_{p_sel}.pdf" style="text-decoration:none;"><div style="text-align:center; padding:15px; background-color:#183654; color:white; border-radius:8px; font-weight:bold;">📥 DESCARGAR REPORTE</div></a>'
                    st.markdown(href, unsafe_allow_html=True)
                else:
                    st.warning("No se pudieron cargar datos para el reporte.")

        with col2:
            m = folium.Map(location=info['coords'][0], zoom_start=14)
            folium.Polygon(locations=info['coords'], color="#183654", fill=True).add_to(m)
            folium_static(m)

else:
    st.markdown('<p class="section-header">📁 Gestión de Proyectos</p>', unsafe_allow_html=True)
    with st.form("registro_p"):
        nom = st.text_input("Nombre del Proyecto")
        sid = st.text_input("ID del Google Sheet (Cópialo de la URL)")
        pes = st.text_input("Nombre de la Pestaña", value="Hoja 1")
        raw_c = st.text_area("Pegue coordenadas (Cualquier formato)")
        
        if st.form_submit_button("Guardar"):
            # Limpiador universal de coordenadas
            nums = re.findall(r"[-+]?\d*\.\d+|[-+]?\d+", raw_c)
            coords_finales = [[float(nums[i]), float(nums[i+1])] for i in range(0, len(nums), 2) if i+1 < len(nums)]
            
            if len(coords_finales) >= 3 and len(sid) > 15:
                st.session_state.clientes_db[nom] = {
                    "sheet_id": sid.strip(), "pestaña": pes.strip(), "coords": coords_finales
                }
                st.success(f"Proyecto {nom} guardado.")
            else:
                st.error("Revisa el ID del Sheet o las coordenadas.")

    st.write("Registros:", st.session_state.clientes_db)
