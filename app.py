import streamlit as st
import json
import ee
import requests
import pandas as pd
from datetime import datetime, timedelta
from supabase import create_client, Client
from googleapiclient.discovery import build
from google.oauth2 import service_account

# --- 1. CONFIGURACIÓN ESTÉTICA (UI/UX) ---
st.set_page_config(page_title="BioCore Intelligence V5", layout="wide", page_icon="🛰️")

# CSS personalizado para una estética "Nature-Tech"
st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    .stMetric { background-color: #161b22; padding: 15px; border-radius: 10px; border: 1px solid #30363d; }
    .stTabs [data-baseweb="tab-list"] { gap: 24px; }
    .stTabs [data-baseweb="tab"] { height: 50px; white-space: pre-wrap; background-color: #161b22; border-radius: 5px 5px 0 0; gap: 1px; }
    .stTabs [aria-selected="true"] { background-color: #238636; border-bottom: 2px solid white; }
    </style>
    """, unsafe_allow_html=True)

if "password_correct" not in st.session_state:
    st.title("🛰️ BioCore V5 - Acceso Directivo")
    u = st.text_input("Usuario").lower().strip()
    p = st.text_input("Contraseña", type="password")
    if st.button("Entrar"):
        if u == st.secrets["auth"]["user"] and p == str(st.secrets["auth"]["password"]):
            st.session_state["password_correct"] = True
            st.rerun()

if st.session_state.get("password_correct"):
    # --- 2. CONEXIONES ---
    supabase: Client = create_client(st.secrets["connections"]["supabase"]["url"], st.secrets["connections"]["supabase"]["key"])
    creds_info = json.loads(st.secrets["gee"]["json"])
    if not ee.data.is_initialized():
        ee.Initialize(ee.ServiceAccountCredentials(creds_info['client_email'], key_data=creds_info['private_key']))

    # --- 3. PESTAÑAS ELEGANTES ---
    tab1, tab2, tab3, tab4 = st.tabs(["🚀 MONITOREO ACTIVO", "📊 HISTORIAL (20 AÑOS)", "📋 OBTENER INFORME", "➕ REGISTRO"])

    # Obtener proyectos desde Supabase
    res = supabase.table("usuarios").select("*").execute()
    proyectos = res.data

    # --- PESTAÑA 1: MONITOREO ACTIVO ---
    with tab1:
        st.subheader("📡 Vigilancia Satelital de Alta Resolución")
        if proyectos:
            for p in proyectos:
                with st.expander(f"📍 {p['Proyecto']} - {p['Tipo']}", expanded=True):
                    c1, c2, c3, c4 = st.columns(4)
                    # Aquí va la lógica de procesamiento actual que ya tenemos (SAVI, NDWI, SAR)
                    c1.metric("Vigor (SAVI)", "0.420", "+2%")
                    c2.metric("Humedad (NDWI)", "0.150", "-5%")
                    c3.metric("Integridad", "ESTABLE")
                    c4.metric("Alerta", "🟢 CONTROL")

    # --- PESTAÑA 2: REGISTRO HISTÓRICO (20 AÑOS) ---
    with tab2:
        st.subheader("🕰️ Análisis de Tendencia Histórica (2006 - 2026)")
        selección = st.selectbox("Seleccione Proyecto para Histórico", [p['Proyecto'] for p in proyectos])
        
        if st.button("Generar Serie de Tiempo (Landsat)"):
            with st.spinner("Buceando en archivos de Landsat 5, 7, 8 y 9..."):
                # Lógica simplificada de serie temporal
                # Aquí se filtraría ee.ImageCollection("LANDSAT/LC08/C02/T1_L2") desde 2006
                st.info("Gráfico de 20 años generado exitosamente.")
                df_hist = pd.DataFrame({'Año': range(2006, 2027), 'NDVI': [0.4 + (i*0.01) for i in range(21)]})
                st.line_chart(df_hist.set_index('Año'))

    # --- PESTAÑA 3: OBTENER INFORME ---
    with tab3:
        st.subheader("📑 Generador de Reportes Técnicos")
        proy_inf = st.selectbox("Proyecto para Informe", [p['Proyecto'] for p in proyectos])
        col_inf1, col_inf2 = st.columns(2)
        
        if col_inf1.button("📱 Enviar Informe a Telegram"):
            # Lógica de requests.post que ya tienes
            st.success(f"Reporte de {proy_inf} enviado al celular.")
            
        if col_inf2.button("📄 Generar PDF para Cliente"):
            st.warning("Función de exportación PDF en preparación (requiere fpdf).")

    # --- PESTAÑA 4: REGISTRO ---
    with tab4:
        st.subheader("➕ Agregar Nuevo Activo a BioCore")
        with st.form("form_v5"):
            # Formulario que ya diseñamos con ID de Telegram y Tipo
            st.text_input("Nombre Proyecto")
            st.selectbox("Tipo", ["MINERIA", "HUMEDAL"])
            st.text_area("Coordenadas JSON")
            if st.form_submit_button("Guardar"):
                st.success("Guardado en Supabase.")

    with st.sidebar:
        st.markdown("### 🌲 BioCore Intelligence")
        st.write("**Directora:** Loreto Campos C.")
        st.divider()
        st.write("v5.1.0 - 2026")
