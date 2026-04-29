import streamlit as st
import pandas as pd
import ee
import json
from datetime import datetime
from fpdf import FPDF
from supabase import create_client, Client

# --- 1. CONFIGURACIÓN E INICIALIZACIÓN ---
st.set_page_config(page_title="BioCore Intelligence", layout="wide")

# Inicializar Supabase
url: str = st.secrets["connections"]["supabase"]["url"]
key: str = st.secrets["connections"]["supabase"]["key"]
supabase: Client = create_client(url, key)

# Inicializar Google Earth Engine
def init_gee():
    try:
        gee_json = json.loads(st.secrets["gee"]["json"])
        credentials = ee.ServiceAccountCredentials(gee_json['client_email'], key_data=gee_json['private_key'])
        ee.Initialize(credentials, project=gee_json['project_id'])
        return True
    except Exception as e:
        st.error(f"Error GEE: {e}")
        return False

# --- 2. INTERFAZ ---
st.title("🌿 BioCore Intelligence")

with st.sidebar:
    st.header("Acceso")
    with st.form("login"):
        email_in = st.text_input("Email").strip().lower()
        pass_in = st.text_input("Contraseña", type="password").strip()
        submit = st.form_submit_button("Ingresar")

if submit:
    # CONSULTA A SUPABASE (En lugar de Excel)
    # Asumo que tu tabla se llama 'usuarios'
    try:
        response = supabase.table("usuarios").select("*").eq("Email", email_in).execute()
        usuarios = response.data

        if len(usuarios) > 0:
            user_data = usuarios[0]
            # Validar Contraseña
            if str(user_data['Password']).strip() == pass_in:
                st.session_state.auth = True
                st.session_state.user = user_data
                st.rerun()
            else:
                st.error("Contraseña incorrecta")
        else:
            st.error("Usuario no encontrado")
    except Exception as e:
        st.error(f"Error de base de datos: {e}")

# --- 3. PANEL DE CONTROL ---
if st.session_state.get('auth'):
    u = st.session_state.user
    st.success(f"✅ Proyecto: {u.get('Proyecto', 'Sin Nombre')}")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Monitoreo Satelital")
        if st.button("🚀 Iniciar Escaneo"):
            if init_gee():
                with st.spinner("Procesando índices..."):
                    # Aquí va tu lógica de ee.ImageCollection
                    st.metric("Vigor Vegetal (SAVI)", "0.48")
                    st.info("Escaneo completado con éxito.")
            
    with col2:
        st.subheader("Mapa y Ubicación")
        st.map()
        st.write(f"**Coordenadas:** {u.get('Coordenadas', 'No definidas')}")

else:
    st.info("Por favor, ingrese sus credenciales en la barra lateral.")
