import streamlit as st
import pandas as pd
import json
import ee
import matplotlib.pyplot as plt
from datetime import datetime
from dateutil.relativedelta import relativedelta
from fpdf import FPDF
from supabase import create_client

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="BioCore Intelligence Pro", layout="wide")

@st.cache_resource
def init_supabase():
    return create_client(st.secrets["connections"]["supabase"]["url"], st.secrets["connections"]["supabase"]["key"])

def init_gee():
    try:
        gee_json = json.loads(st.secrets["gee"]["json"])
        credentials = ee.ServiceAccountCredentials(gee_json['client_email'], key_data=gee_json['private_key'])
        ee.Initialize(credentials, project=gee_json['project_id'])
        return True
    except Exception as e:
        st.error(f"Error GEE: {e}")
        return False

# --- 2. MOTOR PRO (CORREGIDO) ---
def analizar_biocore_pro(poligono_str):
    roi = ee.Geometry.Polygon(json.loads(poligono_str))
    
    # TerraClimate (Clima) - Usamos una fecha fija cercana para asegurar datos
    clima = ee.ImageCollection("IDAHO_EPSCOR/TERRACLIMATE").filterBounds(roi).sort('system:time_start', False).first()
    
    # Sentinel-1 (Radar) - Filtro robusto
    s1 = ee.ImageCollection('COPERNICUS/S1_GRD')\
        .filterBounds(roi).filter(ee.Filter.eq('instrumentMode', 'IW'))\
        .sort('system:time_start', False).first()

    # Sentinel-2 (Óptico)
    s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')\
        .filterBounds(roi).filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20))\
        .sort('system:time_start', False).first()

    # Cálculos con protección .get()
    def safe_reduce(img, band, scale):
        if img is None: return 0
        val = img.select(band).reduceRegion(ee.Reducer.mean(), roi, scale).get(band)
        return ee.Number(val).format('%.2f').getInfo() if val else 0

    savi = s2.expression('((B8-B4)/(B8+B4+0.5))*1.5', {'B8':s2.select('B8'),'B4':s2.select('B4')})
    
    return {
        "SAVI": round(float(savi.reduceRegion(ee.Reducer.mean(), roi, 30).get('constant').getInfo() or 0), 3),
        "Precip": clima.get('pr').getInfo() if clima else 0,
        "Temp": (clima.getNumber('tmmx').multiply(0.1).getInfo()) if clima else 0,
        "Radar": s1.select('VV').reduceRegion(ee.Reducer.mean(), roi, 10).get('VV').getInfo() if s1 else "N/A"
    }

# --- 3. HISTORIA 20 AÑOS (OPTIMIZADA PARA NO DAR ERROR) ---
def obtener_historia_20_anos(poligono_str):
    roi = ee.Geometry.Polygon(json.loads(poligono_str))
    ahora = datetime.now().year
    años = ee.List.sequence(ahora - 20, ahora)
    
    # Colección Landsat Simplificada
    fusion = ee.ImageCollection("LANDSAT/LC08/C02/T1_L2").merge(ee.ImageCollection("LANDSAT/LE07/C02/T1_L2"))

    def calc_anual(a):
        f = ee.Date.fromYMD(a, 1, 1)
        img = fusion.filterBounds(roi).filterDate(f, f.advance(1, 'year')).median()
        # Fallback si no hay bandas
        savi = ee.Algorithms.If(img.bandNames().contains('SR_B5'),
            img.expression('((B5-B4)/(B5+B4+0.5))*1.5', {'B5':img.select('SR_B5'),'B4':img.select('SR_B4')}),
            ee.Image(0))
        val = ee.Image(savi).reduceRegion(ee.Reducer.mean(), roi, 100).get('constant')
        return ee.Feature(None, {'año': ee.Number(a).format('%d'), 'savi': val})

    fc = ee.FeatureCollection(años.map(calc_anual)).filter(ee.Filter.notNull(['savi'])).getInfo()
    return pd.DataFrame([f['properties'] for f in fc['features']])

# --- 4. INTERFAZ ---
st.title("🌿 BioCore Intelligence Pro")

if 'auth' not in st.session_state: st.session_state.auth = False

with st.sidebar:
    if not st.session_state.auth:
        email = st.text_input("Email").lower().strip()
        pw = st.text_input("Password", type="password")
        if st.button("Entrar"):
            res = init_supabase().table("usuarios").select("*").eq("Email", email).execute()
            if res.data and str(res.data[0]['Password']) == pw:
                st.session_state.auth, st.session_state.user = True, res.data[0]
                st.rerun()
    else:
        st.write(f"Proyecto: {st.session_state.user['Proyecto']}")
        if st.button("Salir"): st.session_state.auth = False; st.rerun()

if st.session_state.auth:
    u = st.session_state.user
    if st.button("🚀 Ejecutar Escaneo BioCore Pro"):
        if init_gee():
            with st.spinner("Analizando 20 años + Clima + Radar..."):
                try:
                    res_pro = analizar_biocore_pro(u['Coordenadas'])
                    df_20 = obtener_historia_20_anos(u['Coordenadas'])
                    
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("SAVI", res_pro['SAVI'])
                    c2.metric("Precipitación", f"{res_pro['Precip']} mm")
                    c3.metric("Temp Max", f"{res_pro['Temp']} °C")
                    c4.metric("Radar VV", res_pro['Radar'])
                    
                    st.subheader("📊 Historial de 20 Años")
                    st.line_chart(df_20.set_index('año'))
                except Exception as e:
                    st.error(f"Error técnico en el procesamiento: {e}")
