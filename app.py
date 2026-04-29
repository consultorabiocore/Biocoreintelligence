import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from fpdf import FPDF
import json, base64, requests, io
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
from st_supabase_connection import SupabaseConnection

# --- 1. CONFIGURACIÓN INICIAL ---
st.set_page_config(page_title="BioCore Audit System", layout="wide")

try:
    s_url = st.secrets["connections"]["supabase"]["url"].strip()
    s_key = st.secrets["connections"]["supabase"]["key"].strip()
    st_supabase = st.connection("supabase", type=SupabaseConnection, url=s_url, key=s_key)
except:
    st.error("Error de conexión a la base de datos.")
    st.stop()

# --- 2. FUNCIONES TÉCNICAS (TELEGRAM Y DATOS) ---
def enviar_a_telegram(pdf_bytes, filename, chat_id):
    try:
        token = st.secrets["telegram"]["token"].strip()
        cid = str(chat_id).strip().replace(" ", "")
        url = f"https://api.telegram.org/bot{token}/sendDocument"
        files = {'document': (filename, pdf_bytes, 'application/pdf')}
        data = {'chat_id': cid, 'caption': f"📊 Reporte de Auditoría: {filename}"}
        r = requests.post(url, data=data, files=files, timeout=30)
        return r.status_code == 200
    except:
        return False

def obtener_datos_gsheets(sheet_id, pestaña):
    try:
        creds_dict = json.loads(st.secrets["gee"]["json"])
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        client = gspread.authorize(creds)
        sid = sheet_id.split("/d/")[1].split("/")[0] if "/d/" in sheet_id else sheet_id
        hoja = client.open_by_key(sid).worksheet(pestaña)
        df = pd.DataFrame(hoja.get_all_records())
        df['Fecha'] = pd.to_datetime(df['Fecha'], errors='coerce')
        df = df.dropna(subset=['Fecha']).sort_values('Fecha')
        for c in ["SAVI", "NDWI", "SWIR", "Deficit"]:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors='coerce').interpolate().fillna(0)
        return df
    except:
        return pd.DataFrame()

# --- 3. GENERACIÓN DE PDF ---
class BioCorePDF(FPDF):
    def header(self):
        self.set_fill_color(24, 54, 84)
        self.rect(0, 0, 210, 35, 'F')
        self.set_text_color(255, 255, 255)
        self.set_font("Arial", 'B', 14)
        self.cell(0, 15, "AUDITORÍA DE CUMPLIMIENTO AMBIENTAL", 0, 1, 'C')

def generar_pdf(df, proyecto, umbral):
    pdf = BioCorePDF()
    pdf.add_page()
    pdf.ln(30)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, f"PROYECTO: {proyecto}", 0, 1)
    
    # Gráfico para el PDF
    plt.figure(figsize=(10, 4))
    col = "SAVI" if "SAVI" in df.columns else df.columns[1]
    plt.plot(df['Fecha'], df[col], color='#143654', marker='.')
    plt.grid(True, alpha=0.3)
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=120)
    buf.seek(0)
    with open("temp.png", "wb") as f: f.write(buf.getbuffer())
    
    pdf.image("temp.png", x=15, w=180)
    return pdf.output(dest='S').encode('latin-1')

# --- 4. INTERFAZ (MENÚ LATERAL) ---
menu = st.sidebar.selectbox("MENÚ", ["📊 Auditoría", "⚙️ Gestión de Clientes", "➕ Registrar Nuevo"])

# --- PESTAÑA 1: AUDITORÍA ---
if menu == "📊 Auditoría":
    st.title("🛡️ Ejecución de Auditoría")
    res = st_supabase.table("proyectos").select("*").execute()
    proyectos = res.data
    
    if proyectos:
        sel = st.selectbox("Seleccione Proyecto:", [p['nombre'] for p in proyectos])
        p_info = next(p for p in proyectos if p['nombre'] == sel)
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🚀 1. EJECUTAR"):
                df = obtener_datos_gsheets(p_info["sheet_id"], p_info["pestana"])
                if not df.empty:
                    pdf_bytes = generar_pdf(df, sel, p_info["umbral"])
                    st.session_state['pdf_bytes'] = pdf_bytes
                    st.session_state['pdf_name'] = f"Audit_{sel}.pdf"
                    
                    st.success("Reporte generado.")
                    b64 = base64.b64encode(pdf_bytes).decode()
                    href = f'<a href="data:application/pdf;base64,{b64}" download="{st.session_state["pdf_name"]}" style="text-decoration:none; color:white; background:#183654; padding:10px; border-radius:5px; display:block; text-align:center;">⬇️ DESCARGAR REPORTE</a>'
                    st.markdown(href, unsafe_allow_html=True)
                else:
                    st.error("No hay datos en el Excel.")
        
        with col2:
            if 'pdf_bytes' in st.session_state:
                if st.button("📤 2. ENVIAR A TELEGRAM"):
                    if enviar_a_telegram(st.session_state['pdf_bytes'], st.session_state['pdf_name'], p_info["telegram_id"]):
                        st.success("✅ ¡Enviado!")
                        st.balloons()
    else:
        st.info("No hay proyectos registrados.")

# --- PESTAÑA 2: GESTIÓN ---
elif menu == "⚙️ Gestión de Clientes":
    st.title("⚙️ Administración de Datos")
    res = st_supabase.table("proyectos").select("*").execute()
    df_proy = pd.DataFrame(res.data)
    
    if not df_proy.empty:
        st.write("Datos actuales en la nube:")
        st.dataframe(df_proy[["nombre", "telegram_id", "umbral"]])
        
        proy_edit = st.selectbox("Seleccione proyecto para actualizar:", df_proy["nombre"])
        p_data = df_proy[df_proy["nombre"] == proy_edit].iloc[0]
        
        new_id = st.text_input("Nuevo ID Telegram:", value=str(p_data["telegram_id"]))
        new_umb = st.number_input("Nuevo Umbral:", value=float(p_data["umbral"]))
        
        if st.button("💾 Guardar Cambios"):
            st_supabase.table("proyectos").update({"telegram_id": new_id, "umbral": new_umb}).eq("nombre", proy_edit).execute()
            st.success("Actualizado. Recarga la página.")
            st.cache_resource.clear()
            
        if st.button("🗑️ Eliminar Proyecto"):
            st_supabase.table("proyectos").delete().eq("nombre", proy_edit).execute()
            st.warning("Eliminado.")
            st.cache_resource.clear()

# --- PESTAÑA 3: REGISTRO ---
elif menu == "➕ Registrar Nuevo":
    st.title("➕ Alta de Nuevo Proyecto")
    with st.form("nuevo_p"):
        n = st.text_input("Nombre del Proyecto:")
        s = st.text_input("Google Sheet ID:")
        p = st.text_input("Nombre de la Pestaña (ej: Hoja 1):")
        t = st.text_input("ID Telegram del Cliente:")
        u = st.number_input("Umbral Crítico:", value=0.40)
        
        if st.form_submit_button("✅ Registrar en BioCore"):
            st_supabase.table("proyectos").insert({
                "nombre": n, "sheet_id": s, "pestana": p, "telegram_id": t, "umbral": u
            }).execute()
            st.success("¡Proyecto registrado exitosamente!")
