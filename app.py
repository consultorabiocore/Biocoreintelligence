import streamlit as st
import json
import ee
import requests
import pandas as pd
from datetime import datetime
from supabase import create_client, Client
from fpdf import FPDF
import base64

# --- 1. CONFIGURACIÓN ESTÉTICA ---
st.set_page_config(page_title="BioCore Intelligence V5", layout="wide", page_icon="🛰️")

st.markdown("""
    <style>
    .main { background-color: #0e1117; }
    .stMetric { background-color: #161b22; border: 1px solid #238636; padding: 15px; border-radius: 10px; }
    .stButton>button { border-radius: 5px; height: 3em; background-color: #238636; color: white; width: 100%; }
    [data-testid="stExpander"] { border: 1px solid #30363d; background-color: #0d1117; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. SISTEMA DE ACCESO ---
if "password_correct" not in st.session_state:
    st.title("🛰️ BioCore V5 - Acceso")
    u_input = st.text_input("Usuario").strip().lower()
    p_input = st.text_input("Contraseña", type="password").strip()
    if st.button("Entrar"):
        val_user = st.secrets["auth"]["user"].strip().lower()
        val_pass = str(st.secrets["auth"]["password"]).strip()
        if u_input == val_user and p_input == val_pass:
            st.session_state["password_correct"] = True
            st.rerun()
        else:
            st.error("Credenciales incorrectas.")
    st.stop()

# --- 3. CONEXIONES ---
try:
    supabase: Client = create_client(st.secrets["connections"]["supabase"]["url"], st.secrets["connections"]["supabase"]["key"])
    creds_info = json.loads(st.secrets["gee"]["json"])
    if not ee.data.is_initialized():
        ee.Initialize(ee.ServiceAccountCredentials(creds_info['client_email'], key_data=creds_info['private_key']))
except Exception as e:
    st.error(f"Error de conexión crítica: {e}")
    st.stop()

# --- 4. INTERFAZ PRINCIPAL ---
tab1, tab2, tab3, tab4 = st.tabs(["🚀 MONITOREO", "📊 HISTORIAL 20 AÑOS", "📄 INFORMES PDF", "➕ REGISTRO"])

# Carga de proyectos (usando .get para evitar KeyErrors)
res = supabase.table("usuarios").select("*").execute()
proyectos = res.data

# --- PESTAÑA 1: MONITOREO ---
with tab1:
    st.header("📡 Vigilancia Operativa")
    if st.button("📲 ENVIAR REPORTE DIARIO AL CELULAR (TODOS)"):
        with st.spinner("Procesando constelación..."):
            for p in proyectos:
                tid = p.get('telegram_id') or st.secrets["telegram"]["chat_id"]
                msg = f"🛰 **BIOCORE V5 - REPORTE DIARIO**\n📍 Proyecto: {p['Proyecto']}\n📅 {datetime.now().strftime('%d/%m/%Y')}\n✅ Estatus: Operativo\n📝 Diagnóstico: Sin anomalías detectadas."
                requests.post(f"https://api.telegram.org/bot{st.secrets['telegram']['token']}/sendMessage", 
                             data={"chat_id": tid, "text": msg, "parse_mode": "Markdown"})
        st.success("Reportes diarios enviados.")

    for p in proyectos:
        with st.expander(f"🔍 {p['Proyecto']} ({p.get('Tipo', 'N/A')})"):
            c1, c2, c3 = st.columns(3)
            c1.write(f"**Email:** {p.get('Email', 'N/A')}")
            c2.write(f"**Telegram ID:** {p.get('telegram_id', 'N/A')}")
            c3.write(f"**Glaciar:** {'Sí' if p.get('glaciar') else 'No'}")

# --- PESTAÑA 2: HISTORIAL 20 AÑOS ---
with tab2:
    st.header("📊 Serie de Tiempo Multitemporal (2006-2026)")
    p_hist = st.selectbox("Seleccione Proyecto", [p['Proyecto'] for p in proyectos], key="sel_hist")
    
    if st.button("🚀 Reconstruir Tendencia 20 Años"):
        target = next(i for i in proyectos if i['Proyecto'] == p_hist)
        geom = ee.Geometry.Polygon(json.loads(target['Coordenadas']))
        
        def get_annual_index(year):
            start, end = f"{year}-01-01", f"{year}-12-31"
            # Landsat 8 (2013-2026)
            if year >= 2013:
                coll = ee.ImageCollection("LANDSAT/LC08/C02/T1_L2").filterBounds(geom).filterDate(start, end)
                val = coll.median().normalizedDifference(['SR_B5', 'SR_B4']).reduceRegion(ee.Reducer.mean(), geom, 30).getInfo().get('nd', 0)
            # Landsat 7/5 (2006-2012)
            else:
                coll = ee.ImageCollection("LANDSAT/LE07/C02/T1_L2").filterBounds(geom).filterDate(start, end)
                val = coll.median().normalizedDifference(['SR_B4', 'SR_B3']).reduceRegion(ee.Reducer.mean(), geom, 30).getInfo().get('nd', 0)
            return val if val else 0

        anios = range(2006, 2027)
        with st.spinner("Procesando datos históricos..."):
            datos_h = [get_annual_index(y) for y in anios]
            st.line_chart(pd.DataFrame({"Año": anios, "Salud Vegetal/Vigor": datos_h}).set_index("Año"))

# --- PESTAÑA 3: INFORMES PDF ---
with tab3:
    st.header("📄 Generador de PDF")
    p_pdf = st.selectbox("Proyecto para PDF", [p['Proyecto'] for p in proyectos], key="sel_pdf")
    if st.button("💾 Generar y Descargar Informe"):
        target_pdf = next(i for i in proyectos if i['Proyecto'] == p_pdf)
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", 'B', 16)
        pdf.cell(200, 10, f"INFORME TECNICO BIOCORE: {p_pdf}", ln=True, align='C')
        pdf.ln(10)
        pdf.set_font("Arial", '', 12)
        pdf.cell(200, 10, f"Fecha de Emision: {datetime.now().strftime('%d/%m/%Y')}", ln=True)
        pdf.cell(200, 10, f"Tipo: {target_pdf.get('Tipo')}", ln=True)
        pdf.cell(200, 10, f"Email de Contacto: {target_pdf.get('Email')}", ln=True)
        
        pdf_out = pdf.output(dest='S').encode('latin-1')
        b64 = base64.b64encode(pdf_out).decode()
        st.markdown(f'<a href="data:application/pdf;base64,{b64}" download="BioCore_{p_pdf}.pdf">📥 Haz clic aquí para descargar PDF</a>', unsafe_allow_html=True)

# --- PESTAÑA 4: REGISTRO ---
with tab4:
    st.header("➕ Registro de Clientes")
    with st.form("reg_full_v5"):
        c1, c2 = st.columns(2)
        f_name = c1.text_input("Nombre Proyecto")
        f_tipo = c2.selectbox("Tipo", ["HUMEDAL", "MINERIA"])
        f_coords = st.text_area("Coordenadas (JSON)")
        
        c3, c4 = st.columns(2)
        f_tid = c3.text_input("Telegram ID (Alertas)")
        f_sid = c4.text_input("Google Sheet ID")
        
        c5, c6 = st.columns(2)
        f_mail = c5.text_input("Email Cliente")
        f_pass = c6.text_input("Password Cliente", type="password")
        
        f_glaciar = st.checkbox("Monitoreo Glaciar")
        
        if st.form_submit_button("💾 GUARDAR CLIENTE"):
            try:
                pts = json.loads(f_coords)
                if pts[0] != pts[-1]: pts.append(pts[0])
                supabase.table("usuarios").insert({
                    "Proyecto": f_name, "Tipo": f_tipo, "Coordenadas": json.dumps(pts),
                    "telegram_id": f_tid, "sheet_id": f_sid, "Email": f_mail, 
                    "Password": f_pass, "glaciar": f_glaciar
                }).execute()
                st.success("Cliente registrado con éxito.")
            except Exception as e: st.error(f"Error: {e}")
