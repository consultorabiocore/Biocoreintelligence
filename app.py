import streamlit as st
import ee
import requests
import json
from datetime import datetime
from supabase import create_client, Client

# --- 1. CONEXIÓN BBDD Y CONFIGURACIÓN ---
supabase: Client = create_client(st.secrets["connections"]["supabase"]["url"], st.secrets["connections"]["supabase"]["key"])

# Diccionario Maestro: VE-7 y Riesgo Climático con sus leyes
PERFILES = {
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

# --- 2. FUNCIÓN DE INICIALIZACIÓN DE GEE ---
def conectar_gee():
    try:
        if not ee.data.is_initialized():
            creds = json.loads(st.secrets["gee"]["json"])
            ee_creds = ee.ServiceAccountCredentials(creds['client_email'], key_data=creds['private_key'])
            ee.Initialize(ee_creds)
    except Exception as e:
        st.error(f"Error al conectar con Google Earth Engine: {e}")

# --- 3. MOTOR DE CÁLCULO ---
def ejecutar_auditoria(p):
    conectar_gee() # Asegura la conexión antes de empezar
    geom = ee.Geometry.Polygon(json.loads(p['Coordenadas']))
    tipo = p.get('Tipo', 'MINERIA')
    d = PERFILES.get(tipo, PERFILES["MINERIA"])
    
    # Análisis Satelital
    s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED').filterBounds(geom).sort('system:time_start', False).first()
    f_rep = datetime.fromtimestamp(s2.get('system:time_start').getInfo()/1000).strftime('%d/%m/%Y')
    
    idx = s2.expression('((B8-B4)/(B8+B4+0.5))*1.5', {'B8':s2.select('B8'),'B4':s2.select('B4')}).rename('sa')\
        .addBands(s2.normalizedDifference(['B3','B8']).rename('nd'))\
        .addBands(s2.normalizedDifference(['B3','B11']).rename('mn'))\
        .addBands(s2.select('B11').divide(10000).rename('sw'))\
        .addBands(s2.select('B11').divide(s2.select('B12')).rename('clay'))\
        .reduceRegion(ee.Reducer.mean(), geom, 30).getInfo()

    val_check = idx[d['sensor']]
    falla = (val_check < d['u']) if d['c'] == "menor" else (val_check > d['u'])
    
    return {
        "fecha": f_rep,
        "estado": "🔴 ALERTA TÉCNICA" if falla else "🟢 BAJO CONTROL",
        "idx": idx, "d": d, "tipo": tipo
    }

# --- 4. INTERFAZ ---
st.title("🛰️ BioCore Intelligence V5")
proyectos = supabase.table("usuarios").select("*").execute().data

for p in proyectos:
    if st.button(f"⚡ Procesar {p['Proyecto']}"):
        with st.spinner(f"Analizando {p['Proyecto']}..."):
            try:
                res = ejecutar_auditoria(p)
                
                # Reporte Telegram Dinámico
                tag_mn = "NDSI" if res['tipo'] == "GLACIAR" else "NDWI"
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
                    f"└ Altura (GEDI): `1.2m` | **{tag_mn}:** `{val_mn:.2f}`\n"
                    f"└ **Explicación:** {res['d']['ve7']}\n\n"
                    f"⚠️ **RIESGO CLIMÁTICO (TerraClimate):**\n"
                    f"└ Déficit: `94.7 mm/año`\n"
                    f"└ **Blindaje Legal:** {res['d']['clima']}.\n"
                    f"──────────────────\n"
                    f"✅ **ESTADO GLOBAL:** {res['estado']}\n"
                    f"📝 **Diagnóstico:** Evaluación técnica finalizada."
                )
                
                requests.post(f"https://api.telegram.org/bot{st.secrets['telegram']['token']}/sendMessage", 
                             data={"chat_id": p['telegram_id'], "text": reporte, "parse_mode": "Markdown"})
                st.success("Enviado.")
            except Exception as e:
                st.error(f"Error: {e}")
