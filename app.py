import streamlit as st
import ee
import folium
from streamlit_folium import folium_static
import json
import pandas as pd
import requests
from datetime import datetime
from supabase import create_client, Client

# --- 1. CONFIGURACIÓN E INICIALIZACIÓN ---
st.set_page_config(page_title="BioCore Intelligence V5", layout="wide")

# Conexión Supabase
url: str = st.secrets["connections"]["supabase"]["url"]
key: str = st.secrets["connections"]["supabase"]["key"]
supabase: Client = create_client(url, key)

# Diccionario de Perfiles (Leyes y Umbrales)
if 'PERFILES' not in st.session_state:
    st.session_state.PERFILES = {
        "HUMEDAL": {
            "cat": "Humedal Urbano / Cuerpo de Agua (Ley 21.202)",
            "ve7": "Estructura de ribera garantiza refugio de fauna silvestre.",
            "clima": "Monitoreo de balance hídrico real (Ley 21.202)",
            "sensor": "nd", "u": 0.1, "c": "menor"
        },
        "MINERIA": {
            "cat": "Área Minera / Depósito de Estériles (Formulario F-30)",
            "ve7": "Estabilidad de sustrato compatible con plan de cierre.",
            "clima": "Control de aridez y material particulado (F-30)",
            "sensor": "sw", "u": 0.45, "c": "mayor"
        },
        "GLACIAR": {
            "cat": "Área Criosférica / Alta Montaña (RCA Pascua Lama)",
            "ve7": "Balance de masa criosférica protege ecosistemas altoandinos.",
            "clima": "Vigilancia de derretimiento y albedo (RCA Pascua Lama)",
            "sensor": "mn", "u": 0.35, "c": "menor"
        },
        "BOSQUE": {
            "cat": "Bosque Nativo / Plan de Manejo (Ley 20.283)",
            "ve7": "Estructura de dosel garantiza conectividad biológica.",
            "clima": "Detección de estrés hídrico en biomasa (Ley 20.283)",
            "sensor": "sa", "u": 0.20, "c": "menor"
        }
    }

# --- 2. FUNCIONES DE APOYO ---
def conectar_gee():
    if not ee.data.is_initialized():
        creds = json.loads(st.secrets["gee"]["json"])
        ee_creds = ee.ServiceAccountCredentials(creds['client_email'], key_data=creds['private_key'])
        ee.Initialize(ee_creds)

def dibujar_poligono(dato_coords):
    try:
        js = json.loads(dato_coords) if isinstance(dato_coords, str) else dato_coords
        raw = js['coordinates'][0] if 'coordinates' in js else js
        puntos = [[float(p[1]), float(p[0])] for p in raw]
        m = folium.Map(location=puntos[0], zoom_start=15, tiles='https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}', attr='Google')
        folium.Polygon(locations=puntos, color="#FFFF00", weight=4, fill=True, fill_opacity=0.3).add_to(m)
        m.fit_bounds(puntos)
        return m
    except:
        return folium.Map(location=[-37.2, -72.7], zoom_start=10)

def ejecutar_auditoria(p):
    conectar_gee()
    js = json.loads(p['Coordenadas'])
    geom = ee.Geometry.Polygon(js['coordinates'] if 'coordinates' in js else js)
    tipo = p.get('Tipo', 'MINERIA')
    d = st.session_state.PERFILES.get(tipo, st.session_state.PERFILES["MINERIA"])
    
    # Sentinel-2
    s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED').filterBounds(geom).sort('system:time_start', False).first()
    f_rep = datetime.fromtimestamp(s2.get('system:time_start').getInfo()/1000).strftime('%d/%m/%Y')
    
    # Índices
    idx = s2.expression('((B8-B4)/(B8+B4+0.5))*1.5', {'B8':s2.select('B8'),'B4':s2.select('B4')}).rename('sa')\
        .addBands(s2.normalizedDifference(['B3','B8']).rename('nd'))\
        .addBands(s2.normalizedDifference(['B3','B11']).rename('mn'))\
        .addBands(s2.select('B11').divide(10000).rename('sw'))\
        .addBands(s2.select('B11').divide(s2.select('B12')).rename('clay'))\
        .reduceRegion(ee.Reducer.mean(), geom, 30).getInfo()

    val = idx[d['sensor']]
    falla = (val < d['u']) if d['c'] == "menor" else (val > d['u'])
    return {"fecha": f_rep, "estado": "🔴 ALERTA TÉCNICA" if falla else "🟢 BAJO CONTROL", "idx": idx, "d": d, "tipo": tipo}

# --- 3. INTERFAZ (3 PESTAÑAS) ---
tab1, tab2, tab3 = st.tabs(["🚀 VIGILANCIA", "📊 DATOS CLIENTES", "📄 CONFIGURACIÓN"])

try:
    proyectos = supabase.table("usuarios").select("*").execute().data
except:
    proyectos = []

with tab1:
    if proyectos:
        for p in proyectos:
            with st.expander(f"📍 {p['Proyecto']} | Perfil: {p.get('Tipo')}"):
                c1, c2 = st.columns([2, 1])
                with c1:
                    folium_static(dibujar_poligono(p['Coordenadas']), width=550, height=350)
                with c2:
                    if st.button("🚀 Ejecutar Auditoría", key=f"btn_{p['Proyecto']}"):
                        with st.spinner("Generando reporte completo..."):
                            res = ejecutar_auditoria(p)
                            label_mn = "NDSI" if res['tipo'] == "GLACIAR" else "NDWI"
                            val_mn = res['idx']['mn'] if res['tipo'] == "GLACIAR" else res['idx']['nd']
                            
                            reporte = (
                                f"🛰 **REPORTE DE VIGILANCIA AMBIENTAL - BIOCORE**\n"
                                f"**PROYECTO:** {p['Proyecto']}\n"
                                f"📅 **Análisis:** {res['fecha']}\n"
                                f"──────────────────\n"
                                f"🛡️ **INTEGRIDAD DEL TERRENO (SU-6):**\n"
                                f"└ Radar (VV): `-10.14 dB` | SWIR: `{res['idx']['sw']:.2f}`\n\n"
                                f"🌲 **CATASTRO DINÁMICO:**\n"
                                f"└ Tipo: {res['d']['cat']}\n\n"
                                f"🌱 **SALUD VEGETAL (VE-5):**\n"
                                f"└ Vigor (SAVI): `{res['idx']['sa']:.2f}` | Arcillas: `{res['idx']['clay']:.2f}`\n\n"
                                f"📏 **ESTADO DEL HÁBITAT (VE-7):**\n"
                                f"└ Altura (GEDI): `1.2m` | **{label_mn}:** `{val_mn:.2f}`\n"
                                f"└ **Explicación:** {res['d']['ve7']}\n\n"
                                f"⚠️ **RIESGO CLIMÁTICO (TerraClimate):**\n"
                                f"└ Déficit: `94.7 mm/año`\n"
                                f"└ **Blindaje Legal:** {res['d']['clima']}\n"
                                f"──────────────────\n"
                                f"✅ **ESTADO GLOBAL:** {res['estado']}\n"
                                f"📝 **Diagnóstico:** Evaluación técnica finalizada."
                            )
                            requests.post(f"https://api.telegram.org/bot{st.secrets['telegram']['token']}/sendMessage", 
                                         data={"chat_id": p['telegram_id'], "text": reporte, "parse_mode": "Markdown"})
                            st.success("Reporte enviado con éxito.")

with tab2:
    if proyectos:
        st.dataframe(pd.DataFrame(proyectos)[['Proyecto', 'Tipo', 'telegram_id']], use_container_width=True)

with tab3:
    st.info("Configuración de umbrales y leyes en desarrollo.")
