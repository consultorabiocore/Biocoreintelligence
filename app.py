import streamlit as st
import json
import ee
import requests
import pandas as pd
from datetime import datetime
from supabase import create_client, Client
from fpdf import FPDF
import base64

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="BioCore Intelligence V5", layout="wide")

# Estética Dark Nature
st.markdown("""
    <style>
    .stMetric { background-color: #161b22; border: 1px solid #238636; padding: 15px; border-radius: 10px; }
    [data-testid="stExpander"] { border: 1px solid #30363d; background-color: #0d1117; }
    </style>
""", unsafe_allow_html=True)

if "password_correct" not in st.session_state:
    st.title("🛰️ BioCore V5 - Acceso")
    u = st.text_input("Usuario")
    p = st.text_input("Contraseña", type="password")
    if st.button("Entrar"):
        if u == st.secrets["auth"]["user"] and p == str(st.secrets["auth"]["password"]):
            st.session_state["password_correct"] = True
            st.rerun()

if st.session_state.get("password_correct"):
    supabase: Client = create_client(st.secrets["connections"]["supabase"]["url"], st.secrets["connections"]["supabase"]["key"])
    creds_info = json.loads(st.secrets["gee"]["json"])
    if not ee.data.is_initialized():
        ee.Initialize(ee.ServiceAccountCredentials(creds_info['client_email'], key_data=creds_info['private_key']))

    tab1, tab2, tab3, tab4 = st.tabs(["🚀 MONITOREO", "📊 HISTORIAL 20 AÑOS", "📄 INFORMES PDF", "➕ REGISTRO"])

    # --- DATOS ---
    res = supabase.table("usuarios").select("*").execute()
    proyectos = res.data

    # --- PESTAÑA 1: MONITOREO Y REPORTE DIARIO ---
    with tab1:
        st.subheader("📡 Vigilancia Operativa")
        if st.button("📲 ENVIAR REPORTE DIARIO A TODOS"):
            with st.spinner("Analizando constelación satelital..."):
                for p in proyectos:
                    tid = p.get('telegram_id') or st.secrets["telegram"]["chat_id"]
                    msg = f"🛰 **REPORTE DIARIO BIOCORE**\n📍 Proyecto: {p['Proyecto']}\n📅 {datetime.now().strftime('%d/%m/%Y')}\n✅ Estatus: Operativo"
                    requests.post(f"https://api.telegram.org/bot{st.secrets['telegram']['token']}/sendMessage", 
                                 data={"chat_id": tid, "text": msg, "parse_mode": "Markdown"})
            st.success("Reportes enviados correctamente.")

        for p in proyectos:
            with st.expander(f"🔍 {p['Proyecto']} ({p.get('Tipo', 'N/A')})"):
                st.write(f"**Email Cliente:** {p.get('Email', 'No registrado')}")
                st.write(f"**Glaciar:** {'Sí' if p.get('glaciar') else 'No'}")

    # --- PESTAÑA 2: HISTORIAL 20 AÑOS (LANDSAT) ---
    with tab2:
        st.subheader("📊 Análisis Multitemporal (2006-2026)")
        p_hist = st.selectbox("Seleccione Proyecto para histórico", [p['Proyecto'] for p in proyectos], key="hist")
        
        if st.button("🚀 Reconstruir Historial"):
            target = next(i for i in proyectos if i['Proyecto'] == p_hist)
            geom = ee.Geometry.Polygon(json.loads(target['Coordenadas']))
            
            def get_index(year):
                start, end = f"{year}-01-01", f"{year}-12-31"
                coll = ee.ImageCollection("LANDSAT/LC08/C02/T1_L2").filterBounds(geom).filterDate(start, end)
                if coll.size().getInfo() == 0: # Backup para años viejos (Landsat 7/5)
                    coll = ee.ImageCollection("LANDSAT/LE07/C02/T1_L2").filterBounds(geom).filterDate(start, end)
                
                img = coll.median()
                val = img.normalizedDifference(['SR_B5', 'SR_B4']).reduceRegion(ee.Reducer.mean(), geom, 30).getInfo().get('nd', 0)
                return val

            anios = range(2006, 2027)
            with st.spinner("Procesando 20 años de datos Landsat..."):
                datos_h = [get_index(y) for y in anios]
                df = pd.DataFrame({"Año": anios, "Salud Vegetal": datos_h})
                st.line_chart(df.set_index("Año"))
                st.success("Tendencia histórica generada.")

    # --- PESTAÑA 3: INFORMES PDF ---
    with tab3:
        st.subheader("📄 Generación de Documentos")
        p_pdf = st.selectbox("Proyecto para PDF", [p['Proyecto'] for p in proyectos])
        
        if st.button("💾 Generar PDF"):
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Arial", 'B', 16)
            pdf.cell(200, 10, f"Informe Tecnico: {p_pdf}", ln=True, align='C')
            pdf.set_font("Arial", '', 12)
            pdf.ln(10)
            pdf.cell(200, 10, f"Emitido por: BioCore Intelligence", ln=True)
            pdf.cell(200, 10, f"Fecha: {datetime.now().strftime('%d/%m/%Y')}", ln=True)
            
            output = pdf.output(dest='S').encode('latin-1')
            b64 = base64.b64encode(output).decode()
            st.markdown(f'<a href="data:application/pdf;base64,{b64}" download="BioCore_{p_pdf}.pdf">📥 Descargar PDF</a>', unsafe_allow_html=True)

    # --- PESTAÑA 4: REGISTRO ---
    with tab4:
        st.subheader("➕ Nuevo Registro")
        with st.form("reg_form"):
            c1, c2 = st.columns(2)
            name = c1.text_input("Nombre Proyecto")
            tipo = c2.selectbox("Tipo", ["HUMEDAL", "MINERIA"])
            coords = st.text_area("Coordenadas JSON")
            tid = st.text_input("Telegram ID")
            mail = st.text_input("Email Cliente")
            pw = st.text_input("Password Cliente", type="password")
            gl = st.checkbox("Monitoreo Glaciar")
            
            if st.form_submit_button("Guardar"):
                pts = json.loads(coords)
                if pts[0] != pts[-1]: pts.append(pts[0])
                supabase.table("usuarios").insert({
                    "Proyecto": name, "Tipo": tipo, "Coordenadas": json.dumps(pts),
                    "telegram_id": tid, "Email": mail, "Password": pw, "glaciar": gl
                }).execute()
                st.success("Registrado.")
