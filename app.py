import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from fpdf import FPDF
import json, base64, requests, io, re
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
from st_supabase_connection import SupabaseConnection

# --- 1. CONFIGURACIÓN E INTERFAZ ---
st.set_page_config(page_title="BioCore Audit System", layout="wide")

# Estilo para botones y métricas
st.markdown("""
    <style>
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; font-weight: bold; }
    .download-btn {
        display: block; width: 100%; text-align: center; background-color: #1a3a5a;
        color: white; padding: 12px; border-radius: 5px; text-decoration: none; font-weight: bold;
    }
    </style>
    """, unsafe_allow_html=True)

# --- 2. CONEXIONES ---
st.cache_resource.clear()

try:
    s_url = st.secrets["connections"]["supabase"]["url"].strip()
    s_key = st.secrets["connections"]["supabase"]["key"].strip()
    st_supabase = st.connection("supabase", type=SupabaseConnection, url=s_url, key=s_key)
except:
    st.error("❌ Error de conexión con Supabase. Revisa tus Secrets.")
    st.stop()

# --- 3. LÓGICA DE DATOS ---
def obtener_datos(sheet_id, pestaña):
    try:
        creds_info = json.loads(st.secrets["gee"]["json"])
        creds = Credentials.from_service_account_info(creds_info, scopes=["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"])
        client = gspread.authorize(creds)
        sid = sheet_id.split("/d/")[1].split("/")[0] if "/d/" in sheet_id else sheet_id
        sh = client.open_by_key(sid).worksheet(pestaña)
        df = pd.DataFrame(sh.get_all_records())
        
        # Limpieza de nombres y tipos
        df.columns = [c.strip() for c in df.columns]
        if 'Fecha' in df.columns:
            df['Fecha'] = pd.to_datetime(df['Fecha'], dayfirst=True, errors='coerce')
            df = df.dropna(subset=['Fecha']).sort_values('Fecha')
        
        indices = [c for c in ["SAVI", "NDWI", "NDSI", "Deficit"] if c in df.columns]
        for c in indices:
            df[c] = pd.to_numeric(df[c], errors='coerce').interpolate().fillna(0)
        return df, indices
    except: return pd.DataFrame(), []

# --- 4. MOTOR DE REPORTES PDF ---
class BioCorePDF(FPDF):
    def header(self):
        self.set_fill_color(24, 54, 84) 
        self.rect(0, 0, 210, 35, 'F')
        self.set_text_color(255, 255, 255)
        self.set_font("Arial", 'B', 14)
        self.cell(0, 15, "AUDITORÍA DE CUMPLIMIENTO AMBIENTAL", 0, 1, 'C')
        self.set_font("Arial", 'I', 9)
        self.cell(0, 5, "BioCore Intelligence | Loreto Campos Carrasco", 0, 1, 'C')

def generar_pdf(df, proyecto, columnas, umbral):
    pdf = BioCorePDF()
    pdf.add_page()
    pdf.ln(25)
    
    val_ref = df[columnas[0]].iloc[-1] if columnas else 0
    alerta = val_ref < umbral
    
    # Cuadro de Estatus
    pdf.set_fill_color(200, 0, 0) if alerta else pdf.set_fill_color(0, 100, 0)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 12, f"  ESTATUS: {'ALERTA TÉCNICA' if alerta else 'CUMPLIMIENTO NORMAL'}", 0, 1, 'L', True)
    
    pdf.ln(10)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, f"INFORME: {proyecto}", 0, 1)
    pdf.set_font("Arial", size=11)
    pdf.multi_cell(0, 8, f"Hallazgo: El índice {columnas[0]} registra un valor de {val_ref:.4f}. Umbral de control: {umbral}.", border=1)
    
    # Gráfico
    plt.figure(figsize=(10, 5))
    plt.plot(df['Fecha'], df[columnas[0]], color='#143654', marker='o')
    plt.title(f"Histórico {columnas[0]}")
    plt.grid(True, alpha=0.3)
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150)
    buf.seek(0)
    with open("temp_plot.png", "wb") as f: f.write(buf.getbuffer())
    
    pdf.add_page()
    pdf.ln(20)
    pdf.image("temp_plot.png", x=15, w=180)
    
    return pdf.output(dest='S').encode('latin-1')

# --- 5. COMUNICACIÓN (TELEGRAM) ---
def enviar_telegram(pdf_bytes, filename, chat_id):
    try:
        token = st.secrets["telegram"]["token"]
        url = f"https://api.telegram.org/bot{token}/sendDocument"
        files = {'document': (filename, pdf_bytes, 'application/pdf')}
        data = {'chat_id': chat_id, 'caption': f"📊 Reporte de Auditoría: {filename}"}
        r = requests.post(url, data=data, files=files, timeout=20)
        return r.status_code == 200
    except: return False

# --- 6. FLUJO DE LA APP ---
st.title("🛡️ BioCore Intelligence | Gestión de Auditorías")

# Cargar proyectos de Supabase
res = st_supabase.table("proyectos").select("*").execute()
proyectos = res.data

if proyectos:
    sel = st.selectbox("Seleccione Proyecto:", [p['nombre'] for p in proyectos])
    p = next(item for item in proyectos if item['nombre'] == sel)

    col_rev, col_env = st.columns(2)

    with col_rev:
        st.subheader("1. Revisión Técnica")
        if st.button("🔍 GENERAR REPORTE"):
            with st.spinner("Procesando datos..."):
                df_data, cols_data = obtener_datos(p["sheet_id"], p["pestana"])
                if not df_data.empty:
                    pdf_out = generar_pdf(df_data, sel, cols_data, p["umbral"])
                    st.session_state['pdf_bytes'] = pdf_out
                    st.session_state['pdf_name'] = f"Audit_{sel}.pdf"
                    
                    # Botón de Descarga Manual Robusto
                    b64 = base64.b64encode(pdf_out).decode()
                    href = f'<a href="data:application/pdf;base64,{b64}" download="{st.session_state["pdf_name"]}" class="download-btn">⬇️ DESCARGAR PARA REVISIÓN</a>'
                    st.markdown(href, unsafe_allow_html=True)
                    st.success("Reporte generado. Revísalo antes de enviar.")
                else:
                    st.error("Planilla de Google Sheets sin datos válidos.")

    with col_env:
        st.subheader("2. Envío a Cliente")
        if 'pdf_bytes' in st.session_state:
            st.info(f"Reporte listo: {st.session_state['pdf_name']}")
            if st.button("🚀 ENVIAR A TELEGRAM"):
                if enviar_telegram(st.session_state['pdf_bytes'], st.session_state['pdf_name'], p["telegram_id"]):
                    st.success(f"✅ ¡Enviado con éxito al ID {p['telegram_id']}!")
                    st.balloons()
                    del st.session_state['pdf_bytes'] # Limpiar después de enviar
                else:
                    st.error("Error en el envío. ¿El cliente inició el bot?")
        else:
            st.write("Primero genera el reporte para habilitar el envío.")
else:
    st.info("No hay proyectos en la base de datos.")
