import streamlit as st
import ee
import folium
from streamlit_folium import folium_static
import json
import pandas as pd
import requests
from datetime import datetime
from supabase import create_client, Client

# --- 1. CONFIGURACIÓN Y CONEXIONES ---
st.set_page_config(page_title="BioCore Intelligence V5", layout="wide")

# Conexión Supabase
supabase: Client = create_client(st.secrets["connections"]["supabase"]["url"], st.secrets["connections"]["supabase"]["key"])

# Perfiles Técnicos y Legales
if 'PERFILES' not in st.session_state:
    st.session_state.PERFILES = {
        "HUMEDAL": {"cat": "Ley 21.202", "ve7": "Refugio fauna silvestre.", "clima": "Balance hídrico.", "sensor": "nd", "u": 0.1, "c": "menor"},
        "MINERIA": {"cat": "Formulario F-30", "ve7": "Estabilidad sustrato cierre.", "clima": "Control aridez.", "sensor": "sw", "u": 0.45, "c": "mayor"},
        "GLACIAR": {"cat": "RCA Pascua Lama", "ve7": "Protección criosférica.", "clima": "Vigilancia albedo.", "sensor": "mn", "u": 0.35, "c": "menor"},
        "BOSQUE": {"cat": "Ley 20.283", "ve7": "Conectividad biológica.", "clima": "Estrés hídrico.", "sensor": "sa", "u": 0.20, "c": "menor"}
    }

# --- 2. MOTOR DE ANÁLISIS ---
def conectar_gee():
    if not ee.data.is_initialized():
        creds = json.loads(st.secrets["gee"]["json"])
        ee_creds = ee.ServiceAccountCredentials(creds['client_email'], key_data=creds['private_key'])
        ee.Initialize(ee_creds)

def ejecutar_auditoria_completa(p):
    conectar_gee()
    js = json.loads(p['Coordenadas'])
    geom = ee.Geometry.Polygon(js['coordinates'] if 'coordinates' in js else js)
    tipo = p.get('Tipo', 'MINERIA')
    d = st.session_state.PERFILES.get(tipo, st.session_state.PERFILES["MINERIA"])
    
    # Análisis Multicapa
    s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED').filterBounds(geom).sort('system:time_start', False).first()
    f_rep = datetime.fromtimestamp(s2.get('system:time_start').getInfo()/1000).strftime('%d/%m/%Y')
    
    # Radar e Índices
    s1 = ee.ImageCollection('COPERNICUS/S1_GRD').filterBounds(geom).filter(ee.Filter.eq('transmitterReceiverPolarisation', ['VV'])).sort('system:time_start', False).first()
    vv = s1.reduceRegion(ee.Reducer.mean(), geom, 30).getInfo().get('VV', -10.14)
    
    idx = s2.expression('((B8-B4)/(B8+B4+0.5))*1.5', {'B8':s2.select('B8'),'B4':s2.select('B4')}).rename('sa')\
        .addBands(s2.normalizedDifference(['B3','B8']).rename('nd'))\
        .addBands(s2.normalizedDifference(['B3','B11']).rename('mn'))\
        .addBands(s2.select('B11').divide(10000).rename('sw'))\
        .addBands(s2.select('B11').divide(s2.select('B12')).rename('clay'))\
        .reduceRegion(ee.Reducer.mean(), geom, 30).getInfo()

    # Amenazas y Clima
    temp_img = ee.ImageCollection("MODIS/061/MOD11A1").filterBounds(geom).sort('system:time_start', False).first()
    temp = temp_img.select('LST_Day_1km').multiply(0.02).subtract(273.15).reduceRegion(ee.Reducer.mean(), geom, 1000).getInfo().get('LST_Day_1km', 0)
    
    fuego = ee.ImageCollection("FIRMS").filterBounds(geom).filterDate(ee.Date(datetime.now()).advance(-7, 'day')).size().getInfo()

    # Estado Alerta
    falla = (idx[d['sensor']] < d['u']) if d['c'] == "menor" else (idx[d['sensor']] > d['u'])
    estado = "🔴 ALERTA" if (falla or fuego > 0) else "🟢 BAJO CONTROL"

    res = {"fecha": f_rep, "vv": vv, "idx": idx, "temp": temp, "fuego": fuego, "estado": estado, "d": d, "tipo": tipo}
    
    # GUARDADO EN HISTORIAL (Excel Alimentación)
    supabase.table("historial_reportes").insert({
        "proyecto": p['Proyecto'], "savi": idx['sa'], "temp_suelo": temp, "radar_vv": vv, "estado": estado
    }).execute()
    
    return res

# --- 3. AUTOMATIZACIÓN 08:30 AM ---
if st.query_params.get("run_automation") == "true":
    proyectos_auto = supabase.table("usuarios").select("*").execute().data
    for p in proyectos_auto:
        res = ejecutar_auditoria_completa(p)
        # Lógica de reporte largo de Telegram aquí...
        requests.post(f"https://api.telegram.org/bot{st.secrets['telegram']['token']}/sendMessage", 
                     data={"chat_id": p['telegram_id'], "text": f"Reporte Auto: {res['estado']}", "parse_mode": "Markdown"})
    st.query_params.clear()

# --- 4. INTERFAZ ---
tab1, tab2, tab3 = st.tabs(["🚀 VIGILANCIA", "📊 EXCEL/HISTORIAL", "⚙️ CONFIG"])

with tab1:
    # (Interfaz de mapas y botón manual...)
    pass

with tab2:
    st.subheader("Historial acumulado para Excel")
    hist = supabase.table("historial_reportes").select("*").execute().data
    if hist:
        df = pd.DataFrame(hist)
        st.dataframe(df)
        st.download_button("📥 Descargar Excel (.csv)", data=df.to_csv().encode('utf-8'), file_name="BioCore_Historial.csv")
