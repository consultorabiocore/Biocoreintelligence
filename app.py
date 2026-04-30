import streamlit as st
import pandas as pd
import json
import ee
import requests
import matplotlib.pyplot as plt
from datetime import datetime
from dateutil.relativedelta import relativedelta
from fpdf import FPDF
import folium
from streamlit_folium import folium_static
from supabase import create_client

# --- 1. CONFIGURACIÓN E IDENTIDAD ---
st.set_page_config(page_title="BioCore Intelligence Console", layout="wide")
T_TOKEN = st.secrets["telegram"]["token"]
T_ID = st.secrets["telegram"]["chat_id"]
DIRECTORA = "Loreto Campos Carrasco"

def clean(text):
    return text.encode('latin-1', 'replace').decode('latin-1')

# --- 2. CONEXIÓN SUPABASE (TU LOGIN) ---
@st.cache_resource
def init_supabase():
    return create_client(st.secrets["connections"]["supabase"]["url"], st.secrets["connections"]["supabase"]["key"])

supabase = init_supabase()

def init_gee():
    try:
        gee_json = json.loads(st.secrets["gee"]["json"])
        credentials = ee.ServiceAccountCredentials(gee_json['client_email'], key_data=gee_json['private_key'])
        ee.Initialize(credentials, project=gee_json['project_id'])
        return True
    except Exception as e:
        st.error(f"Error GEE: {e}"); return False

# --- 3. MOTOR DE CÁLCULO PRO (ANTI-ERRORES) ---
def escanear_multimodal(coords_str):
    roi = ee.Geometry.Polygon(json.loads(coords_str))
    
    # Captura de sensores
    s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED').filterBounds(roi).sort('system:time_start', False).first()
    s1 = ee.ImageCollection('COPERNICUS/S1_GRD').filterBounds(roi).filter(ee.Filter.eq('instrumentMode', 'IW')).sort('system:time_start', False).first()
    clima = ee.ImageCollection("IDAHO_EPSCOR/TERRACLIMATE").filterBounds(roi).sort('system:time_start', False).first()

    def get_val(img, band, scale):
        if not img: return 0
        try:
            val = img.reduceRegion(ee.Reducer.mean(), roi, scale).get(band).getInfo()
            return val if val else 0
        except: return 0

    # Procesamiento Óptico
    savi_img = s2.expression('((B8-B4)/(B8+B4+0.5))*1.5', {'B8':s2.select('B8'),'B4':s2.select('B4')}) if s2 else None
    
    return {
        "SAVI": round(float(get_val(savi_img, 'constant', 30)), 3),
        "Precip": round(float(get_val(clima, 'pr', 4638)), 1),
        "Temp": round(float(get_val(clima, 'tmmx', 4638)) * 0.1, 1),
        "Radar": round(float(get_val(s1, 'VV', 10)), 2)
    }

# --- 4. INTERFAZ DE ACCESO (SUPABASE) ---
if 'auth' not in st.session_state: st.session_state.auth = False

with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/satellite.png", width=60)
    st.title("BioCore Admin")
    if not st.session_state.auth:
        email = st.text_input("Email").lower().strip()
        pw = st.text_input("Password", type="password")
        if st.button("Ingresar"):
            res = supabase.table("usuarios").select("*").eq("Email", email).execute()
            if res.data and str(res.data[0]['Password']) == pw:
                st.session_state.auth, st.session_state.user = True, res.data[0]
                st.rerun()
    else:
        st.success(f"Conectado: {st.session_state.user['Proyecto']}")
        menu = st.radio("Módulos:", ["🛰️ Monitor Pro", "📊 Auditoría 20 Años", "🔥 Riesgo Incendio"])
        if st.button("Cerrar Sesión"): st.session_state.auth = False; st.rerun()

# --- 5. PANEL DE CONTROL ---
if st.session_state.auth:
    u = st.session_state.user
    
    # Caso especial: Laguna Señoraza (Si no está en BD, usamos estas coords por defecto)
    coords_act = u.get('Coordenadas', '[[-72.715,-37.275],[-72.715,-37.285],[-72.690,-37.285],[-72.690,-37.270]]')
    
    if menu == "🛰️ Monitor Pro":
        st.subheader(f"Proyecto: {u['Proyecto']}")
        
        col1, col2 = st.columns([2, 1])
        with col1:
            # Mapa de la Laguna o Proyecto
            c = json.loads(coords_act)
            m = folium.Map(location=[c[0][1], c[0][0]], zoom_start=15)
            folium.TileLayer('https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}', attr='Google', name='Sat').add_to(m)
            folium.Polygon(locations=[[p[1], p[0]] for p in c], color='#2ecc71', fill=True).add_to(m)
            folium_static(m)

        with col2:
            if st.button("🚀 INICIAR ESCANEO BIOCORE"):
                if init_gee():
                    with st.spinner("Analizando Laguna Señoraza..."):
                        data = escanear_multimodal(coords_act)
                        
                        st.metric("Vigor Vegetal (SAVI)", data['SAVI'])
                        st.metric("Precipitación", f"{data['Precip']} mm")
                        st.metric("Radar VV", data['Radar'])
                        
                        # Reporte PDF y Telegram
                        pdf = FPDF()
                        pdf.add_page(); pdf.set_font("helvetica", "B", 16)
                        pdf.cell(0, 10, clean(f"REPORTE BIOCORE: {u['Proyecto']}"), ln=1)
                        pdf.set_font("helvetica", "", 12)
                        pdf.cell(0, 10, f"Fecha: {datetime.now().strftime('%d/%m/%Y')}", ln=1)
                        pdf.multi_cell(0, 10, clean(f"SAVI: {data['SAVI']}\nLluvia: {data['Precip']}mm\nTemp: {data['Temp']}C"))
                        
                        pdf_bytes = pdf.output(dest='S').encode('latin-1')
                        requests.post(f"https://api.telegram.org/bot{T_TOKEN}/sendDocument", 
                                      data={"chat_id": T_ID, "caption": f"✅ Scan: {u['Proyecto']}"}, 
                                      files={"document": ("BioCore_Report.pdf", pdf_bytes)})
                        st.success("Reporte enviado a Telegram.")

    elif menu == "📊 Auditoría 20 Años":
        st.subheader("Serie de Tiempo Histórica (2006-2026)")
        # Aquí va la función obtener_historia_20_anos que definimos antes
        st.info("Generando comparación interanual con Landsat...")

    elif menu == "🔥 Riesgo Incendio":
        st.subheader("Detección de Focos de Calor (NASA FIRMS)")
        # Lógica de incendios
