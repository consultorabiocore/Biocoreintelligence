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

# --- 1. ESTILO Y CONFIGURACIÓN ---
st.set_page_config(page_title="BioCore Intelligence Admin", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stButton>button { background-color: #183654; color: white; border-radius: 8px; width: 100%; height: 3.5em; font-weight: bold; }
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

# Base de Datos Persistente en Sesión
if 'clientes_db' not in st.session_state:
    st.session_state.clientes_db = {}

# --- 2. FUNCIONES DE PROCESAMIENTO TÉCNICO ---
def obtener_datos(sheet_id, pestaña):
    try:
        sh = G_CLIENT.open_by_key(sheet_id)
        hoja = sh.worksheet(pestaña)
        df = pd.DataFrame(hoja.get_all_records())
        df.columns = [c.strip() for c in df.columns]
        df['Fecha'] = pd.to_datetime(df['Fecha'], dayfirst=True, errors='coerce')
        df = df.dropna(subset=['Fecha']).sort_values('Fecha')
        for col in ["SAVI", "NDSI", "NDWI", "SWIR", "Deficit"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').interpolate().fillna(0)
        return df
    except: return pd.DataFrame()

def graficar_reporte(df):
    fig, axs = plt.subplots(4, 1, figsize=(8, 12))
    indices = [("NDSI", "CRIÓSFERA (NIEVE/HIELO)", "#00B0F0"), 
               ("NDWI", "RECURSOS HÍDRICOS", "#0070C0"), 
               ("SWIR", "SUELO / SEDIMENTOS", "#7030A0"), 
               ("Deficit", "M. PARTICULADO / DÉFICIT", "#C00000")]
    for i, (col, tit, colr) in enumerate(indices):
        if col in df.columns:
            axs[i].plot(df['Fecha'], df[col], color=colr, lw=1.5, marker='o', markersize=3)
            axs[i].set_title(tit, fontsize=10, fontweight='bold')
            axs[i].grid(True, alpha=0.2, linestyle='--')
    plt.tight_layout(pad=3.0)
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150)
    plt.close()
    return buf

# --- 3. CLASE DE INFORME PDF ---
class BioCorePDF(FPDF):
    def header(self):
        self.set_fill_color(24, 54, 84)
        self.rect(0, 0, 210, 35, 'F')
        self.set_text_color(255, 255, 255)
        self.set_font("Arial", 'B', 15)
        self.cell(0, 15, "AUDITORÍA DE CUMPLIMIENTO AMBIENTAL", 0, 1, 'C')
        self.set_font("Arial", 'I', 8)
        self.cell(0, 5, "Responsable Técnica: Loreto Campos Carrasco | BioCore Intelligence", 0, 1, 'C')

def generar_pdf(df, p_nombre):
    info = st.session_state.clientes_db[p_nombre]
    ultimo = df.iloc[-1]
    pdf = BioCorePDF()
    pdf.add_page()
    
    # Bloque Diagnóstico
    pdf.ln(25)
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(0, 10, f"DIAGNÓSTICO TÉCNICO: {p_nombre.upper()}", 0, 1)
    
    status_val = ultimo.get('NDSI', 0)
    pdf.set_fill_color(200, 0, 0) if status_val < 0.4 else pdf.set_fill_color(0, 100, 0)
    pdf.set_text_color(255, 255, 255)
    status_txt = " ALERTA: PÉRDIDA DE COBERTURA CRÍTICA" if status_val < 0.4 else " ESTATUS: CUMPLIMIENTO NORMATIVO"
    pdf.cell(0, 8, status_txt, 0, 1, 'L', True)
    
    pdf.ln(5)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", '', 9)
    pdf.multi_cell(0, 6, f"Región: {info.get('region', 'N/A')}\nFecha de Análisis: {datetime.now().strftime('%d/%m/%Y')}\n\n"
                         f"HALLAZGOS:\n1. Índice de Nieve (NDSI): {status_val:.2f}\n2. Índice de Agua (NDWI): {ultimo.get('NDWI', 0):.2f}\n"
                         f"3. Recomendación: Se sugiere validación en terreno y revisión de barreras de polvo.")

    # Gráficos
    pdf.add_page()
    pdf.ln(20)
    g_buf = graficar_reporte(df)
    with open("temp_pdf.png", "wb") as f: f.write(g_buf.getbuffer())
    pdf.image("temp_pdf.png", x=15, w=180)
    
    return pdf.output(dest='S').encode('latin-1')

# --- 4. INTERFAZ Y NAVEGACIÓN ---
st.sidebar.title("BioCore Intelligence")
menu = st.sidebar.radio("Navegación", ["Dashboard Auditoría", "Gestión de Clientes"])

if menu == "Dashboard Auditoría":
    st.markdown('<p class="section-header">🛡️ Panel de Auditoría Satelital</p>', unsafe_allow_html=True)
    
    if not st.session_state.clientes_db:
        st.info("No hay clientes registrados. Vaya a 'Gestión de Clientes'.")
    else:
        p_sel = st.selectbox("Proyecto Seleccionado:", list(st.session_state.clientes_db.keys()))
        info = st.session_state.clientes_db[p_sel]
        
        col_ctrl, col_map = st.columns([1, 1.5])
        with col_ctrl:
            st.write(f"**Ubicación:** {info.get('region', 'No especificada')}")
            if st.button("🚀 EJECUTAR ANÁLISIS Y GENERAR INFORME"):
                with st.spinner("Procesando datos de Google Sheets..."):
                    df_final = obtener_datos(info['sheet_id'], info['pestaña'])
                    if not df_final.empty:
                        pdf_data = generar_pdf(df_final, p_sel)
                        b64 = base64.b64encode(pdf_data).decode()
                        st.markdown(f'<a href="data:application/pdf;base64,{b64}" download="Informe_{p_sel}.pdf" style="text-decoration:none;"><div style="text-align:center; padding:15px; background-color:#183654; color:white; border-radius:8px; font-weight:bold;">📥 DESCARGAR INFORME TÉCNICO PDF</div></a>', unsafe_allow_html=True)
                    else:
                        st.error("No se encontraron datos válidos en la pestaña.")

        with col_map:
            m = folium.Map(location=info['coords'][0], zoom_start=14)
            folium.Polygon(locations=info['coords'], color="#183654", fill=True, fill_opacity=0.4).add_to(m)
            folium_static(m)

else:
    st.markdown('<p class="section-header">📁 Registro y Gestión de Polígonos</p>', unsafe_allow_html=True)
    
    # Formulario de Registro Masivo
    with st.form("registro_masivo"):
        nom = st.text_input("Nombre del Proyecto")
        sid = st.text_input("Google Sheet ID")
        pes = st.text_input("Nombre de la Pestaña")
        reg = st.text_input("Región")
        st.markdown("**Pegue el bloque de coordenadas aquí:**")
        st.caption("Formato: lat, lon; lat, lon; lat, lon...")
        raw_coords = st.text_area("Coordenadas")
        
        if st.form_submit_button("Guardar Proyecto"):
            try:
                # Procesador de coordenadas flexible
                limpio = raw_coords.replace('\n', ';').strip()
                puntos = [p.split(',') for p in limpio.split(';') if ',' in p]
                coords_ok = [[float(lat.strip()), float(lon.strip())] for lat, lon in puntos]
                
                if len(coords_ok) >= 3:
                    st.session_state.clientes_db[nom] = {
                        "sheet_id": sid, "pestaña": pes, "coords": coords_ok, "region": reg
                    }
                    st.success(f"Proyecto {nom} registrado correctamente.")
                else:
                    st.error("Se necesitan al menos 3 puntos para formar un polígono.")
            except:
                st.error("Formato de coordenadas incorrecto. Use: lat, lon;")

    st.markdown("### Registro Histórico de Clientes")
    if st.session_state.clientes_db:
        st.dataframe(pd.DataFrame.from_dict(st.session_state.clientes_db, orient='index'), use_container_width=True)
