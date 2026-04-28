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
import requests
from datetime import datetime

# --- 1. CONFIGURACIÓN E INTERFAZ PROFESIONAL ---
st.set_page_config(page_title="BioCore Intelligence: Vigilancia SEIA", layout="wide")
DIRECTORA = "Loreto Campos Carrasco"

st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stButton>button { background-color: #1a3a5a; color: white; font-weight: bold; height: 3em; }
    .metric-container { background-color: white; padding: 20px; border-radius: 10px; box-shadow: 2px 2px 5px rgba(0,0,0,0.1); }
    .section-header { color: #1a3a5a; font-weight: bold; font-size: 24px; border-bottom: 2px solid #1a3a5a; padding-bottom: 5px; margin-bottom: 15px; }
    </style>
    """, unsafe_allow_html=True)

if 'clientes_db' not in st.session_state:
    st.session_state.clientes_db = {
        "Laguna Señoraza (Laja)": {
            "tipo": "HUMEDAL", "sheet_id": "1x6yAXNNlea3e43rijJu0aqcRpe4oP3BEnzgSgLuG1vU", 
            "pestaña": "ID_CARPETA_1", "umbral": 0.10
        },
        "Pascua Lama (Cordillera)": {
            "tipo": "MINERIA", "sheet_id": "1UTrDs939rPlVIR1OTIwbJ6rM3FazgjX43YnJdue-Dmc", 
            "pestaña": "ID_CARPETA_2", "umbral": 0.35
        }
    }

# --- 2. FUNCIONES DE CONEXIÓN Y DATOS ---
def cargar_datos_biocore(sheet_id, pestaña):
    try:
        creds_info = json.loads(st.secrets["GEE_JSON"])
        SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        CREDS = Credentials.from_service_account_info(creds_info, scopes=SCOPE)
        client = gspread.authorize(CREDS)
        sh = client.open_by_key(sheet_id)
        hoja = sh.worksheet(pestaña.strip())
        df = pd.DataFrame(hoja.get_all_records())
        df.columns = [str(c).strip().upper() for c in df.columns]
        if 'FECHA' in df.columns:
            df['FECHA'] = pd.to_datetime(df['FECHA'], dayfirst=True, errors='coerce')
            df = df.dropna(subset=['FECHA']).sort_values('FECHA')
        return df
    except Exception as e:
        st.error(f"Falla de conexión: {e}")
        return pd.DataFrame()

# --- 3. LÓGICA DE VISUALIZACIÓN Y DIAGNÓSTICO ---
def obtener_config_ecosistema(tipo):
    if tipo == "MINERIA":
        return {
            "indices": ["NDSI", "CLAY", "SWIR"],
            "colores": ["#00BFFF", "#D2691E", "#708090"],
            "main": "NDSI", "desc": "Criósfera y Estériles"
        }
    return {
        "indices": ["NDWI", "SAVI", "SWIR"],
        "colores": ["#1E90FF", "#32CD32", "#8B4513"],
        "main": "NDWI", "desc": "Cuerpo de Agua y Veg."
    }

# --- 4. GENERACIÓN DE INFORME PDF ---
class BioCoreReport(FPDF):
    def header(self):
        self.set_fill_color(26, 58, 90)
        self.rect(0, 0, 210, 40, 'F')
        self.set_text_color(255, 255, 255)
        self.set_font("Arial", 'B', 15)
        self.cell(0, 15, "INFORME DE CUMPLIMIENTO AMBIENTAL - SEIA", 0, 1, 'C')

def generar_pdf(df, info, nombre):
    pdf = BioCoreReport()
    pdf.add_page()
    pdf.ln(35)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, f"PROYECTO: {nombre.upper()} | TIPO: {info['tipo']}", ln=1)
    
    conf = obtener_config_ecosistema(info['tipo'])
    val_act = df[conf['main']].iloc[-1]
    
    # Diagnóstico dinámico
    estado = "CRÍTICO" if val_act < info['umbral'] else "ESTABLE"
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(0, 10, f"ESTATUS ACTUAL: {estado}", ln=1)
    
    # Agregar Gráfico al PDF
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(df['FECHA'], df[conf['main']], color=conf['colores'][0], marker='o')
    ax.axhline(y=info['umbral'], color='red', linestyle='--')
    plt.grid(True, alpha=0.3)
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150)
    plt.close()
    
    with open("temp.png", "wb") as f: f.write(buf.getbuffer())
    pdf.image("temp.png", x=15, w=180)
    
    return pdf.output(dest='S').encode('latin-1')

# --- 5. NAVEGACIÓN ---
menu = st.sidebar.radio("SISTEMA BIOCORE", ["🛡️ Auditoría", "⚙️ Gestión"])

if menu == "🛡️ Auditoría":
    st.markdown('<p class="section-header">Panel de Vigilancia de Alto Nivel</p>', unsafe_allow_html=True)
    
    if not st.session_state.clientes_db:
        st.info("No hay proyectos registrados.")
    else:
        p_sel = st.selectbox("Seleccione Proyecto Activo:", list(st.session_state.clientes_db.keys()))
        info = st.session_state.clientes_db[p_sel]
        conf = obtener_config_ecosistema(info['tipo'])
        
        col_ctrl, col_map = st.columns([1, 1.2])
        
        with col_ctrl:
            if st.button("🚀 EJECUTAR AUDITORÍA"):
                df = cargar_datos_biocore(info['sheet_id'], info['pestaña'])
                if not df.empty:
                    val_act = df[conf['main']].iloc[-1]
                    prom_hist = df[conf['main']].mean()
                    desv = ((val_act - prom_hist) / prom_hist) * 100
                    
                    # Métricas Históricas
                    m1, m2 = st.columns(2)
                    m1.metric(f"Último {conf['main']}", f"{val_act:.3f}")
                    m2.metric("Vs Histórico", f"{desv:+.1f}%")
                    
                    # Gráfico Comparativo
                    fig, ax = plt.subplots()
                    for idx, color in zip(conf['indices'], conf['colores']):
                        if idx in df.columns:
                            ax.plot(df['FECHA'], df[idx], label=idx, color=color, marker='o')
                    ax.fill_between(df['FECHA'], prom_hist*0.9, prom_hist*1.1, color='gray', alpha=0.1, label='Rango Normal')
                    ax.legend()
                    st.pyplot(fig)
                    
                    # PDF y Descarga
                    pdf_b = generar_pdf(df, info, p_sel)
                    b64 = base64.b64encode(pdf_b).decode()
                    st.markdown(f'<a href="data:application/pdf;base64,{b64}" download="Reporte_{p_sel}.pdf" style="text-decoration:none;"><div style="text-align:center; padding:12px; background-color:#1a3a5a; color:white; border-radius:8px; font-weight:bold;">📥 DESCARGAR INFORME TÉCNICO</div></a>', unsafe_allow_html=True)

        with col_map:
            if "coords" in info:
                m = folium.Map(location=info['coords'][0], zoom_start=14)
                folium.Polygon(locations=info['coords'], color="#1a3a5a", fill=True, fill_opacity=0.4).add_to(m)
                folium_static(m)
            else:
                st.warning("Coordenadas no registradas para el mapa.")

else:
    st.markdown('<p class="section-header">Registro de Faenas y Proyectos SEIA</p>', unsafe_allow_html=True)
    with st.form("reg_final"):
        n = st.text_input("Nombre del Proyecto")
        t = st.selectbox("Tipo de Ecosistema", ["MINERIA", "HUMEDAL"])
        sid = st.text_input("ID Google Sheet")
        pes = st.text_input("Pestaña", value="Hoja 1")
        u = st.number_input("Umbral Crítico SEIA", value=0.35 if t=="MINERIA" else 0.10)
        c_raw = st.text_area("Coordenadas (Lat, Lon)")
        
        if st.form_submit_button("Sincronizar con BioCore"):
            nums = re.findall(r"[-+]?\d*\.\d+|[-+]?\d+", c_raw)
            coords = [[float(nums[i]), float(nums[i+1])] for i in range(0, len(nums), 2) if i+1 < len(nums)]
            st.session_state.clientes_db[n] = {"tipo": t, "sheet_id": sid, "pestaña": pes, "umbral": u, "coords": coords}
            st.success("Proyecto registrado en el historial histórico.")
