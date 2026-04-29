import streamlit as st
import pandas as pd
import json
import ee
from datetime import datetime
from dateutil.relativedelta import relativedelta
from fpdf import FPDF

# --- 1. CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="BioCore Intelligence", layout="wide")
st.title("🌿 BioCore Intelligence")

# --- 2. CARGA DE DATOS (URL DIRECTA) ---
# Usamos tu link transformado para que pandas lo lea como CSV
sheet_id = "1x6yAXNNlea3e43rijJu0aqcRpe4oP3BEnzgSgLuG1vU"
url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"

@st.cache_data(ttl=60) # Se actualiza cada minuto
def cargar_datos():
    try:
        return pd.read_csv(url)
    except Exception as e:
        st.error(f"Error al conectar con el Excel: {e}")
        return None

df = cargar_datos()

# --- 3. FUNCIONES TÉCNICAS ---
def inicializar_gee():
    try:
        ee.Initialize()
        return True
    except:
        return False

def crear_pdf(user_data, res):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, f"REPORTE BIOCORE: {user_data['Proyecto']}", ln=True, align="C")
    pdf.ln(10)
    pdf.set_font("Arial", "", 12)
    pdf.cell(0, 10, f"Vigor Vegetal (SAVI): {res['savi']}", ln=True)
    pdf.ln(20)
    pdf.set_font("Arial", "I", 8)
    pdf.multi_cell(0, 5, "NOTA: Reporte referencial basado en teledetección satelital. BioCore (c) 2026.")
    return pdf.output(dest='S').encode('latin-1')

# --- 4. LOGIN ---
if 'auth' not in st.session_state:
    st.session_state.auth = False

with st.sidebar:
    st.header("Acceso Auditoría")
    with st.form("login"):
        in_email = st.text_input("Email").strip().lower()
        in_pass = st.text_input("Password", type="password").strip()
        if st.form_submit_button("Ingresar"):
            if df is not None:
                # Limpiamos columnas del Excel para comparar
                df['Email_C'] = df['Email'].astype(str).str.strip().str.lower()
                user = df[df['Email_C'] == in_email]
                
                if not user.empty and str(user.iloc[0]['Password']).strip() == in_pass:
                    st.session_state.auth = True
                    st.session_state.datos = user.iloc[0].to_dict()
                    st.rerun()
                else:
                    st.error("Credenciales incorrectas")

# --- 5. PANEL DE CONTROL ---
if st.session_state.auth:
    d = st.session_state.datos
    
    # Lógica de Pago
    try:
        inicio = datetime.strptime(str(d['Fecha_Inicio']).strip(), "%d/%m/%Y")
        vence = inicio + relativedelta(months=int(d['Meses_Pagados']))
        al_dia = datetime.now() <= vence
    except:
        al_dia = False
        vence = "Error formato"

    if not al_dia:
        st.error(f"⚠️ SUSCRIPCIÓN VENCIDA (Expiró el {vence.strftime('%d/%m/%Y') if not isinstance(vence, str) else vence})")
    else:
        st.success(f"✅ Proyecto: {d['Proyecto']}")
        
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("📊 Monitoreo")
            if st.button("🚀 Escaneo Satelital"):
                with st.spinner("Procesando..."):
                    # Resultados simulados (ajustar con lógica ee)
                    res = {"savi": 0.45, "temp": 22.1}
                    st.metric("Vigor Vegetal", res["savi"])
                    
                    pdf_bytes = crear_pdf(d, res)
                    st.download_button("📥 Descargar PDF", pdf_bytes, "Reporte_BioCore.pdf")
        
        with col2:
            st.subheader("📍 Ubicación")
            st.map()
            st.caption(f"Tipo: {d['Tipo']} | Coordenadas: {d['Coordenadas']}")

else:
    st.info("Ingresa tus credenciales en la barra lateral.")
    df['Pass_Clean'] = df['Password'].astype(str).str.strip()

    usuario = df[df['Email_Clean'] == email_in]

    if not usuario.empty:
        if str(usuario.iloc[0]['Pass_Clean']) == pass_in:
            st.session_state.autenticado = True
            st.session_state.user_data = usuario.iloc[0].to_dict()
            st.rerun()
        else:
            st.error("Contraseña incorrecta.")
    else:
        st.error(f"El correo '{email_in}' no existe en la base de datos.")

# --- PANEL PRINCIPAL ---
if st.session_state.get('autenticado'):
    u = st.session_state.user_data
    st.success(f"✅ Proyecto: {u['Proyecto']}")
    
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Estado de Cuenta")
        try:
            inicio = datetime.strptime(str(u['Fecha_Inicio']).strip(), "%d/%m/%Y")
            vence = inicio + relativedelta(months=int(u['Meses_Pagados']))
            if datetime.now() > vence:
                st.error(f"Suscripción VENCIDA el {vence.strftime('%d/%m/%Y')}")
            else:
                st.info(f"Suscripción activa hasta {vence.strftime('%d/%m/%Y')}")
                if st.button("🚀 Iniciar Análisis"):
                    st.metric("Vigor Vegetal", "0.45")
        except:
            st.warning("Error en formato de fecha del Excel (usa DD/MM/AAAA)")
    
    with col2:
        st.subheader("Mapa")
        st.map()
