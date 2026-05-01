import streamlit as st
import ee
import folium
from streamlit_folium import folium_static
import json
import pandas as pd
import requests
from datetime import datetime
from supabase import create_client, Client

# --- 1. CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="BioCore Intelligence V5", layout="wide")

# --- 2. CONEXIONES Y ESTADO DE SESIÓN ---
url: str = st.secrets["connections"]["supabase"]["url"]
key: str = st.secrets["connections"]["supabase"]["key"]
supabase: Client = create_client(url, key)

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
        },
        "INDUSTRIAL": {
            "cat": "Zona de Impacto / Logística (Formulario F-22)",
            "ve7": "Monitoreo de sellado de suelo y escorrentía.",
            "clima": "Gestión de pluviosidad y drenaje (F-22)",
            "sensor": "sw", "u": 0.50, "c": "mayor"
        }
    }

# --- 3. FUNCIONES TÉCNICAS (GEE Y MAPAS) ---
def conectar_gee():
    if not ee.data.is_initialized():
        creds = json.loads(st.secrets["gee"]["json"])
        ee_creds = ee.ServiceAccountCredentials(creds['client_email'], key_data=creds['private_key'])
        ee.Initialize(ee_creds)

def dibujar_poligono(dato_coords):
    try:
        js = json.loads(dato_coords) if isinstance(dato_coords, str) else dato_coords
        raw = js['coordinates'][0] if 'coordinates' in js else js
        # Inversión lon,lat -> lat,lon
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
    
    s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED').filterBounds(geom).sort('system:time_start', False).first()
    f_rep = datetime.fromtimestamp(s2.get('system:time_start').getInfo()/1000).strftime('%d/%m/%Y')
    
    idx = s2.expression('((B8-B4)/(B8+B4+0.5))*1.5', {'B8':s2.select('B8'),'B4':s2.select('B4')}).rename('sa')\
        .addBands(s2.normalizedDifference(['B3','B8']).rename('nd'))\
        .addBands(s2.normalizedDifference(['B3','B11']).rename('mn'))\
        .addBands(s2.select('B11').divide(10000).rename('sw'))\
        .addBands(s2.select('B11').divide(s2.select('B12')).rename('clay'))\
        .reduceRegion(ee.Reducer.mean(), geom, 30).getInfo()

    val = idx[d['sensor']]
    falla = (val < d['u']) if d['c'] == "menor" else (val > d['u'])
    return {"fecha": f_rep, "estado": "🔴 ALERTA" if falla else "🟢 CONTROL", "idx": idx, "d": d, "tipo": tipo}

# --- 4. INTERFAZ PRINCIPAL ---
st.title("🛰️ BioCore Intelligence V5")

try:
    proyectos = supabase.table("usuarios").select("*").execute().data
except:
    proyectos = []

t1, t2, t3 = st.tabs(["🚀 VIGILANCIA", "📊 CLIENTES", "📄 CONFIG"])

with t1:
    if proyectos:
        for p in proyectos:
            with st.expander(f"📍 {p['Proyecto']} | {p.get('Tipo')}"):
                c1, c2 = st.columns([2, 1])
                with c1:
                    folium_static(dibujar_poligono(p['Coordenadas']), width=550, height=350)
                with c2:
                    if st.button("Ejecutar Auditoría", key=f"btn_{p['Proyecto']}"):
                        with st.spinner("Analizando satélites..."):
                            res = ejecutar_auditoria(p)
                            label_mn = "NDSI" if res['tipo'] == "GLACIAR" else "NDWI"
                            val_mn = res['idx']['mn'] if res['tipo'] == "GLACIAR" else res['idx']['nd']
                            
                            reporte = (
                                f"🛰 **REPORTE BIOCORE**\n**PROYECTO:** {p['Proyecto']}\n"
                                f"📅 **Análisis:** {res['fecha']}\n"
                                f"──────────────────\n"
                                f"🌲 **CATASTRO:** {res['d']['cat']}\n"
                                f"📏 **VE-7:** {res['d']['ve7']}\n"
                                f"└ **{label_mn}:** `{val_mn:.2f}`\n"
                                f"⚠️ **CLIMA:** {res['d']['clima']}\n"
                                f"──────────────────\n"
                                f"✅ **ESTADO:** {res['estado']}"
                            )
                            requests.post(f"https://api.telegram.org/bot{st.secrets['telegram']['token']}/sendMessage", 
                                         data={"chat_id": p['telegram_id'], "text": reporte, "parse_mode": "Markdown"})
                            st.success("Reporte enviado.")
    else: st.warning("Sin datos.")

with t2:
    if proyectos:
        st.dataframe(pd.DataFrame(proyectos)[['Proyecto', 'Tipo', 'telegram_id']], use_container_width=True)

with t3:
    st.write("Ajuste de leyes y umbrales por perfil.")
    # Aquí puedes añadir el selectbox y formulario de edición que ya teníamos
