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

# Conexión a Supabase (Gestión de Clientes)
try:
    s_url = st.secrets["connections"]["supabase"]["url"].strip()
    s_key = st.secrets["connections"]["supabase"]["key"].strip()
    st_supabase = st.connection("supabase", type=SupabaseConnection, url=s_url, key=s_key)
except:
    st.error("Error: Conexión con base de datos fallida.")
    st.stop()

# --- 2. FUNCIONES DE TELEGRAM (Lógica que funcionaba ayer) ---
def enviar_a_telegram(pdf_bytes, filename, chat_id):
    try:
        # Usamos el nuevo token de BotFather que me pasaste
        token = st.secrets["telegram"]["token"].strip()
        # Limpiamos el ID: fundamental que sea 6712325113
        cid = str(chat_id).strip().replace(" ", "")
        
        url = f"https://api.telegram.org/bot{token}/sendDocument"
        files = {'document': (filename, pdf_bytes, 'application/pdf')}
        data = {'chat_id': cid, 'caption': f"📊 Reporte BioCore: {filename}"}
        
        r = requests.post(url, data=data, files=files, timeout=30)
        
        if r.status_code == 200:
            return True
        else:
            st.error(f"Telegram dice: {r.text}") # Esto nos dirá el error exacto
            return False
    except:
        return False

# --- 3. PROCESAMIENTO DE DATOS (Tu lógica original) ---
def obtener_datos(sheet_id, pestaña):
    try:
        creds_dict = json.loads(st.secrets["gee"]["json"])
        SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        CREDS = Credentials.from_service_account_info(creds_dict, scopes=SCOPE)
        client = gspread.authorize(CREDS)
        
        sid = sheet_id.split("/d/")[1].split("/")[0] if "/d/" in sheet_id else sheet_id
        hoja = client.open_by_key(sid).worksheet(pestaña)
        df = pd.DataFrame(hoja.get_all_records())
        
        # Limpieza de columnas exacta a tu código anterior
        df['Fecha'] = pd.to_datetime(df['Fecha'], errors='coerce')
        df = df.dropna(subset=['Fecha']).sort_values('Fecha')
        
        cols_interes = ["SAVI", "NDWI", "SWIR", "Arcillas", "Deficit"]
        presentes = [c for c in cols_interes if c in df.columns]
        for c in presentes:
            df[c] = pd.to_numeric(df[c], errors='coerce').interpolate().fillna(0)
        return df, presentes
    except:
        return pd.DataFrame(), []

# --- 4. MOTOR DE GRÁFICOS Y PDF ---
def crear_graficos_audit(df, columnas):
    fig, axs = plt.subplots(len(columnas), 1, figsize=(10, 3 * len(columnas)))
    if len(columnas) == 1: axs = [axs]
    colores = {"SAVI": "#143654", "NDWI": "#2E7D32", "SWIR": "#555555", "Deficit": "#C62828"}
    for i, col in enumerate(columnas):
        axs[i].plot(df['Fecha'], df[col], marker='.', color=colores.get(col, "black"), linewidth=1)
        axs[i].set_title(f"MONITOREO: {col}", fontsize=10, fontweight='bold', loc='left')
        axs[i].grid(True, linestyle=':', alpha=0.5)
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150)
    buf.seek(0)
    return buf

class BioCorePDF(FPDF):
    def header(self):
        self.set_fill_color(24, 54, 84)
        self.rect(0, 0, 210, 35, 'F')
        self.set_text_color(255, 255, 255)
        self.set_font("Arial", 'B', 14)
        self.cell(0, 15, "AUDITORÍA DE CUMPLIMIENTO AMBIENTAL", 0, 1, 'C')
        self.set_font("Arial", 'I', 9)
        self.cell(0, 5, "BioCore Intelligence | Loreto Campos Carrasco", 0, 1, 'C')

def generar_pdf_final(df, proyecto, columnas, umbral):
    val_ref = df[columnas[0]].iloc[-1] if columnas else 0
    alerta = val_ref < umbral
    pdf = BioCorePDF()
    pdf.add_page()
    pdf.ln(25)
    pdf.set_fill_color(200, 0, 0) if alerta else pdf.set_fill_color(0, 100, 0)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, f"  ESTATUS: {'ALERTA TÉCNICA' if alerta else 'CUMPLIMIENTO'}", 0, 1, 'L', True)
    pdf.ln(5); pdf.set_text_color(0,0,0)
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(0, 10, f"DIAGNÓSTICO: {proyecto}", 0, 1)
    pdf.multi_cell(0, 7, f"El valor de {columnas[0]} es {val_ref:.4f}. Umbral: {umbral}.", border=1)
    
    # Agregar gráficos
    pdf.add_page()
    pdf.ln(20)
    g_buf = crear_graficos_audit(df, columnas)
    with open("temp.png", "wb") as f: f.write(g_buf.getbuffer())
    pdf.image("temp.png", x=15, w=180)
    return pdf.output(dest='S').encode('latin-1')

# --- 5. INTERFAZ ---
st.title("🛡️ BioCore Intelligence | Sistema de Auditoría")

res = st_supabase.table("proyectos").select("*").execute()
proyectos_db = res.data

if proyectos_db:
    sel = st.selectbox("Seleccione Proyecto:", [p['nombre'] for p in proyectos_db])
    p_info = next(p for p in proyectos_db if p['nombre'] == sel)

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🚀 EJECUTAR AUDITORÍA"):
            with st.spinner("Cargando datos..."):
                df_data, cols_data = obtener_datos(p_info["sheet_id"], p_info["pestana"])
                if not df_data.empty:
                    pdf_bytes = generar_pdf_final(df_data, sel, cols_data, p_info["umbral"])
                    st.session_state['pdf_bytes'] = pdf_bytes
                    st.session_state['pdf_name'] = f"Audit_{sel}.pdf"
                    
                    st.image(crear_graficos_audit(df_data, cols_data))
                    b64 = base64.b64encode(pdf_bytes).decode()
                    href = f'<a href="data:application/pdf;base64,{b64}" download="{st.session_state["pdf_name"]}" style="display:block; text-align:center; padding:15px; background-color:#183654; color:white; border-radius:5px; text-decoration:none; font-weight:bold;">📄 DESCARGAR REPORTE</a>'
                    st.markdown(href, unsafe_allow_html=True)
                else: st.error("No hay datos.")

    with col2:
        if 'pdf_bytes' in st.session_state:
            st.info(f"Reporte listo para ID: {p_info['telegram_id']}")
            if st.button("📤 ENVIAR A TELEGRAM"):
                if enviar_a_telegram(st.session_state['pdf_bytes'], st.session_state['pdf_name'], p_info["telegram_id"]):
                    st.success("✅ ¡Enviado!")
                    st.balloons()
                else: st.error("Error al enviar. Revisa el ID.")
else: st.warning("Registra un proyecto.")
