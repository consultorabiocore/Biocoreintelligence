import streamlit as st
import ee
import folium
from streamlit_folium import folium_static
import json
import pandas as pd
import requests
from datetime import datetime
from supabase import create_client, Client

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="BioCore Intelligence V5", layout="wide")

# Conexión Supabase
url: str = st.secrets["connections"]["supabase"]["url"]
key: str = st.secrets["connections"]["supabase"]["key"]
supabase: Client = create_client(url, key)

if 'PERFILES' not in st.session_state:
    st.session_state.PERFILES = {
        "HUMEDAL": {"cat": "Ley 21.202", "ve7": "Refugio fauna silvestre.", "clima": "Balance hídrico.", "sensor": "nd", "u": 0.1, "c": "menor"},
        "MINERIA": {"cat": "Formulario F-30", "ve7": "Estabilidad sustrato.", "clima": "Control aridez.", "sensor": "sw", "u": 0.45, "c": "mayor"},
        "GLACIAR": {"cat": "RCA Pascua Lama", "ve7": "Protección criosférica.", "clima": "Vigilancia albedo.", "sensor": "mn", "u": 0.35, "c": "menor"},
        "BOSQUE": {"cat": "Ley 20.283", "ve7": "Conectividad biológica.", "clima": "Estrés hídrico.", "sensor": "sa", "u": 0.20, "c": "menor"}
    }

# --- 2. FUNCIONES TÉCNICAS ---
def conectar_gee():
    if not ee.data.is_initialized():
        creds = json.loads(st.secrets["gee"]["json"])
        ee_creds = ee.ServiceAccountCredentials(creds['client_email'], key_data=creds['private_key'])
        ee.Initialize(ee_creds)

def dibujar_mapa_pro(dato_coords):
    try:
        js = json.loads(dato_coords) if isinstance(dato_coords, str) else dato_coords
        raw = js['coordinates'][0] if 'coordinates' in js else js
        puntos = [[float(p[1]), float(p[0])] for p in raw]
        m = folium.Map(location=puntos[0], zoom_start=15, tiles='https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}', attr='Google Satellite')
        folium.Polygon(locations=puntos, color="#FFFF00", weight=4, fill=True, fill_opacity=0.2).add_to(m)
        m.fit_bounds(puntos)
        return m
    except: return folium.Map(location=[-37.2, -72.7], zoom_start=12)

def analizar_amenazas(geom):
    incendios = ee.ImageCollection("FIRMS").filterBounds(geom).filterDate(ee.Date(datetime.now()).advance(-7, 'day')).size().getInfo()
    temp_img = ee.ImageCollection("MODIS/061/MOD11A1").filterBounds(geom).sort('system:time_start', False).first()
    temp_c = temp_img.select('LST_Day_1km').multiply(0.02).subtract(273.15).reduceRegion(ee.Reducer.mean(), geom, 1000).getInfo()
    return incendios, temp_c.get('LST_Day_1km', 0)

def ejecutar_auditoria(p):
    conectar_gee()
    js = json.loads(p['Coordenadas'])
    geom = ee.Geometry.Polygon(js['coordinates'] if 'coordinates' in js else js)
    tipo = p.get('Tipo', 'MINERIA')
    d = st.session_state.PERFILES.get(tipo, st.session_state.PERFILES["MINERIA"])
    s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED').filterBounds(geom).sort('system:time_start', False).first()
    f_rep = datetime.fromtimestamp(s2.get('system:time_start').getInfo()/1000).strftime('%d/%m/%Y')
    idx = s2.expression('((B8-B4)/(B8+B4+0.5))*1.5', {'B8':s2.select('B8'),'B4':s2.select('B4')}).rename('sa')\
        .addBands(s2.normalizedDifference(['B3','B8']).rename('nd'))\
        .addBands(s2.normalizedDifference(['B3','B11']).rename('mn'))\
        .addBands(s2.select('B11').divide(10000).rename('sw'))\
        .addBands(s2.select('B11').divide(s2.select('B12')).rename('clay'))\
        .reduceRegion(ee.Reducer.mean(), geom, 30).getInfo()
    fuego, temp = analizar_amenazas(geom)
    val = idx[d['sensor']]
    falla = (val < d['u']) if d['c'] == "menor" else (val > d['u'])
    return {"fecha": f_rep, "estado": "🔴 ALERTA" if (falla or fuego > 0) else "🟢 BAJO CONTROL", 
            "idx": idx, "d": d, "tipo": tipo, "fuego": fuego, "temp": temp}

# --- 3. INTERFAZ ---
try:
    proyectos = supabase.table("usuarios").select("*").execute().data
except:
    proyectos = []

t1, t2, t3 = st.tabs(["🚀 VIGILANCIA PRINCIPAL", "📊 INFORME TÉCNICO", "⚙️ CONFIG"])

with t1:
    if proyectos:
        for p in proyectos:
            st.subheader(f"📍 {p['Proyecto']}")
            c_m, c_a = st.columns([3, 1])
            with c_m: folium_static(dibujar_mapa_pro(p['Coordenadas']), width=850, height=450)
            with c_a:
                if st.button("⚡ Disparar Auditoría", key=f"run_{p['Proyecto']}"):
                    res = ejecutar_auditoria(p)
                    reporte = f"🛰 **REPORTE BIOCORE**\n**PROYECTO:** {p['Proyecto']}\n📅 **Análisis:** {res['fecha']}\n──────────────────\n🔥 **INCENDIOS:** {'⚠️ ALERTA' if res['fuego']>0 else '✅ SIN ALERTAS'}\n🌡️ **TEMP:** `{res['temp']:.1f}°C`\n🛡️ **INTEGRIDAD:** SWIR `{res['idx']['sw']:.2f}`\n🌱 **SALUD:** SAVI `{res['idx']['sa']:.2f}`\n📏 **HABITAT:** {res['d']['ve7']}\n──────────────────\n✅ **ESTADO:** {res['estado']}"
                    requests.post(f"https://api.telegram.org/bot{st.secrets['telegram']['token']}/sendMessage", 
                                 data={"chat_id": p['telegram_id'], "text": reporte, "parse_mode": "Markdown"})
                    st.success("Enviado")
            st.divider()

with t2:
    st.subheader("Generación de Informe Ejecutivo")
    if proyectos:
        sel = st.selectbox("Seleccione el proyecto para ver el histórico:", [p['Proyecto'] for p in proyectos])
        p_sel = next(item for item in proyectos if item["Proyecto"] == sel)
        df = pd.DataFrame([{"Parámetro": "LST (Temp)", "Valor": "24.5 °C"}, {"Parámetro": "SAVI", "Valor": "0.02"}, {"Parámetro": "NDWI", "Valor": "-0.11"}])
        st.write(f"### Análisis de Cumplimiento: {sel}")
        st.table(df)
        st.download_button("📥 Descargar Reporte PDF", data="...", file_name=f"Informe_{sel}.pdf")

with t3:
    st.write("Panel administrativo.")
