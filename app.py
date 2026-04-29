import streamlit as st
import pandas as pd
import json
import ee
from datetime import datetime
from dateutil.relativedelta import relativedelta
from fpdf import FPDF

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="BioCore Intelligence", layout="wide")
st.title("🌿 BioCore Intelligence")

# --- 2. CONEXIÓN A GOOGLE SHEETS (IMPORTANTE) ---
# Asegúrate de que tu conexión se llame 'gsheets' en Secrets
try:
    from streamlit_gsheets import GSheetsConnection
    conn = st.connection("gsheets", type=GSheetsConnection)
    df = conn.read()
except Exception as e:
    st.error(f"Error de conexión con Excel: {e}")
    df = pd.DataFrame() # Evita que la app colapse si no hay conexión

# --- 3. BARRA LATERAL Y LOGIN ---
with st.sidebar:
    st.header("Acceso de Auditoría")
    with st.form("login_form"):
        email_in = st.text_input("Email Corporativo").strip().lower()
        pass_in = st.text_input("Contraseña", type="password").strip()
        submit = st.form_submit_button("Ingresar")

# --- 4. LÓGICA DE VALIDACIÓN ---
if submit:
    if not df.empty:
        # Limpieza total: quitamos espacios y pasamos a minúsculas las columnas del Excel
        df['Email_Clean'] = df['Email'].astype(str).str.strip().str.lower()
        df['Pass_Clean'] = df['Password'].astype(str).str.strip()

        # Buscamos al usuario
        usuario = df[df['Email_Clean'] == email_in]

        if not usuario.empty:
            if str(usuario.iloc[0]['Pass_Clean']) == pass_in:
                st.session_state.autenticado = True
                st.session_state.user_data = usuario.iloc[0].to_dict()
                st.rerun()
            else:
                st.error("❌ Contraseña incorrecta.")
        else:
            st.error(f"❌ El correo '{email_in}' no existe en el Excel.")
            st.info("Asegúrate de que en la Columna A del Excel el correo esté completo.")
    else:
        st.error("No se pudo leer la base de datos de Google Sheets.")

# --- 5. PANEL PRINCIPAL (Solo si entró) ---
if st.session_state.get('autenticado'):
    u = st.session_state.user_data
    st.success(f"✅ Conectado a: {u['Proyecto']}")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Análisis de Datos")
        # Aquí verificamos la fecha de inicio (Columna H) y meses (Columna I)
        try:
            inicio = datetime.strptime(str(u['Fecha_Inicio']).strip(), "%d/%m/%Y")
            vence = inicio + relativedelta(months=int(u['Meses_Pagados']))
            
            if datetime.now() > vence:
                st.error(f"Suscripción Vencida el {vence.strftime('%d/%m/%Y')}")
            else:
                st.info(f"Suscripción válida hasta: {vence.strftime('%d/%m/%Y')}")
                if st.button("🚀 Ejecutar Escaneo"):
                    st.metric("Vigor Vegetal (SAVI)", "0.45")
                    st.write("Generando reporte...")
        except:
            st.warning("Revisa el formato de fecha (DD/MM/AAAA) en tu Excel.")

    with col2:
        st.subheader("Mapa del Proyecto")
        st.map()
else:
    st.info("Ingresa tus datos para ver el panel de monitoreo.")
