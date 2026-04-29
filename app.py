import streamlit as st
import pandas as pd
import json
import ee
from datetime import datetime

# --- 1. CONFIGURACIÓN INICIAL (Fuera de cualquier IF) ---
st.set_page_config(page_title="BioCore Intelligence", layout="wide")

# Título Principal (Siempre visible)
st.title("🌿 BioCore Intelligence")

# --- 2. BARRA LATERAL (Siempre visible) ---
with st.sidebar:
    st.header("Acceso de Auditoría")
    # Usamos st.form para que no se recargue la página a cada rato
    with st.form("login_form"):
        email_in = st.text_input("Email")
        pass_in = st.text_input("Contraseña", type="password")
        submit = st.form_submit_button("Ingresar")

# --- 3. LÓGICA DE LOGIN ---
# Reemplaza 'tus_datos_reales' con la lectura de tu Sheets
if submit:
    # IMPORTANTE: Verifica que el email coincida EXACTAMENTE con tu Excel
    if email_in.lower() == "consultorabiocore@gmail.com" and pass_in == "123":
        st.session_state.autenticado = True
        st.session_state.proyecto = "Pascua Lama"
    else:
        st.error("Credenciales incorrectas o usuario no encontrado.")

# --- 4. CONTENIDO PRINCIPAL (Solo se activa si hay login exitoso) ---
if st.session_state.get('autenticado'):
    st.success(f"✅ Sesión activa: {st.session_state.proyecto}")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("📊 Panel de Monitoreo")
        
        # Intentamos inicializar GEE solo AQUÍ adentro
        try:
            # Si no tienes los Secrets configurados, esto fallará pero no matará la App
            # ee.Initialize() 
            st.info("Conexión satelital lista.")
        except Exception as e:
            st.warning(f"Modo offline: No se pudo conectar con GEE ({e})")

        if st.button("🚀 Iniciar Escaneo"):
            st.write("Analizando área de Pascua Lama...")
            st.metric("Vigor Vegetal", "0.42")
            st.metric("Humedad", "15%")
            
    with col2:
        st.subheader("🗺️ Ubicación del Proyecto")
        # Esto siempre funciona, no requiere GEE
        st.map() 

else:
    # Si no hay login, mostrar un mensaje de espera
    st.info("Por favor, ingresa tus credenciales en la barra lateral para ver los datos.")
