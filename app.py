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

res = supabase.table("usuarios").select("*").execute()
proyectos = res.data

# --- PESTAÑA 1: MONITOREO ---
with tab1:
    st.header("📡 Vigilancia Operativa")
    if st.button("📲 ENVIAR REPORTE DIARIO AL CELULAR (TODOS)"):
        with st.spinner("Procesando..."):
            for p in proyectos:
                tid = p.get('telegram_id') or st.secrets["telegram"]["chat_id"]
                msg = f"🛰 **BIOCORE V5**\n📍 Proyecto: {p['Proyecto']}\n📅 {datetime.now().strftime('%d/%m/%Y')}\n✅ Estatus: Operativo"
                requests.post(f"https://api.telegram.org/bot{st.secrets['telegram']['token']}/sendMessage", 
                             data={"chat_id": tid, "text": msg, "parse_mode": "Markdown"})
        st.success("Reportes enviados.")

    for p in proyectos:
        with st.expander(f"🔍 {p['Proyecto']} ({p.get('Tipo', 'N/A')})"):
            c1, c2, c3 = st.columns(3)
            c1.write(f"**Email:** {p.get('Email', 'N/A')}")
            c2.write(f"**Telegram ID:** {p.get('telegram_id', 'N/A')}")
            c3.write(f"**Glaciar:** {'Sí' if p.get('glaciar') else 'No'}")

# --- PESTAÑA 2: HISTORIAL 20 AÑOS ---
with tab2:
    st.header("📊 Serie de Tiempo (2006-2026)")
    p_hist = st.selectbox("Seleccione Proyecto", [p['Proyecto'] for p in proyectos], key="sel_hist")
    if st.button("🚀 Reconstruir Tendencia"):
        target = next(i for i in proyectos if i['Proyecto'] == p_hist)
        geom = ee.Geometry.Polygon(json.loads(target['Coordenadas']))
        anios = range(2006, 2027)
        datos_h = []
        with st.spinner("Buscando en Landsat 5, 7 y 8..."):
            for y in anios:
                coll = ee.ImageCollection("LANDSAT/LC08/C02/T1_L2") if y >= 2013 else ee.ImageCollection("LANDSAT/LE07/C02/T1_L2")
                img = coll.filterBounds(geom).filterDate(f"{y}-01-01", f"{y}-12-31").median()
                try:
                    val = img.normalizedDifference(['SR_B5', 'SR_B4'] if y >= 2013 else ['SR_B4', 'SR_B3']).reduceRegion(ee.Reducer.mean(), geom, 30).getInfo().get('nd', 0)
                except: val = 0
                datos_h.append(val or 0)
            st.line_chart(pd.DataFrame({"Año": anios, "Vigor": datos_h}).set_index("Año"))

# --- PESTAÑA 3: INFORMES PDF (CORREGIDA) ---
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
        pdf.cell(200, 10, f"Fecha: {datetime.now().strftime('%d/%m/%Y')}", ln=True)
        pdf.cell(200, 10, f"Tipo: {target_pdf.get('Tipo')}", ln=True)
        
        # EL ARREGLO ESTÁ AQUÍ:
        pdf_content = pdf.output(dest='S')
        if isinstance(pdf_content, str): # Si la versión de fpdf devuelve string
            pdf_bytes = pdf_content.encode('latin-1')
        else: # Si devuelve bytes directamente (fpdf2)
            pdf_bytes = pdf_content
            
        b64 = base64.b64encode(pdf_bytes).decode()
        st.markdown(f'<a href="data:application/pdf;base64,{b64}" download="BioCore_{p_pdf}.pdf">📥 Descargar PDF</a>', unsafe_allow_html=True)

# --- PESTAÑA 4: REGISTRO ---
with tab4:
    st.header("➕ Registro")
    with st.form("reg_v5"):
        c1, c2 = st.columns(2)
        f_name = c1.text_input("Nombre Proyecto")
        f_tipo = c2.selectbox("Tipo", ["HUMEDAL", "MINERIA"])
        f_coords = st.text_area("Coordenadas (JSON)")
        f_tid = st.text_input("Telegram ID")
        f_mail = st.text_input("Email Cliente")
        f_pass = st.text_input("Password Cliente", type="password")
        f_glaciar = st.checkbox("Monitoreo Glaciar")
        
        if st.form_submit_button("💾 GUARDAR"):
            try:
                pts = json.loads(f_coords)
                if pts[0] != pts[-1]: pts.append(pts[0])
                supabase.table("usuarios").insert({
                    "Proyecto": f_name, "Tipo": f_tipo, "Coordenadas": json.dumps(pts),
                    "telegram_id": f_tid, "Email": f_mail, "Password": f_pass, "glaciar": f_glaciar
                }).execute()
                st.success("Guardado.")
            except Exception as e: st.error(f"Error: {e}")
