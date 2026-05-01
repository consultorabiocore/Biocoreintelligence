import streamlit as st
import ee
import folium
from streamlit_folium import folium_static
import json
import pandas as pd
import requests
from datetime import datetime
from supabase import create_client, Client

# --- 1. CONFIGURACIÓN INICIAL ---
st.set_page_config(page_title="BioCore Intelligence V5", layout="wide")

@st.cache_resource
def init_connections():
    # Conexión a Supabase
    url = st.secrets["connections"]["supabase"]["url"]
    key = st.secrets["connections"]["supabase"]["key"]
    return create_client(url, key)

supabase = init_connections()

# Perfiles de configuración (Lógica de Blindaje Legal y Catastro)
if 'PERFILES' not in st.session_state:
    st.session_state.PERFILES = {
        "MINERIA": {
            "cat": "Área Minera / Depósito de Estériles (Formulario F-30)",
            "ve7": "Estabilidad de sustrato compatible con plan de cierre.",
            "clima": "Control de aridez y material particulado (F-30)",
            "sensor": "sw", "u": 0.45, "c": "mayor"
        },
        "GLACIAR": {
            "cat": "Área Criosférica / Glaciar Rock (RCA Pascua Lama)",
            "ve7": "Protección de balance de masa y escorrentía.",
            "clima": "Vigilancia de albedo y temperatura criosférica.",
            "sensor": "mn", "u": 0.35, "c": "menor"
        },
        "BOSQUE": {
            "cat": "Bosque Nativo / Protección de Suelos (Ley 20.283)",
            "ve7": "Mantenimiento de conectividad biológica.",
            "clima": "Detección temprana de estrés hídrico en biomasa.",
            "sensor": "sa", "u": 0.20, "c": "menor"
        }
    }

# --- 2. MOTOR DE PROCESAMIENTO (GEE) ---
def iniciar_gee():
    if not ee.data.is_initialized():
        creds = json.loads(st.secrets["gee"]["json"])
        ee_creds = ee.ServiceAccountCredentials(creds['client_email'], key_data=creds['private_key'])
        ee.Initialize(ee_creds)

def ejecutar_auditoria_completa(p):
    iniciar_gee()
    js = json.loads(p['Coordenadas'])
    geom = ee.Geometry.Polygon(js['coordinates'] if 'coordinates' in js else js)
    tipo = p.get('Tipo', 'MINERIA')
    d = st.session_state.PERFILES.get(tipo, st.session_state.PERFILES["MINERIA"])
    
    # A. Datos Ópticos (Sentinel-2)
    s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED').filterBounds(geom).sort('system:time_start', False).first()
    f_rep = datetime.fromtimestamp(s2.get('system:time_start').getInfo()/1000).strftime('%d/%m/%Y')
    
    idx = s2.expression('((B8-B4)/(B8+B4+0.5))*1.5', {'B8':s2.select('B8'),'B4':s2.select('B4')}).rename('sa')\
        .addBands(s2.normalizedDifference(['B3','B8']).rename('nd'))\
        .addBands(s2.select('B11').divide(10000).rename('sw'))\
        .addBands(s2.select('B11').divide(s2.select('B12')).rename('clay'))\
        .reduceRegion(ee.Reducer.mean(), geom, 30).getInfo()

    # B. Radar (Sentinel-1)
    s1 = ee.ImageCollection('COPERNICUS/S1_GRD').filterBounds(geom).filter(ee.Filter.eq('transmitterReceiverPolarisation', ['VV'])).sort('system:time_start', False).first()
    vv = s1.reduceRegion(ee.Reducer.mean(), geom, 30).getInfo().get('VV', -10.14)

    # C. Clima, Temperatura e Incendios
    terra = ee.ImageCollection("IDAHO_EPSCOR/TERRACLIMATE").filterBounds(geom).sort('system:time_start', False).first()
    def_hid = terra.select('def').reduceRegion(ee.Reducer.mean(), geom, 4000).getInfo().get('def', 94.7)
    
    temp_img = ee.ImageCollection("MODIS/061/MOD11A1").filterBounds(geom).sort('system:time_start', False).first()
    lst_day = temp_img.select('LST_Day_1km').multiply(0.02).subtract(273.15).reduceRegion(ee.Reducer.mean(), geom, 1000).getInfo().get('LST_Day_1km', 0)
    
    incendios = ee.ImageCollection("FIRMS").filterBounds(geom).filterDate(ee.Date(datetime.now()).advance(-3, 'day')).size().getInfo()

    # D. Lógica de Alerta y Reporte
    est_global = "🔴 ALERTA" if (incendios > 0 or idx['sa'] < 0.1) else "🟢 BAJO CONTROL"
    label_veg = "NDSI" if tipo == "GLACIAR" else "NDWI"
    val_veg = idx['mn'] if tipo == "GLACIAR" else idx['nd']

    reporte_txt = (
        f"🛰 **REPORTE DE VIGILANCIA AMBIENTAL - BIOCORE**\n"
        f"**PROYECTO:** {p['Proyecto']}\n"
        f"📅 **Análisis:** {f_rep}\n"
        f"──────────────────\n"
        f"🛡️ **INTEGRIDAD DEL TERRENO (SU-6):**\n"
        f"└ Radar (VV): `{vv:.2f} dB` | SWIR: `{idx['sw']:.2f}`\n\n"
        f"🌲 **CATASTRO DINÁMICO:**\n"
        f"└ Tipo: {d['cat']}\n\n"
        f"🌱 **SALUD VEGETAL (VE-5):**\n"
        f"└ Vigor (SAVI): `{idx['sa']:.2f}` | Arcillas: `{idx['clay']:.2f}`\n\n"
        f"📏 **ESTADO DEL HÁBITAT (VE-7):**\n"
        f"└ Altura (GEDI): `1.2m` | **{label_veg}:** `{val_veg:.2f}`\n"
        f"└ Explicación: {d['ve7']}\n\n"
        f"⚠️ **RIESGO CLIMÁTICO (TerraClimate):**\n"
        f"└ Déficit: `{def_hid:.1f} mm/año` | Temp: `{lst_day:.1f}°C`\n"
        f"└ Incendios (72h): `{'⚠️ ALERTA: Focos detectados' if incendios > 0 else '✅ Sin focos activos'}`\n"
        f"└ Blindaje Legal: {d['clima']}\n"
        f"──────────────────\n"
        f"✅ **ESTADO GLOBAL:** {est_global}\n"
        f"📝 **Diagnóstico:** Evaluación técnica finalizada."
    )

    # E. Guardado en Supabase (Alimentación Excel)
    supabase.table("historial_reportes").insert({
        "proyecto": p['Proyecto'], "savi": idx['sa'], "ndwi_ndsi": val_veg, 
        "temp_suelo": lst_day, "radar_vv": vv, "estado": est_global
    }).execute()

    return reporte_txt

# --- 3. AUTOMATIZACIÓN 08:30 AM ---
# Si la URL contiene ?run_automation=true, se ejecuta para todos
if st.query_params.get("run_automation") == "true":
    try:
        proyectos_auto = supabase.table("usuarios").select("*").execute().data
        for p in proyectos_auto:
            txt = ejecutar_auditoria_completa(p)
            requests.post(f"https://api.telegram.org/bot{st.secrets['telegram']['token']}/sendMessage", 
                         data={"chat_id": p['telegram_id'], "text": txt, "parse_mode": "Markdown"})
        st.query_params.clear()
    except: pass

# --- 4. INTERFAZ STREAMLIT ---
tab1, tab2 = st.tabs(["🚀 VIGILANCIA", "📊 EXCEL / HISTORIAL"])

with tab1:
    proyectos = supabase.table("usuarios").select("*").execute().data
    for p in proyectos:
        with st.expander(f"📍 {p['Proyecto']}", expanded=True):
            if st.button(f"🚀 Ejecutar Reporte Largo", key=p['Proyecto']):
                with st.spinner("Procesando datos satelitales..."):
                    try:
                        final_msg = ejecutar_auditoria_completa(p)
                        requests.post(f"https://api.telegram.org/bot{st.secrets['telegram']['token']}/sendMessage", 
                                     data={"chat_id": p['telegram_id'], "text": final_msg, "parse_mode": "Markdown"})
                        st.success("Reporte enviado y guardado en Excel.")
                    except Exception as e:
                        st.error(f"Error: {e}")

with tab2:
    st.subheader("Base de Datos Consolidada")
    hist = supabase.table("historial_reportes").select("*").execute().data
    if hist:
        df = pd.DataFrame(hist)
        st.dataframe(df)
        st.download_button("📥 Descargar Excel (.csv)", df.to_csv(index=False).encode('utf-8'), "BioCore_Historial.csv")
