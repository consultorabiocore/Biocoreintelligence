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

# --- 3. MOTORES DE CÁLCULO (MULTIMODAL & HISTÓRICO) ---
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

    savi_img = s2.expression('((B8-B4)/(B8+B4+0.5))*1.5', {'B8':s2.select('B8'),'B4':s2.select('B4')}) if s2 else None
    
    return {
        "SAVI": round(float(get_val(savi_img, 'constant', 30)), 3),
        "Precip": round(float(get_val(clima, 'pr', 4638)), 1),
        "Temp": round(float(get_val(clima, 'tmmx', 4638)) * 0.1, 1),
        "Radar": round(float(get_val(s1, 'VV', 10)), 2)
    }

def obtener_historia_20_anos(coords_str):
    roi = ee.Geometry.Polygon(json.loads(coords_str))
    ahora = datetime.now().year
    años = ee.List.sequence(ahora - 20, ahora)
    fusion = ee.ImageCollection("LANDSAT/LC08/C02/T1_L2").merge(ee.ImageCollection("LANDSAT/LE07/C02/T1_L2"))

    def calc_anual(a):
        f = ee.Date.fromYMD(a, 1, 1)
        img = fusion.filterBounds(roi).filterDate(f, f.advance(1, 'year')).median()
        bandas = img.bandNames()
        tiene = bandas.contains('SR_B5').And(bandas.contains('SR_B4'))
        savi = ee.Algorithms.If(tiene,
            img.expression('((B5-B4)/(B5+B4+0.5))*1.5', {'B5':img.select('SR_B5'), 'B4':img.select('SR_B4')}),
            ee.Image(0))
        val = ee.Image(savi).reduceRegion(ee.Reducer.mean(), roi, 100).get('constant')
        return ee.Feature(None, {'año': ee.Number(a).format('%d'), 'savi': ee.Algorithms.If(val, val, 0)})

    fc = ee.FeatureCollection(años.map(calc_anual)).getInfo()
    return pd.DataFrame([f['properties'] for f in fc['features']])

# --- 4. INTERFAZ DE ACCESO ---
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

# --- 5. PANELES DE CONTROL ---
if st.session_state.auth:
    u = st.session_state.user
    # Coordenadas por defecto Laguna Señoraza si no existen en BD
    coords_act = u.get('Coordenadas', '[[-72.715,-37.275],[-72.715,-37.285],[-72.690,-37.285],[-72.690,-37.270]]')

    if menu == "🛰️ Monitor Pro":
        st.subheader(f"Proyecto Activo: {u['Proyecto']}")
        col1, col2 = st.columns([2, 1])
        
        with col1:
            c = json.loads(coords_act)
            m = folium.Map(location=[c[0][1], c[0][0]], zoom_start=15)
            folium.TileLayer('https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}', attr='Google', name='Sat').add_to(m)
            folium.Polygon(locations=[[p[1], p[0]] for p in c], color='#2ecc71', fill=True, opacity=0.3).add_to(m)
            folium_static(m)

        with col2:
            if st.button("🚀 INICIAR ESCANEO BIOCORE"):
                if init_gee():
                    with st.spinner("Analizando Multimodalmente..."):
                        data = escanear_multimodal(coords_act)
                        st.metric("Vigor (SAVI)", data['SAVI'])
                        st.metric("Precipitación", f"{data['Precip']} mm")
                        st.metric("Radar VV", data['Radar'])
                        
                        # Generación de PDF
                        pdf = FPDF()
                        pdf.add_page()
                        pdf.set_font("helvetica", "B", 16)
                        pdf.cell(0, 10, clean(f"REPORTE BIOCORE: {u['Proyecto']}"), ln=1)
                        pdf.set_font("helvetica", "", 12)
                        pdf.multi_cell(0, 10, clean(f"Fecha: {datetime.now().strftime('%d/%m/%Y')}\nSAVI: {data['SAVI']}\nLluvia: {data['Precip']}mm\nRadar: {data['Radar']}"))
                        
                        pdf_out = pdf.output(dest='S')
                        pdf_bytes = bytes(pdf_out) if not isinstance(pdf_out, str) else pdf_out.encode('latin-1')
                        
                        try:
                            requests.post(
                                f"https://api.telegram.org/bot{T_TOKEN}/sendDocument", 
                                data={"chat_id": T_ID, "caption": f"✅ Scan: {u['Proyecto']}"}, 
                                files={"document": (f"BioCore_{u['Proyecto']}.pdf", pdf_bytes)}
                            )
                            st.success("Enviado a Telegram.")
                        except:
                            st.warning("Error enviando a Telegram.")
                        
                        st.download_button("📥 Descargar Reporte", pdf_bytes, f"BioCore_{u['Proyecto']}.pdf")

    elif menu == "📊 Auditoría 20 Años":
        st.subheader("Serie Histórica (2006-Presente)")
        if st.button("🔄 Generar Historial Interanual"):
            if init_gee():
                with st.spinner("Procesando 20 años de Landsat..."):
                    df_20 = obtener_historia_20_anos(coords_act)
                    st.line_chart(df_20.set_index('año'))
                    st.dataframe(df_20)

    elif menu == "🔥 Riesgo Incendio":
        st.subheader("Detección NASA FIRMS (24h)")
        if init_gee():
            p = ee.Geometry.Polygon(json.loads(coords_act))
            focos = ee.ImageCollection('FIRMS').filterBounds(p).filterDate(
                (datetime.now()-relativedelta(days=1)).strftime('%Y-%m-%d'), 
                datetime.now().strftime('%Y-%m-%d')
            ).size().getInfo()
            if focos > 0: st.error(f"🚨 Alerta: {focos} focos detectados."); st.toast("RIESGO")
            else: st.success("✅ Sin anomalías térmicas recientes.")
