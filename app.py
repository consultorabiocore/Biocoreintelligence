import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from fpdf import FPDF
import json, base64, requests, io, re
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
from st_supabase_connection import SupabaseConnection

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="BioCore Audit System", layout="wide")
st.cache_resource.clear()

try:
    s_url = st.secrets["connections"]["supabase"]["url"].strip()
    s_key = st.secrets["connections"]["supabase"]["key"].strip()
    st_supabase = st.connection("supabase", type=SupabaseConnection, url=s_url, key=s_key)
except:
    st.error("Error de conexión a Base de Datos.")
    st.stop()

# --- 2. FUNCIONES TÉCNICAS ---
def enviar_pdf_telegram(pdf_bytes, filename, chat_id):
    try:
        token = st.secrets["telegram"]["token"].strip()
        url = f"https://api.telegram.org/bot{token}/sendDocument"
        # Limpieza absoluta del ID para evitar errores de formato
        clean_chat_id = str(chat_id).replace(" ", "").strip()
        
        files = {'document': (filename, pdf_bytes, 'application/pdf')}
        data = {'chat_id': clean_chat_id, 'caption': f"📊 Reporte de Auditoría: {datetime.now().strftime('%d/%m/%Y')}"}
        
        r = requests.post(url, data=data, files=files, timeout=30)
        if r.status_code == 200:
            return True
        else:
            st.error(f"Error Telegram ({r.status_code}): {r.text}")
            return False
    except Exception as e:
        st.error(f"Error de red: {e}")
        return False

def obtener_datos(sheet_id, pestaña):
    try:
        creds_info = json.loads(st.secrets["gee"]["json"])
        creds = Credentials.from_service_account_info(creds_info, scopes=["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"])
        client = gspread.authorize(creds)
        sid = sheet_id.split("/d/")[1].split("/")[0] if "/d/" in sheet_id else sheet_id
        hoja = client.open_by_key(sid).worksheet(pestaña)
        df = pd.DataFrame(hoja.get_all_records())
        df.columns = [c.strip() for c in df.columns]
        if 'Fecha' in df.columns:
            df['Fecha'] = pd.to_datetime(df['Fecha'], dayfirst=True, errors='coerce')
            df = df.dropna(subset=['Fecha']).sort_values('Fecha')
        cols = [c for c in ["SAVI", "NDWI", "NDSI", "Deficit"] if c in df.columns]
        for c in cols: df[c] = pd.to_numeric(df[c], errors='coerce').interpolate().fillna(0)
        return df, cols
    except: return pd.DataFrame(), []

class BioCorePDF(FPDF):
    def header(self):
        self.set_fill_color(24, 54, 84) 
        self.rect(0, 0, 210, 35, 'F')
        self.set_text_color(255, 255, 255)
        self.set_font("Arial", 'B', 14)
        self.cell(0, 15, "AUDITORÍA DE CUMPLIMIENTO AMBIENTAL", 0, 1, 'C')
        self.set_font("Arial", 'I', 9)
        self.cell(0, 5, "Responsable Técnica: Loreto Campos | BioCore Intelligence", 0, 1, 'C')

def generar_pdf_bytes(df, proyecto, columnas, umbral):
    pdf = BioCorePDF()
    pdf.add_page()
    pdf.ln(25)
    val_ref = df[columnas[0]].iloc[-1] if columnas else 0
    alerta = val_ref < umbral
    
    pdf.set_fill_color(200, 0, 0) if alerta else pdf.set_fill_color(0, 100, 0)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, f"  ESTATUS: {'ALERTA' if alerta else 'NORMAL'}", 0, 1, 'L', True)
    
    pdf.ln(5)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(0, 10, f"PROYECTO: {proyecto}", 0, 1)
    pdf.set_font("Arial", size=10)
    pdf.multi_cell(0, 7, f"Hallazgo: El índice {columnas[0]} registra {val_ref:.4f}. Umbral: {umbral}.", border=1)
    
    # Gráfico temporal
    plt.figure(figsize=(10, 4))
    plt.plot(df['Fecha'], df[columnas[0]], color='#143654', marker='o')
    plt.grid(True, alpha=0.2)
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=120)
    buf.seek(0)
    with open("temp_audit.png", "wb") as f: f.write(buf.getbuffer())
    
    pdf.add_page()
    pdf.ln(20)
    pdf.image("temp_audit.png", x=15, w=180)
    return pdf.output(dest='S').encode('latin-1')

# --- 3. INTERFAZ ---
st.title("🛡️ BioCore Intelligence | Auditoría v2.0")

res = st_supabase.table("proyectos").select("*").execute()
db_proyectos = res.data

if db_proyectos:
    nombres = [p['nombre'] for p in db_proyectos]
    sel = st.selectbox("Seleccione Proyecto:", nombres)
    p_info = next(p for p in db_proyectos if p['nombre'] == sel)

    c_rev, c_env = st.columns(2)
    
    with c_rev:
        if st.button("📄 1. GENERAR REPORTE"):
            with st.spinner("Leyendo datos..."):
                df_data, cols_data = obtener_datos(p_info["sheet_id"], p_info["pestana"])
                if not df_data.empty:
                    pdf_bytes = generar_pdf_bytes(df_data, sel, cols_data, p_info["umbral"])
                    st.session_state['pdf_actual'] = pdf_bytes
                    st.session_state['nombre_actual'] = f"Audit_{sel}.pdf"
                    
                    # Descarga forzada
                    b64 = base64.b64encode(pdf_bytes).decode()
                    href = f'<a href="data:application/pdf;base64,{b64}" download="{st.session_state["nombre_actual"]}" style="display:block; text-align:center; padding:12px; background:#1a3a5a; color:white; border-radius:5px; text-decoration:none; font-weight:bold;">⬇️ DESCARGAR PARA REVISAR</a>'
                    st.markdown(href, unsafe_allow_html=True)
                else:
                    st.error("Error en Google Sheets.")

    with c_env:
        if 'pdf_actual' in st.session_state:
            st.info(f"Listo para enviar a ID: {p_info['telegram_id']}")
            if st.button("🚀 2. ENVIAR A CLIENTE"):
                if enviar_pdf_telegram(st.session_state['pdf_actual'], st.session_state['nombre_actual'], p_info["telegram_id"]):
                    st.success("✅ ¡Reporte enviado!")
                    st.balloons()
                else:
                    st.error("Error en envío. Revisa el ID y que el bot esté iniciado.")
else:
    st.info("Registra un proyecto en Gestión.")
