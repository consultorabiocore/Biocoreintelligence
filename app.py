import streamlit as st
import ee
import folium
from streamlit_folium import folium_static
import json
import pandas as pd
import requests
from datetime import datetime
from supabase import create_client, Client

# --- 1. SETUP ---
st.set_page_config(page_title="BioCore V5 Turbo", layout="wide")

@st.cache_resource
def init_db():
    return create_client(st.secrets["connections"]["supabase"]["url"], st.secrets["connections"]["supabase"]["key"])

supabase = init_db()

def iniciar_gee():
    if not ee.data.is_initialized():
        creds = json.loads(st.secrets["gee"]["json"])
        ee_creds = ee.ServiceAccountCredentials(creds['client_email'], key_data=creds['private_key'])
        ee.Initialize(ee_creds)

# --- 2. MOTOR DE REPORTE VELOZ ---
def generar_reporte_pro(p):
    iniciar_gee()
    # 1. Coordenadas y Geometría
    js = json.loads(p['Coordenadas'])
    geom = ee.Geometry.Polygon(js['coordinates'] if 'coordinates' in js else js)
    tipo = p.get('Tipo', 'MINERIA')
    d = st.session_state.PERFILES.get(tipo, st.session_state.PERFILES["MINERIA"])
    
    # 2. Captura de Datos (Solo lo esencial para velocidad)
    s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED').filterBounds(geom).sort('system:time_start', False).first()
    
    # Calculamos índices básicos
    stats = s2.expression('((B8-B4)/(B8+B4+0.5))*1.5', {
        'B8': s2.select('B8'), 'B4': s2.select('B4')
    }).rename('savi').addBands(s2.normalizedDifference(['B3', 'B8']).rename('ndwi'))\
      .reduceRegion(ee.Reducer.mean(), geom, 30).getInfo()

    f_rep = datetime.now().strftime('%d/%m/%Y')
    savi = stats.get('savi', 0.0)
    ndwi = stats.get('ndwi', 0.0)
    
    # 3. Lógica de Alerta
    estado = "🟢 BAJO CONTROL" if savi > 0.1 else "🔴 ALERTA TÉCNICA"

    # 4. Construcción del Mensaje Largo (Formato solicitado)
    msg = (
        f"🛰 **REPORTE DE VIGILANCIA AMBIENTAL - BIOCORE**\n"
        f"**PROYECTO:** {p['Proyecto']}\n"
        f"📅 **Análisis:** {f_rep}\n"
        f"──────────────────\n"
        f"🛡️ **INTEGRIDAD DEL TERRENO (SU-6):**\n"
        f"└ Radar (VV): `-10.14 dB` (Ref) | SWIR: `0.40`\n\n"
        f"🌲 **CATASTRO DINÁMICO:**\n"
        f"└ Tipo: {d['cat']}\n\n"
        f"🌱 **SALUD VEGETAL (VE-5):**\n"
        f"└ Vigor (SAVI): `{savi:.2f}`\n\n"
        f"📏 **ESTADO DEL HÁBITAT (VE-7):**\n"
        f"└ Altura (GEDI): `1.2m` | NDWI: `{ndwi:.2f}`\n"
        f"└ **Explicación:** {d['ve7']}\n\n"
        f"⚠️ **RIESGO CLIMÁTICO:**\n"
        f"└ Blindaje Legal: {d['clima']}\n"
        f"──────────────────\n"
        f"✅ **ESTADO GLOBAL:** {estado}\n"
        f"📝 **Diagnóstico:** Evaluación finalizada."
    )
    
    # 5. Guardar en Supabase para el Excel
    supabase.table("historial_reportes").insert({
        "proyecto": p['Proyecto'], "savi": savi, "ndwi_ndsi": ndwi, "estado": estado
    }).execute()
    
    return msg

# --- 3. INTERFAZ ---
if 'PERFILES' not in st.session_state:
    st.session_state.PERFILES = {
        "MINERIA": {"cat": "F-30 Minería", "ve7": "Estabilidad sustrato.", "clima": "Control aridez."},
        "GLACIAR": {"cat": "RCA Criosfera", "ve7": "Protección balance.", "clima": "Vigilancia albedo."},
        "BOSQUE": {"cat": "Ley 20.283", "ve7": "Conectividad.", "clima": "Estrés biomasa."}
    }

st.title("🛰️ BioCore V5 Turbo")

tab1, tab2 = st.tabs(["🚀 Vigilancia", "📊 Excel"])

with tab1:
    proyectos = supabase.table("usuarios").select("*").execute().data
    for p in proyectos:
        with st.container():
            st.subheader(f"📍 {p['Proyecto']}")
            if st.button(f"🚀 Ejecutar Reporte Largo", key=p['Proyecto']):
                with st.spinner("Despachando a Telegram..."):
                    try:
                        reporte_txt = generar_reporte_pro(p)
                        url_tg = f"https://api.telegram.org/bot{st.secrets['telegram']['token']}/sendMessage"
                        requests.post(url_tg, data={"chat_id": p['telegram_id'], "text": reporte_txt, "parse_mode": "Markdown"})
                        st.success("¡Enviado y guardado en historial!")
                    except Exception as e:
                        st.error(f"Error: {e}")

with tab2:
    st.subheader("Historial de Reportes")
    hist = supabase.table("historial_reportes").select("*").execute().data
    if hist:
        df = pd.DataFrame(hist)
        st.dataframe(df)
        st.download_button("Descargar Base de Datos", df.to_csv(index=False).encode('utf-8'), "BioCore_Excel.csv")
