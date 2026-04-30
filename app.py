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
    s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED').filterBounds(roi).sort('system:time_start', False).first()
    s1 = ee.ImageCollection('COPERNICUS/S1_GRD').filterBounds(roi).filter(ee.Filter.eq('instrumentMode', 'IW')).sort('system:time_start', False).first()
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
        "Radar_VV": get_val(s1, 'VV', 10),
        "Precip": get_val(clima, 'pr', 4638),
        "Temp": round(get_val(clima, 'tmmx', 4638) * 0.1, 1)
    }

def obtener_historia_20_anos(coords_str):
    try:
        geom = ee.Geometry.Polygon(json.loads(coords_str))
        ahora = datetime.now().year
        datos = []
        
        # Procesamos cada colección por separado para evitar el error de homogeneidad
        l89 = ee.ImageCollection("LANDSAT/LC08/C02/T1_L2").merge(ee.ImageCollection("LANDSAT/LC09/C02/T1_L2")) \
                .select(['SR_B5', 'SR_B4'], ['NIR', 'RED'])
        
        l57 = ee.ImageCollection("LANDSAT/LE07/C02/T1_L2").merge(ee.ImageCollection("LANDSAT/LT05/C02/T1_L2")) \
                .select(['SR_B4', 'SR_B3'], ['NIR', 'RED'])
        
        # Ahora la unión es segura porque todas tienen las mismas bandas: NIR y RED
        fusion = l89.merge(l57)

        for año in range(ahora - 20, ahora + 1):
            inicio, fin = f"{año}-01-01", f"{año}-12-31"
            # Filtramos nubes usando la mediana anual
            img = fusion.filterBounds(geom).filterDate(inicio, fin).median()
            
            # Verificamos si la imagen resultante tiene bandas (si hay datos para ese año)
            tiene_datos = img.bandNames().size().getInfo() > 0

            if tiene_datos:
                savi_val = img.expression('((N-R)/(N+R+0.5))*1.5', {'N':img.select('NIR'),'R':img.select('RED')}) \
                    .reduceRegion(ee.Reducer.mean(), geom, 30).getInfo().get('constant', 0)
                val = round(savi_val, 3) if savi_val else 0
            else:
                val = 0
                
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
            if st.button("🚀 ANÁLISIS MULTIMODAL"):
                if init_gee():
                    with st.spinner("Analizando Óptico + Radar..."):
                        data = escanear_multimodal(coords_act)
                        st.metric("Vigor (SAVI)", data['SAVI'])
                        st.metric("Radar VV", f"{data['Radar_VV']} dB")
                        st.metric("Humedad/Lluvia", f"{data['Precip']} mm")
                        
                        msg = (f"🛰️ *REPORTE BIOCORE*\n📍 *Proyecto:* {u['Proyecto']}\n📅 *Fecha:* {fecha_hoy}\n\n"
                               f"🌿 *SAVI:* {data['SAVI']}\n📡 *Radar VV:* {data['Radar_VV']} dB\n💧 *Lluvia:* {data['Precip']} mm")
                        
                        try:
                            requests.post(f"https://api.telegram.org/bot{T_TOKEN}/sendMessage", 
                                          data={"chat_id": T_ID, "text": msg, "parse_mode": "Markdown"})
                            st.success("✅ Telegram enviado.")
                        except: st.warning("⚠️ Error Telegram.")

                        pdf = FPDF()
                        pdf.add_page(); pdf.set_font("helvetica", "B", 16)
                        pdf.cell(0, 10, clean(f"INFORME BIOCORE: {u['Proyecto']}"), ln=1)
                        pdf.set_font("helvetica", "", 12)
                        pdf.multi_cell(0, 10, clean(f"Fecha: {fecha_hoy}\nSAVI: {data['SAVI']}\nRadar: {data['Radar_VV']} dB"))
                        st.download_button("📥 Descargar Reporte PDF", pdf.output(dest='S').encode('latin-1'), f"BioCore_{u['Proyecto']}.pdf")

    elif menu == "📊 Auditoría 20 Años":
        st.subheader(f"Evolución Histórica: {u['Proyecto']}")
        if st.button("🔍 Cargar Cronología"):
            if init_gee():
                with st.spinner("Sincronizando 20 años de satélites..."):
                    df = obtener_historia_20_anos(coords_act)
                    if not df.empty:
                        st.line_chart(df.set_index('año'))
                        st.dataframe(df)

    elif menu == "🔥 Riesgo Incendio":
        st.subheader("Anomalías Térmicas FIRMS")
        if init_gee():
            p = ee.Geometry.Polygon(json.loads(coords_act))
            f = ee.ImageCollection('FIRMS').filterBounds(p).filterDate((datetime.now()-relativedelta(days=3)).strftime('%Y-%m-%d'), datetime.now().strftime('%Y-%m-%d')).size().getInfo()
            if f > 0: st.error(f"🚨 {f} focos detectados."); st.toast("RIESGO")
            else: st.success("✅ Área segura.")
