import streamlit as st
import pandas as pd
import json
import ee
from datetime import datetime
from dateutil.relativedelta import relativedelta
from fpdf import FPDF

# Título siempre visible
st.title("🌿 BioCore Intelligence")

# --- INTENTO DE CONEXIÓN A SHEETS ---
try:
    from streamlit_gsheets import GSheetsConnection
    # Intentamos conectar con el nombre 'gsheets' definido en tus Secrets
    conn = st.connection("gsheets", type=GSheetsConnection)
    df = conn.read()
    conexion_ok = True
except ModuleNotFoundError:
    st.error("Falta instalar la librería: Ejecuta 'pip install st-gsheets-connection'")
    conexion_ok = False
except Exception as e:
    st.error(f"Error de configuración: {e}")
    conexion_ok = False

# --- LOGIN ---
with st.sidebar:
    st.header("Acceso Auditoría")
    with st.form("login_form"):
        email_in = st.text_input("Email").strip().lower()
        pass_in = st.text_input("Contraseña", type="password").strip()
        submit = st.form_submit_button("Ingresar")

if submit and conexion_ok:
    # Limpieza de datos del Excel para asegurar el 'match'
    df['Email_Clean'] = df['Email'].astype(str).str.strip().str.lower()
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
