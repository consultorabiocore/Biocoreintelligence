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
st.cache_resource.clear()

# Conexión a Base de Datos (Supabase)
try:
    s_url = st.secrets["connections"]["supabase"]["url"].strip()
    s_key = st.secrets["connections"]["supabase"]["key"].strip()
    st_supabase = st.connection("supabase", type=SupabaseConnection, url=s_url, key=s_key)
except:
    st.error("Error crítico: No se pudo conectar a la base de datos de gestión.")
    st.stop()

# --- 2. FUNCIONES DE COMUNICACIÓN (Telegram) ---
def enviar_a_telegram(pdf_bytes, filename, chat_id):
    try:
        token = st.secrets["telegram"]["token"].strip()
        # Limpieza de seguridad para el ID
        cid = str(chat_id).strip().replace(" ", "")
        url = f"https://api.telegram.org/bot{token}/sendDocument"
        
        files = {'document': (filename, pdf_bytes, 'application/pdf')}
        data = {'chat_id': cid, 'caption': f"📊 Reporte de Auditoría: {filename}\nFecha: {datetime.now().strftime('%d/%m/%Y')}"}
        
        r = requests.post(url, data=data, files=files, timeout=30)
        return r.status_code == 200
    except:
        return False

# --- 3. PROCESAMIENTO DE DATOS (Google Sheets) ---
def obtener_datos(sheet_id, pestaña):
    try:
        creds_dict = json.loads(st.secrets["gee"]["json"]) # Usamos tu secreto gee
        SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        CREDS = Credentials.from_service_account_info(creds_dict, scopes=SCOPE)
        client = gspread.authorize(CREDS)
        
        # Limpiamos el ID por si viene la URL completa
        sid = sheet_id.split("/d/")[1].split("/")[0] if "/d/" in sheet_id else sheet_id
        hoja = client.open_by_key(sid).worksheet(pestaña)
        
        df = pd.DataFrame(hoja.get_all_records())
        df.columns = [c.strip() for c in df.columns]
        
        if 'Fecha' in df.columns:
            df['Fecha'] = pd.to_datetime(df['Fecha'], dayfirst=True, errors='coerce')
            df = df.dropna(subset=['Fecha']).sort_values('Fecha')
        
        # Columnas técnicas de BioCore
        cols_tecnicas = ["SAVI", "NDWI", "NDSI", "SWIR", "Arcillas", "Deficit"]
        presentes = [c for c in cols_tecnicas if c in df.columns]
        
        for c in presentes:
            df[c] = pd.to_numeric(df[c], errors='coerce').interpolate().fillna(0)
            
        return df, presentes
    except Exception as e:
        st.error(f"Error leyendo la planilla: {e}")
        return pd.DataFrame(), []

# --- 4. MOTOR DE GRÁFICOS ---
def crear_grafico_png(df, columnas):
    fig, axs = plt.subplots(len(columnas), 1, figsize=(10, 3 * len(columnas)))
    if len(columnas) == 1: axs = [axs]
    
    colores = {"SAVI": "#143654", "NDWI": "#2E7D32", "NDSI": "#C62828", "Deficit": "#555555"}
    
    for i, col in enumerate(columnas):
        axs[i].plot(df['Fecha'], df[col], marker='.', color=colores.get(col, "black"), linewidth=1)
        axs[i].set_title(f"MONITOREO: {col}", fontsize=10, fontweight='bold', loc='left')
        axs[i].grid(True, linestyle=':', alpha=0.5)
    
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150)
    buf.seek(0)
    return buf

# --- 5. REPORTE PDF PROFESIONAL ---
class BioCorePDF(FPDF):
    def header(self):
        self.set_fill_color(24, 54, 84) # Azul Marino BioCore
        self.rect(0, 0, 210, 35, 'F')
        self.set_text_color(255, 255, 255)
        self.set_font("Arial", 'B', 14)
        self.cell(0, 15, "AUDITORÍA DE CUMPLIMIENTO AMBIENTAL", 0, 1, 'C')
        self.set_font("Arial", 'I', 9)
        self.cell(0, 5, "Responsable Técnica: Loreto Campos Carrasco | BioCore Intelligence", 0, 1, 'C')

def generar_pdf_reporte(df, proyecto, columnas, umbral):
    # Usamos el primer índice disponible para la alerta
    val_ref = df[columnas[0]].iloc[-1] if columnas else 0
    es_alerta = val_ref < umbral
    
    pdf = BioCorePDF()
    pdf.add_page()
    pdf.ln(25)
    
    status_txt = "ALERTA TÉCNICA: DESVIACIÓN DETECTADA" if es_alerta else "NORMAL / CUMPLIMIENTO"
    pdf.set_fill_color(200, 0, 0) if es_alerta else pdf.set_fill_color(0, 100, 0)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, f"  ESTATUS: {status_txt}", 0, 1, 'L', True)
    
    pdf.ln(5)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(0, 10, f"DIAGNÓSTICO PROYECTO: {proyecto}", 0, 1)
    pdf.set_font("Arial", size=10)
    
    pdf.multi_cell(0, 7, f"1. HALLAZGO: El valor de {columnas[0]} es {val_ref:.4f}. Umbral: {umbral}.", border=1)
    pdf.multi_cell(0, 7, "2. RIESGO: Posible alteración de parámetros ambientales según RCA.", border=1)

    # Gráficos en página 2
    pdf.add_page()
    pdf.ln(20)
    grafico_buf = crear_grafico_png(df, columnas)
    with open("temp_audit.png", "wb") as f:
        f.write(grafico_buf.getbuffer())
    pdf.image("temp_audit.png", x=15, w=180)
    
    return pdf.output(dest='S').encode('latin-1')

# --- 6. INTERFAZ PRINCIPAL ---
st.title("🛡️ BioCore Intelligence | Sistema de Auditoría")

# Traer proyectos desde Supabase
try:
    res = st_supabase.table("proyectos").select("*").execute()
    proyectos_db = res.data
except:
    proyectos_db = []

if proyectos_db:
    nombres = [p['nombre'] for p in proyectos_db]
    sel = st.selectbox("Seleccione Proyecto:", nombres)
    p_info = next(p for p in proyectos_db if p['nombre'] == sel)

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Paso 1: Generar")
        if st.button("🚀 EJECUTAR AUDITORÍA"):
            with st.spinner("Procesando datos técnicos..."):
                df_data, cols_data = obtener_datos(p_info["sheet_id"], p_info["pestana"])
                
                if not df_data.empty:
                    pdf_bytes = generar_pdf_reporte(df_data, sel, cols_data, p_info["umbral"])
                    st.session_state['pdf_bytes'] = pdf_bytes
                    st.session_state['pdf_name'] = f"Auditoria_{sel}.pdf"
                    
                    # Mostrar vista previa
                    st.image(crear_grafico_png(df_data, cols_data))
                    
                    # Botón de Descarga
                    b64 = base64.b64encode(pdf_bytes).decode()
                    href = f'<a href="data:application/pdf;base64,{b64}" download="{st.session_state["pdf_name"]}" style="display:block; text-align:center; padding:15px; background-color:#183654; color:white; border-radius:5px; text-decoration:none; font-weight:bold;">📄 DESCARGAR PARA REVISIÓN</a>'
                    st.markdown(href, unsafe_allow_html=True)
                else:
                    st.error("No se encontraron datos en el Excel.")

    with col2:
        st.subheader("Paso 2: Enviar")
        if 'pdf_bytes' in st.session_state:
            st.info(f"Reporte listo para ID: {p_info['telegram_id']}")
            if st.button("📤 ENVIAR A TELEGRAM"):
                exito = enviar_a_telegram(st.session_state['pdf_bytes'], st.session_state['pdf_name'], p_info["telegram_id"])
                if exito:
                    st.success("✅ ¡Informe enviado con éxito!")
                    st.balloons()
                else:
                    st.error("Error al enviar. Revisa el ID de Telegram.")
        else:
            st.write("Primero ejecuta la auditoría.")

else:
    st.warning("No hay proyectos registrados. Ve a la pestaña de Gestión.")
