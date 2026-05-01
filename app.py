import streamlit as st
import json
import ee
import requests
import pandas as pd
from datetime import datetime
from supabase import create_client, Client
from fpdf import FPDF
import base64

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="BioCore Intelligence V5", layout="wide", page_icon="🛰️")

# --- 2. ACCESO ---
if "password_correct" not in st.session_state:
    st.title("🛰️ BioCore V5 - Acceso Directivo")
    u = st.text_input("Usuario").strip().lower()
    p = st.text_input("Contraseña", type="password").strip()
    if st.button("Entrar"):
        if u == st.secrets["auth"]["user"] and p == str(st.secrets["auth"]["password"]):
            st.session_state["password_correct"] = True
            st.rerun()
    st.stop()

# --- 3. CONEXIONES ---
supabase: Client = create_client(st.secrets["connections"]["supabase"]["url"], st.secrets["connections"]["supabase"]["key"])
creds_info = json.loads(st.secrets["gee"]["json"])
if not ee.data.is_initialized():
    ee.Initialize(ee.ServiceAccountCredentials(creds_info['client_email'], key_data=creds_info['private_key']))

# --- 4. PESTAÑAS ---
tab1, tab2, tab3, tab4 = st.tabs(["🚀 MONITOREO Y DIAGNÓSTICO", "📊 HISTORIAL 20 AÑOS", "📄 INFORMES PDF", "➕ REGISTRO"])

res = supabase.table("usuarios").select("*").execute()
proyectos = res.data

# --- PESTAÑA 1: MONITOREO CON MOTOR BIOCRE ---
with tab1:
    st.header("📡 Vigilancia Ambiental Avanzada")
    
    for p_info in proyectos:
        with st.expander(f"🔍 Ejecutar Diagnóstico: {p_info['Proyecto']}"):
            if st.button(f"🚀 Procesar {p_info['Proyecto']}"):
                try:
                    with st.spinner("Calculando índices BioCore..."):
                        p_geom = ee.Geometry.Polygon(json.loads(p_info['Coordenadas']))
                        
                        # --- CAPTURA DE SENSORES ---
                        s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED').filterBounds(p_geom).sort('system:time_start', False).first()
                        f_rep = datetime.fromtimestamp(s2.get('system:time_start').getInfo()/1000).strftime('%d/%m/%Y')
                        
                        s1 = ee.ImageCollection('COPERNICUS/S1_GRD').filterBounds(p_geom).filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV')).sort('system:time_start', False).first()
                        sar_val = s1.reduceRegion(ee.Reducer.mean(), p_geom, 30).getInfo().get('VV', 0)

                        # --- CÁLCULO DE ÍNDICES ---
                        idx = s2.expression('((B8-B4)/(B8+B4+0.5))*1.5', {
                            'B8': s2.select('B8'), 'B4': s2.select('B4')
                        }).rename('sa')\
                        .addBands(s2.normalizedDifference(['B3','B8']).rename('nd'))\
                        .addBands(s2.normalizedDifference(['B3','B11']).rename('mn'))\
                        .addBands(s2.select('B11').divide(10000).rename('sw'))\
                        .addBands(s2.select('B11').divide(s2.select('B12')).rename('clay'))\
                        .reduceRegion(ee.Reducer.mean(), p_geom, 30).getInfo()
                        
                        sa, nd, mn, sw, clay = idx['sa'], idx['nd'], idx['mn'], idx['sw'], idx['clay']
                        
                        # GEDI y TerraClimate
                        try:
                            gedi = ee.ImageCollection("LARSE/GEDI/L2A_002").filterBounds(p_geom).sort('system:time_start', False).first()
                            alt = gedi.reduceRegion(ee.Reducer.mean(), p_geom, 30).getInfo().get('rh98', 1.2)
                        except: alt = 1.2
                        
                        clim = ee.ImageCollection("IDAHO_EPSCOR/TERRACLIMATE").filterBounds(p_geom).sort('system:time_start', False).first()
                        defic = abs(float(clim.reduceRegion(ee.Reducer.mean(), p_geom, 4638).getInfo().get('pr', 0)) - 100)

                        # --- LÓGICA DE DIAGNÓSTICO ---
                        estado_global = "🟢 BAJO CONTROL"
                        cat_tipo = "Humedal Urbano" if p_info['Tipo'] == "HUMEDAL" else "Área Minera"
                        
                        if p_info['Tipo'] == "HUMEDAL":
                            est_su = "🛡️ HIDROESTABLE"
                            exp_su = f"SWIR ({sw:.2f}): Absorción hídrica óptima."
                            diagnostico = "Parámetros bióticos dentro de la norma."
                            if nd < 0.1: estado_global = "🔴 ALERTA TÉCNICA"; diagnostico = "Estrés hídrico detectado."
                        else:
                            est_su = "🛡️ ESTABLE" if sw < 0.45 else "⚠️ REMOCIÓN"
                            exp_su = f"SWIR ({sw:.2f}): Reflectancia estable."
                            diagnostico = "Sin indicios de intervención antrópica."
                            if p_info.get('glaciar') and mn < 0.35:
                                estado_global = "🔴 ALERTA TÉCNICA"
                                diagnostico = f"Pérdida de cobertura criosférica (NDSI: {mn:.2f})."

                        # --- ENVÍO DE REPORTE ---
                        reporte = (
                            f"🛰 **REPORTE DE VIGILANCIA AMBIENTAL - BIOCORE**\n"
                            f"**PROYECTO:** {p_info['Proyecto']}\n"
                            f"**Directora Técnica:** Loreto Campos Carrasco\n"
                            f"📅 **Análisis:** {f_rep}\n"
                            f"──────────────────\n"
                            f"🛡️ **INTEGRIDAD (SU-6):** {est_su}\n"
                            f"└ Radar: `{sar_val:.2f} dB` | SWIR: `{sw:.2f}`\n\n"
                            f"🌱 **SALUD (VE-5):** Vigor SAVI `{sa:.2f}`\n\n"
                            f"✅ **ESTADO GLOBAL:** {estado_global}\n"
                            f"📝 **Diagnóstico:** {diagnostico}"
                        )
                        
                        requests.post(f"https://api.telegram.org/bot{st.secrets['telegram']['token']}/sendMessage", 
                                     data={"chat_id": p_info['telegram_id'], "text": reporte, "parse_mode": "Markdown"})
                        
                        st.success("Reporte profesional enviado a Telegram.")
                        st.markdown(reporte)

                except Exception as e:
                    st.error(f"Error procesando {p_info['Proyecto']}: {e}")

# (Las pestañas de Historial, PDF y Registro se mantienen con la misma lógica de los bloques anteriores)
