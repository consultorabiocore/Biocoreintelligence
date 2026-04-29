import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from fpdf import FPDF
import json, base64, io, re, requests
import gspread
from google.oauth2.service_account import Credentials
import folium
from streamlit_folium import folium_static
from datetime import datetime

# --- 1. INICIALIZACIÓN Y PERSISTENCIA ---
if 'clientes_db' not in st.session_state:
    st.session_state.clientes_db = {
        "Laguna Señoraza (Laja)": {
            "tipo": "HUMEDAL", 
            "sheet_id": "1x6yAXNNlea3e43rijJu0aqcRpe4oP3BEnzgSgLuG1vU", 
            "pestaña": "ID_CARPETA_1", "umbral": 0.10,
            "telegram_id": st.secrets.get("TELEGRAM_CHAT_ID", ""),
            "coords": [[-37.275, -72.715], [-37.285, -72.715], [-37.285, -72.690], [-37.270, -72.690]]
        },
        "Pascua Lama (Cordillera)": {
            "tipo": "MINERIA", 
            "sheet_id": "1UTrDs939rPlVIR1OTIwbJ6rM3FazgjX43YnJdue-Dmc", 
            "pestaña": "ID_CARPETA_2", "umbral": 0.35,
            "telegram_id": st.secrets.get("TELEGRAM_CHAT_ID", ""),
            "coords": [[-29.316, -70.033], [-29.316, -70.016], [-29.333, -70.016], [-29.333, -70.033]]
        }
    }

# --- 2. CONFIGURACIÓN E INTERFAZ ---
st.set_page_config(page_title="BioCore Intelligence", layout="wide")
DIRECTORA = "Loreto Campos Carrasco"

st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stButton>button { background-color: #1a3a5a; color: white; font-weight: bold; width: 100%; border-radius: 8px; }
    .section-header { color: #1a3a5a; font-weight: bold; font-size: 24px; border-bottom: 2px solid #1a3a5a; padding-bottom: 5px; }
    </style>
    """, unsafe_allow_html=True)

# --- 3. FUNCIONES CORE ---
def enviar_telegram_dinamico(mensaje, chat_id):
    try:
        token = st.secrets["TELEGRAM_TOKEN"]
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": chat_id, "text": mensaje, "parse_mode": "Markdown"}
        requests.post(url, json=payload)
    except: st.error("Error en conexión con Telegram.")

def cargar_datos(sheet_id, pestaña):
    try:
        creds_info = json.loads(st.secrets["GEE_JSON"])
        creds = Credentials.from_service_account_info(creds_info, scopes=["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"])
        client = gspread.authorize(creds)
        sh = client.open_by_key(sheet_id)
        df = pd.DataFrame(sh.worksheet(pestaña).get_all_records())
        df.columns = [c.strip().upper() for c in df.columns]
        if 'FECHA' in df.columns:
            df['FECHA'] = pd.to_datetime(df['FECHA'], dayfirst=True, errors='coerce')
        return df.dropna(subset=['FECHA'])
    except Exception as e:
        st.error(f"Error de datos: {e}")
        return pd.DataFrame()

def obtener_config_proyecto(tipo):
    if tipo == "MINERIA":
        return {"indices": ["NDSI", "CLAY", "SWIR"], "colores": ["#00BFFF", "#D2691E", "#708090"], "main": "NDSI"}
    return {"indices": ["NDWI", "SAVI", "SWIR"], "colores": ["#1E90FF", "#32CD32", "#8B4513"], "main": "NDWI"}

# --- 4. GENERADOR DE REPORTES PDF ---
class BioCorePDF(FPDF):
    def header(self):
        self.set_fill_color(26, 58, 90); self.rect(0, 0, 210, 35, 'F')
        self.set_text_color(255, 255, 255); self.set_font("Arial", 'B', 14)
        self.cell(0, 15, "INFORME DE CUMPLIMIENTO AMBIENTAL - BIOCORE", 0, 1, 'C')

def generar_pdf_final(df, info, nombre):
    pdf = BioCorePDF()
    pdf.add_page(); pdf.ln(30)
    pdf.set_text_color(0, 0, 0); pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, f"FAENA: {nombre.upper()}", ln=1)
    
    conf = obtener_config_proyecto(info['tipo'])
    val = df[conf['main']].iloc[-1]
    est = "CUMPLIMIENTO" if val >= info['umbral'] else "ALERTA"
    
    pdf.set_font("Arial", '', 10)
    pdf.multi_cell(0, 8, f"Diagnostico: Estatus de {conf['main']} en {val:.3f}. Estado global: {est}.\nDirectora Tecnica: {DIRECTORA}")
    
    fig, ax = plt.subplots(figsize=(6, 3))
    ax.plot(df['FECHA'], df[conf['main']], color=conf['colores'][0])
    ax.axhline(y=info['umbral'], color='red', linestyle='--')
    buf = io.BytesIO()
    plt.savefig(buf, format='png'); plt.close()
    with open("temp.png", "wb") as f: f.write(buf.getbuffer())
    pdf.image("temp.png", x=15, w=170)
    return pdf.output(dest='S').encode('latin-1')

# --- 5. NAVEGACIÓN ---
menu = st.sidebar.radio("SISTEMA", ["🛡️ Auditoría", "⚙️ Gestión"])

if menu == "🛡️ Auditoría":
    st.markdown('<p class="section-header">Panel de Vigilancia de Alto Nivel</p>', unsafe_allow_html=True)
    
    opcion = st.selectbox("Proyecto Activo:", list(st.session_state.clientes_db.keys()))
    info = st.session_state.clientes_db[opcion]
    conf = obtener_config_proyecto(info['tipo'])
    
    col_a, col_b = st.columns([1, 1.2])
    
    with col_a:
        if st.button("🚀 EJECUTAR AUDITORÍA Y NOTIFICAR"):
            df = cargar_datos(info['sheet_id'], info['pestaña'])
            if not df.empty:
                val_actual = df[conf['main']].iloc[-1]
                prom_h = df[conf['main']].mean()
                
                # Telegram
                alerta_icon = "🟢" if val_actual >= info['umbral'] else "🔴"
                msg = f"🛰 **BIOCORE: {opcion}**\nValor {conf['main']}: `{val_actual:.3f}`\nEstado: {alerta_icon} {('Estable' if alerta_icon=='🟢' else 'ALERTA')}"
                enviar_telegram_dinamico(msg, info['telegram_id'])
                
                # UI
                st.metric(conf['main'], f"{val_actual:.3f}", f"{((val_actual-prom_h)/prom_h)*100:+.1f}% vs Prom.")
                st.line_chart(df.set_index('FECHA')[conf['indices']])
                
                # PDF
                pdf_b = generar_pdf_final(df, info, opcion)
                st.download_button("📥 Descargar Reporte PDF", pdf_b, f"BioCore_{opcion}.pdf")
                st.success("Telegram enviado.")

    with col_b:
        m = folium.Map(location=info['coords'][0], zoom_start=13)
        folium.Polygon(locations=info['coords'], color="#1a3a5a", fill=True, fill_opacity=0.4).add_to(m)
        folium_static(m)

else:
    st.markdown('<p class="section-header">Registro de Proyectos Ambientales</p>', unsafe_allow_html=True)
    with st.form("registro_seia"):
        nom = st.text_input("Nombre del Proyecto")
        tip = st.selectbox("Ecosistema", ["MINERIA", "HUMEDAL"])
        tid = st.text_input("ID Telegram Cliente")
        sid = st.text_input("ID Google Sheet")
        pes = st.text_input("Pestaña", value="Hoja 1")
        umb = st.number_input("Umbral Crítico", value=0.35 if tip=="MINERIA" else 0.10)
        cor = st.text_area("Coordenadas (Lat, Lon)")
        
        if st.form_submit_button("Guardar en Base de Datos"):
            num_c = re.findall(r"[-+]?\d*\.\d+|[-+]?\d+", cor)
            coords = [[float(num_c[i]), float(num_c[i+1])] for i in range(0, len(num_c), 2) if i+1 < len(num_c)]
            if nom and coords:
                st.session_state.clientes_db[nom] = {"tipo": tip, "telegram_id": tid, "sheet_id": sid, "pestaña": pes, "umbral": umb, "coords": coords}
                st.success(f"Proyecto {nom} registrado correctamente.")
