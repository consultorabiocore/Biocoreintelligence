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

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="BioCore Intelligence Admin", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stButton>button { background-color: #183654; color: white; border-radius: 8px; height: 3em; }
    </style>
    """, unsafe_allow_html=True)

try:
    creds_dict = json.loads(st.secrets["GEE_JSON"])
    SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    CREDS = Credentials.from_service_account_info(creds_dict, scopes=SCOPE)
    G_CLIENT = gspread.authorize(CREDS)
except:
    st.error("Error en credenciales.")
    st.stop()

if 'clientes_db' not in st.session_state:
    st.session_state.clientes_db = {}

# --- PROCESAMIENTO DE DATOS ---
def obtener_datos_seguros(sheet_id, pestaña):
    try:
        hoja = G_CLIENT.open_by_key(sheet_id).worksheet(pestaña)
        df = pd.DataFrame(hoja.get_all_records())
        # Limpieza crítica: asegurar que las fechas sean fechas y los números sean números
        df['Fecha'] = pd.to_datetime(df['Fecha'], errors='coerce')
        df = df.dropna(subset=['Fecha']).sort_values('Fecha')
        for col in ["SAVI", "NDSI", "NDWI", "SWIR", "Deficit"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        return df
    except: return pd.DataFrame()

def crear_graficos_pdf(df):
    # Definir los 4 índices que queremos ver
    indices = [
        ("NDSI", "ÁREA DE NIEVE/HIELO", "#00B0F0"),
        ("NDWI", "RECURSOS HÍDRICOS", "#0070C0"),
        ("SWIR", "ESTABILIDAD DE SUSTRATO", "#7030A0"),
        ("Deficit", "DEPÓSITO DE MATERIAL", "#C00000")
    ]
    
    fig, axs = plt.subplots(4, 1, figsize=(8, 11))
    
    for i, (col, titulo, color) in enumerate(indices):
        if col in df.columns and not df.empty:
            axs[i].plot(df['Fecha'], df[col], color=color, marker='o', markersize=4, lw=1.5)
            axs[i].set_title(titulo, fontsize=10, fontweight='bold')
            axs[i].grid(True, alpha=0.3, linestyle='--')
            axs[i].tick_params(axis='both', which='major', labelsize=8)
        else:
            axs[i].text(0.5, 0.5, f"Sin datos para {col}", ha='center')
            
    plt.tight_layout(pad=3.0)
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150)
    plt.close()
    return buf

# --- REPORTE PDF ---
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
    
    # PÁGINA 1: Diagnóstico
    pdf.add_page()
    pdf.ln(25)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(0, 10, f"DIAGNÓSTICO TÉCNICO: {p_nombre.upper()}", 0, 1)
    
    # Estatus Alerta
    status = ultimo.get('NDSI', 0)
    pdf.set_fill_color(200, 0, 0) if status < 0.4 else pdf.set_fill_color(0, 100, 0)
    pdf.set_text_color(255, 255, 255)
    txt_status = " ALERTA TÉCNICA: PÉRDIDA DE COBERTURA" if status < 0.4 else " CUMPLIMIENTO AMBIENTAL NORMAL"
    pdf.cell(0, 8, txt_status, 0, 1, 'L', True)
    
    pdf.ln(5)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", '', 9)
    pdf.multi_cell(0, 5, f"1. ESTADO DE CRIÓSFERA: El valor actual de NDSI es {status:.2f}.\n2. RECURSOS HÍDRICOS: NDWI estable en {ultimo.get('NDWI', 0):.2f}.\n3. RECOMENDACIÓN: Mantener monitoreo quincenal.")

    # PÁGINA 2: Gráficos
    pdf.add_page()
    pdf.ln(25)
    g_buf = crear_graficos_pdf(df)
    with open("temp_report.png", "wb") as f: f.write(g_buf.getbuffer())
    pdf.image("temp_report.png", x=15, w=180)
    
    return pdf.output(dest='S').encode('latin-1')

# --- INTERFAZ ---
st.sidebar.title("BioCore Intelligence")
menu = st.sidebar.radio("Ir a:", ["Panel de Auditoría", "Gestión de Polígonos"])

if menu == "Panel de Auditoría":
    if not st.session_state.clientes_db:
        st.warning("Primero registre un cliente en 'Gestión de Polígonos'")
    else:
        p_sel = st.selectbox("Seleccione Proyecto:", list(st.session_state.clientes_db.keys()))
        info = st.session_state.clientes_db[p_sel]
        
        col_btn, col_map = st.columns([1, 1.5])
        with col_btn:
            if st.button("🔄 ANALIZAR Y GENERAR REPORTE"):
                df_data = obtener_datos_seguros(info['sheet_id'], info['pestaña'])
                if not df_data.empty:
                    pdf_bytes = generar_pdf(df_data, p_sel)
                    b64 = base64.b64encode(pdf_bytes).decode()
                    href = f'<a href="data:application/pdf;base64,{b64}" download="Audit_{p_sel}.pdf" style="text-decoration:none;"><div style="text-align:center; padding:15px; background-color:#183654; color:white; border-radius:8px; font-weight:bold;">📥 DESCARGAR INFORME TÉCNICO PDF</div></a>'
                    st.markdown(href, unsafe_allow_html=True)
                else:
                    st.error("No se encontraron datos en la hoja especificada.")

        with col_map:
            m = folium.Map(location=info['coords'][0], zoom_start=14)
            folium.Polygon(locations=info['coords'], color="#183654", fill=True, fill_opacity=0.4).add_to(m)
            folium_static(m)

else:
    st.header("📁 Gestión de Clientes (Polígonos)")
    with st.form("form_registro"):
        nom = st.text_input("Nombre del Proyecto (ej: Pascua Lama)")
        sid = st.text_input("ID de Google Sheet")
        pes = st.text_input("Nombre de la Pestaña")
        st.markdown("**Pegue Coordenadas aquí:** (Formato: `lat, lon; lat, lon...`)")
        raw_txt = st.text_area("Bloque de coordenadas")
        
        if st.form_submit_button("Guardar Proyecto"):
            try:
                # Limpiador de texto para el pegado masivo
                limpio = raw_txt.replace('\n', ';').strip()
                puntos = [p.split(',') for p in limpio.split(';') if ',' in p]
                coords_finales = [[float(lat.strip()), float(lon.strip())] for lat, lon in puntos]
                
                if len(coords_finales) >= 3:
                    st.session_state.clientes_db[nom] = {
                        "sheet_id": sid, "pestaña": pes, "coords": coords_finales
                    }
                    st.success(f"Proyecto '{nom}' registrado con éxito.")
                else:
                    st.error("Se necesitan al menos 3 puntos.")
            except:
                st.error("Error en el formato. Use comas para lat/lon y punto y coma entre puntos.")

    st.subheader("Registro Histórico")
    st.write(pd.DataFrame.from_dict(st.session_state.clientes_db, orient='index'))
