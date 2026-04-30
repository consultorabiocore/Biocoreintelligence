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

# --- 2. CONEXIÓN SUPABASE ---
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

# --- 3. MOTORES DE CÁLCULO ---
def escanear_multimodal(coords_str):
    roi = ee.Geometry.Polygon(json.loads(coords_str))
    
    # Sentinel-2 (Óptico - Sensible a nubes)
    s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED').filterBounds(roi).sort('system:time_start', False).first()
    
    # Sentinel-1 (RADAR - Atraviesa nubes)
    s1 = ee.ImageCollection('COPERNICUS/S1_GRD')\
        .filterBounds(roi)\
        .filter(ee.Filter.eq('instrumentMode', 'IW'))\
        .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV'))\
        .sort('system:time_start', False).first()
    
    clima = ee.ImageCollection("IDAHO_EPSCOR/TERRACLIMATE").filterBounds(roi).sort('system:time_start', False).first()

    def get_val(img, band, scale):
        if not img: return 0
        try:
            val = img.reduceRegion(ee.Reducer.mean(), roi, scale).get(band).getInfo()
            return round(float(val), 3) if val else 0
        except: return 0

    savi_img = s2.expression('((B8-B4)/(B8+B4+0.5))*1.5', {'B8':s2.select('B8'),'B4':s2.select('B4')}) if s2 else None
    
    return {
        "SAVI": get_val(savi_img, 'constant', 30),
        "Radar_VV": get_val(s1, 'VV', 10), # Dato clave cuando hay nubes
        "Precip": get_val(clima, 'pr', 4638),
        "Temp": round(get_val(clima, 'tmmx', 4638) * 0.1, 1)
    }

def obtener_historia_20_anos(coords_str):
    try:
        geom = ee.Geometry.Polygon(json.loads(coords_str))
        ahora = datetime.now().year
        datos = []
        
        # Colección Landsat para el pasado
        fusion = ee.ImageCollection("LANDSAT/LC09/C02/T1_L2")\
            .merge(ee.ImageCollection("LANDSAT/LC08/C02/T1_L2"))\
            .merge(ee.ImageCollection("LANDSAT/LE07/C02/T1_L2"))\
            .merge(ee.ImageCollection("LANDSAT/LT05/C02/T1_L2"))

        for año in range(ahora - 20, ahora + 1):
            inicio, fin = f"{año}-01-01", f"{año}-12-31"
            # Reductor de percentil 50 (mediana) para limpiar nubes en el historial
            img = fusion.filterBounds(geom).filterDate(inicio, fin).median()
            
            bandas = img.bandNames().getInfo()
            b_nir, b_red = (('SR_B5', 'SR_B4') if 'SR_B5' in bandas else ('SR_B4', 'SR_B3')) if bandas else (None, None)

            if b_nir:
                savi_val = img.expression('((N-R)/(N+R+0.5))*1.5', {'N':img.select(b_nir),'R':img.select(b_red)})\
                    .reduceRegion(ee.Reducer.mean(), geom, 30).getInfo().get('constant', 0)
                val = round(savi_val, 3) if savi_val else 0
            else: val = 0
                
            datos.append({'año': str(año), 'savi': val})
        return pd.DataFrame(datos)
    except Exception as e:
        st.error(f"Error historial: {e}"); return pd.DataFrame()

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
        st.success(f"Proyecto: {st.session_state.user['Proyecto']}")
        menu = st.radio("Módulos:", ["🛰️ Monitor Pro", "📊 Auditoría 20 Años", "🔥 Riesgo Incendio"])
        if st.button("Cerrar Sesión"): st.session_state.auth = False; st.rerun()

# --- 5. PANEL DE CONTROL ---
if st.session_state.auth:
    u = st.session_state.user
    coords_act = u['Coordenadas']
    fecha_hoy = datetime.now().strftime('%d/%m/%Y')

    if menu == "🛰️ Monitor Pro":
        st.subheader(f"Auditoría: {u['Proyecto']}")
        col1, col2 = st.columns([2, 1])
        
        with col1:
            c = json.loads(coords_act)
            m = folium.Map(location=[c[0][1], c[0][0]], zoom_start=14)
            folium.TileLayer('https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}', attr='Google', name='Sat').add_to(m)
            folium.Polygon(locations=[[p[1], p[0]] for p in c], color='#2ecc71', fill=True, opacity=0.3).add_to(m)
            folium_static(m)

        with col2:
            if st.button("🚀 EJECUTAR ANÁLISIS MULTIMODAL"):
                if init_gee():
                    with st.spinner("Fusionando Óptico + Radar (Sentinel 1/2)..."):
                        data = escanear_multimodal(coords_act)
                        
                        st.metric("Vigor (SAVI)", data['SAVI'], help="Suelo/Vegetación (Óptico)")
                        st.metric("Estructura (Radar VV)", f"{data['Radar_VV']} dB", help="Independiente de nubes")
                        st.metric("Humedad/Precip", f"{data['Precip']} mm")
                        
                        # Reporte Telegram (Texto Directo)
                        msg = (f"🛰️ *REPORTE BIOCORE (Radar + Óptico)*\n"
                               f"📍 *Lugar:* {u['Proyecto']}\n"
                               f"📅 *Fecha:* {fecha_hoy}\n\n"
                               f"🌿 *SAVI:* {data['SAVI']}\n"
                               f"📡 *Radar VV:* {data['Radar_VV']} dB\n"
                               f"💧 *Lluvia:* {data['Precip']} mm\n"
                               f"🌡️ *Temp:* {data['Temp']} °C\n\n"
                               f"✅ _Dato de Radar disponible incluso con nubes._")
                        
                        try:
                            requests.post(f"https://api.telegram.org/bot{T_TOKEN}/sendMessage", 
                                          data={"chat_id": T_ID, "text": msg, "parse_mode": "Markdown"})
                            st.success("✅ Mensaje enviado a Telegram.")
                        except: st.warning("⚠️ Fallo en Telegram.")

                        # Opción de descarga PDF
                        pdf = FPDF()
                        pdf.add_page(); pdf.set_font("helvetica", "B", 16)
                        pdf.cell(0, 10, clean(f"INFORME BIOCORE: {u['Proyecto']}"), ln=1)
                        pdf.set_font("helvetica", "", 12)
                        pdf.multi_cell(0, 10, clean(f"Fecha: {fecha_hoy}\nSAVI: {data['SAVI']}\nRadar: {data['Radar_VV']} dB\nLluvia: {data['Precip']}mm"))
                        
                        pdf_out = pdf.output(dest='S')
                        pdf_bytes = bytes(pdf_out) if not isinstance(pdf_out, str) else pdf_out.encode('latin-1')
                        st.download_button("📥 Descargar Reporte PDF", pdf_bytes, f"BioCore_{u['Proyecto']}.pdf")

    elif menu == "📊 Auditoría 20 Años":
        st.subheader(f"Evolución Histórica Landsat: {u['Proyecto']}")
        if st.button("🔍 Cargar Cronología"):
            if init_gee():
                with st.spinner("Procesando 20 años..."):
                    df = obtener_historia_20_anos(coords_act)
                    if not df.empty:
                        st.line_chart(df.set_index('año'))
                        st.dataframe(df)

    elif menu == "🔥 Riesgo Incendio":
        st.subheader("Anomalías Térmicas (FIRMS)")
        if init_gee():
            p = ee.Geometry.Polygon(json.loads(coords_act))
            f = ee.ImageCollection('FIRMS').filterBounds(p).filterDate(
                (datetime.now()-relativedelta(days=3)).strftime('%Y-%m-%d'), 
                datetime.now().strftime('%Y-%m-%d')
            ).size().getInfo()
            if f > 0: st.error(f"🚨 {f} focos detectados."); st.toast("RIESGO")
            else: st.success("✅ Área sin focos activos.")
