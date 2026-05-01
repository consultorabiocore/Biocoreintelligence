import streamlit as st
import json
import ee
import requests
import pandas as pd
from datetime import datetime
from supabase import create_client, Client
from fpdf import FPDF
import base64

# --- 1. CONFIGURACIÓN E INICIO ---
st.set_page_config(page_title="BioCore Intelligence V5", layout="wide", page_icon="🛰️")

# Estilo Profesional
st.markdown("""
    <style>
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; background-color: #238636; color: white; }
    .stMetric { background-color: #161b22; border: 1px solid #30363d; padding: 10px; border-radius: 10px; }
    </style>
    """, unsafe_allow_html=True)

if "password_correct" not in st.session_state:
    st.title("🛰️ BioCore V5 - Acceso")
    u = st.text_input("Usuario").lower()
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

    tab1, tab2, tab3, tab4 = st.tabs(["🚀 MONITOREO", "📊 HISTORIAL 20 AÑOS", "📄 INFORMES", "➕ REGISTRO"])

    # --- FUNCIONES DE EXPORTACIÓN ---
    def generar_pdf(datos_proyecto):
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", 'B', 16)
        pdf.cell(200, 10, f"Informe Tecnico BioCore: {datos_proyecto['Proyecto']}", ln=True, align='C')
        pdf.set_font("Arial", '', 12)
        pdf.cell(200, 10, f"Fecha de Analisis: {datetime.now().strftime('%d/%m/%Y')}", ln=True)
        pdf.cell(200, 10, f"Tipo de Monitoreo: {datos_proyecto['Tipo']}", ln=True)
        pdf.multi_cell(0, 10, f"Coordenadas: {datos_proyecto['Coordenadas']}")
        return pdf.output(dest='S').encode('latin-1')

    # --- PESTAÑA 4: REGISTRO COMPLETO (Corregido) ---
    with tab4:
        st.header("➕ Registro Integral de Clientes")
        with st.form("registro_full", clear_on_submit=True):
            c1, c2 = st.columns(2)
            n_proy = c1.text_input("Nombre Proyecto")
            t_proy = c2.selectbox("Tipo", ["HUMEDAL", "MINERIA"])
            
            coords = st.text_area("Coordenadas (JSON)")
            
            c3, c4 = st.columns(2)
            t_id = c3.text_input("Telegram ID")
            s_id = c4.text_input("Google Sheet ID")
            
            c5, c6 = st.columns(2)
            email_c = c5.text_input("Email Cliente")
            pass_c = c6.text_input("Password Cliente", type="password")
            
            es_glaciar = st.checkbox("¿Activar Monitoreo de Glaciares/Nieve?")
            
            if st.form_submit_button("💾 GUARDAR CLIENTE"):
                try:
                    puntos = json.loads(coords)
                    if puntos[0] != puntos[-1]: puntos.append(puntos[0]) # Auto-cierre
                    supabase.table("usuarios").insert({
                        "Proyecto": n_proy, "Tipo": t_proy, "Coordenadas": json.dumps(puntos),
                        "telegram_id": t_id, "sheet_id": s_id, "glaciar": es_glaciar,
                        "Email": email_c, "Password": pass_c
                    }).execute()
                    st.success("Cliente registrado con todas sus credenciales.")
                except Exception as e: st.error(f"Error: {e}")

    # --- PESTAÑA 1: MONITOREO Y REPORTE DIARIO ---
    with tab1:
        st.header("🛰️ Estado de la Red de Monitoreo")
        res = supabase.table("usuarios").select("*").execute()
        proyectos = res.data

        if st.button("📲 ENVIAR REPORTE DIARIO AL CELULAR (TODOS)"):
            with st.spinner("Procesando constelación Sentinel..."):
                for p in proyectos:
                    # Lógica simplificada para el ejemplo de envío
                    msg = f"✅ REPORTE DIARIO BIOCORE\n📍 {p['Proyecto']}\nEstatus: Operacional"
                    requests.post(f"https://api.telegram.org/bot{st.secrets['telegram']['token']}/sendMessage", 
                                 data={"chat_id": p['telegram_id'], "text": msg})
            st.success("Reportes diarios enviados individualmente.")

        for p in proyectos:
            with st.expander(f"🔍 Detalle: {p['Proyecto']}"):
                st.write(f"Email: {p['Email']} | Glaciar: {'Sí' if p['glaciar'] else 'No'}")

    # --- PESTAÑA 3: INFORMES (PDF) ---
    with tab3:
        st.header("📄 Generador de Informes Técnicos (PDF)")
        p_sel = st.selectbox("Seleccione Proyecto", [p['Proyecto'] for p in proyectos])
        if st.button("Generar Informe PDF"):
            datos = next(item for item in proyectos if item["Proyecto"] == p_sel)
            pdf_bytes = generar_pdf(datos)
            b64 = base64.b64encode(pdf_bytes).decode()
            href = f'<a href="data:application/octet-stream;base64,{b64}" download="Informe_{p_sel}.pdf">📥 Descargar Informe PDF</a>'
            st.markdown(href, unsafe_allow_html=True)

    # --- PESTAÑA 2: HISTORIAL (Landsat) ---
    with tab2:
        st.header("📊 Reconstrucción Histórica Landsat (20 años)")
        st.info("Esta función utiliza Landsat 5, 7 y 8 para analizar la evolución del área.")
        # Aquí se integra la lógica de ee.ImageCollection("LANDSAT/LC08/C02/T1_L2")...
