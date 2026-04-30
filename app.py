import streamlit as st
import pandas as pd
import json
import ee
import matplotlib.pyplot as plt
from datetime import datetime
from dateutil.relativedelta import relativedelta
from fpdf import FPDF
from supabase import create_client

# --- 1. CONFIGURACIÓN E INICIALIZACIÓN ---
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
        st.error(f"Error de conexión GEE: {e}")
        return False

# --- 2. MOTOR DE ANÁLISIS MULTIMODAL (CLIMA + RADAR + ÓPTICO) ---
def analizar_biocore_pro(poligono_str, tipo_proyecto):
    roi = ee.Geometry.Polygon(json.loads(poligono_str))
    ahora = ee.Date(datetime.now().strftime('%Y-%m-%d'))
    hace_30d = ahora.advance(-1, 'month')

    # A. TERRACLIMA: Datos Meteorológicos
    clima = ee.ImageCollection("IDAHO_EPSCOR/TERRACLIMATE").filterBounds(roi).last().clip(roi)
    stats_clima = clima.reduceRegion(ee.Reducer.mean(), roi, 4638).getInfo()
    
    # B. SENTINEL-1: Radar (Humedad y Estructura sin nubes)
    s1 = ee.ImageCollection('COPERNICUS/S1_GRD')\
        .filterBounds(roi).filterDate(hace_30d, ahora)\
        .filter(ee.Filter.eq('instrumentMode', 'IW'))\
        .median().clip(roi)
    stats_s1 = s1.reduceRegion(ee.Reducer.mean(), roi, 10).getInfo()

    # C. SENTINEL-2: Vigor Actual (SAVI)
    s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')\
        .filterBounds(roi).filterDate(hace_30d, ahora)\
        .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20))\
        .median().clip(roi)
    
    savi_img = s2.expression('((B8-B4)/(B8+B4+0.5))*1.5', {
        'B8': s2.select('B8'), 'B4': s2.select('B4')
    })
    val_savi = savi_img.reduceRegion(ee.Reducer.mean(), roi, 30).getInfo().get('constant', 0)

    return {
        "SAVI": round(val_savi, 3) if val_savi else 0,
        "Precip_mm": round(stats_clima.get('pr', 0), 1),
        "Temp_Max": round(stats_clima.get('tmmx', 0) * 0.1, 1), # Escala TerraClimate
        "Radar_VV": round(stats_s1.get('VV', 0), 2) if stats_s1 else "N/A"
    }

# --- 3. SERIE HISTÓRICA 20 AÑOS (LANDSAT) ---
def obtener_historia_20_anos(poligono_str):
    roi = ee.Geometry.Polygon(json.loads(poligono_str))
    inicio = datetime.now() - relativedelta(years=20)
    
    l8 = ee.ImageCollection("LANDSAT/LC08/C02/T1_L2").select(['SR_B5', 'SR_B4'], ['nir', 'red'])
    l7 = ee.ImageCollection("LANDSAT/LE07/C02/T1_L2").select(['SR_B4', 'SR_B3'], ['nir', 'red'])
    l5 = ee.ImageCollection("LANDSAT/LT05/C02/T1_L2").select(['SR_B4', 'SR_B3'], ['nir', 'red'])
    
    fusion = l8.merge(l7).merge(l5).filterBounds(roi)
    años = ee.List.sequence(inicio.year, datetime.now().year)

    def calc_anual(a):
        f = ee.Date.fromYMD(a, 1, 1)
        img = fusion.filterDate(f, f.advance(1, 'year')).median()
        savi = img.expression('((nir-red)/(nir+red+0.5))*1.5', {
            'nir': img.select('nir').multiply(0.0000275).add(-0.2),
            'red': img.select('red').multiply(0.0000275).add(-0.2)
        })
        return ee.Feature(None, {'año': ee.Number(a).format('%d'), 'savi': savi.reduceRegion(ee.Reducer.mean(), roi, 30).get('constant')})

    features = ee.FeatureCollection(años.map(calc_anual)).getInfo()
    return pd.DataFrame([f['properties'] for f in features['features'] if f['properties']['savi'] is not None])

# --- 4. INTERFAZ DE USUARIO ---
st.title("🌿 BioCore Intelligence Pro")
st.markdown("### Sistema Multimodal: Óptico + Radar + Climatología")

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
        st.write(f"Sesión: **{st.session_state.user['Proyecto']}**")
        if st.button("Cerrar"): st.session_state.auth = False; st.rerun()

if st.session_state.auth:
    u = st.session_state.user
    
    if st.button("🚀 Ejecutar Escaneo BioCore Pro"):
        if init_gee():
            with st.spinner("Analizando 20 años de datos y condiciones climáticas..."):
                # 1. Datos actuales y clima
                res_pro = analizar_biocore_pro(u['Coordenadas'], u['Tipo'])
                
                # 2. Historia 20 años
                df_20 = obtener_historia_20_anos(u['Coordenadas'])
                
                # Despliegue de métricas
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Vigor (SAVI)", res_pro['SAVI'])
                c2.metric("Lluvia (Mes)", f"{res_pro['Precip_mm']} mm")
                c3.metric("Temp Max", f"{res_pro['Temp_Max']} °C")
                c4.metric("Radar VV", res_pro['Radar_VV'])
                
                # Gráfico Histórico
                st.subheader("📊 Evolución Interanual (2006 - Presente)")
                fig, ax = plt.subplots(figsize=(10, 4))
                ax.plot(df_20['año'], df_20['savi'], color='#2ecc71', marker='o', linewidth=2)
                ax.set_facecolor('#f0f2f6')
                ax.grid(True, alpha=0.3)
                st.pyplot(fig)

                # Generación de Informe PDF (Lógica simplificada para descarga)
                st.success("Análisis completado. Reporte listo para descarga.")
                st.download_button("📥 Descargar Auditoría Completa (PDF)", "Contenido del Reporte", f"BioCore_{u['Proyecto']}.pdf")
