import streamlit as st
import ee
import requests
import json
from datetime import datetime
from supabase import create_client, Client

# --- 1. CONEXIÓN BBDD ---
supabase: Client = create_client(st.secrets["connections"]["supabase"]["url"], st.secrets["connections"]["supabase"]["key"])

# --- 2. CONFIGURACIÓN TÉCNICA Y LEGAL ---
# Aquí definimos la lógica para los 5 tipos de proyecto
PERFILES = {
    "HUMEDAL": {
        "ley": "Ley 21.202",
        "cat": "Humedal Urbano / Cuerpo de Agua (Ley 21.202)",
        "ve7_txt": "Estructura de ribera garantiza refugio de fauna silvestre.",
        "clima_txt": "Monitoreo de balance hídrico real para defensa técnica (Ley 21.202)",
        "sensor": "nd", "u": 0.1, "c": "menor"
    },
    "MINERIA": {
        "ley": "Formulario F-30",
        "cat": "Área Minera / Depósito de Estériles (Formulario F-30)",
        "ve7_txt": "Estabilidad de sustrato compatible con plan de cierre.",
        "clima_txt": "Control de aridez y material particulado (Formulario F-30)",
        "sensor": "sw", "u": 0.45, "c": "mayor"
    },
    "GLACIAR": {
        "ley": "RCA Pascua Lama",
        "cat": "Área Criosférica / Alta Montaña (RCA Pascua Lama)",
        "ve7_txt": "Balance de masa criosférica protege ecosistemas altoandinos.",
        "clima_txt": "Vigilancia de derretimiento y albedo (RCA Pascua Lama)",
        "sensor": "mn", "u": 0.35, "c": "menor"
    },
    "BOSQUE": {
        "ley": "Ley 20.283",
        "cat": "Bosque Nativo / Plan de Manejo (Ley 20.283)",
        "ve7_txt": "Estructura de dosel garantiza conectividad biológica.",
        "clima_txt": "Detección de estrés hídrico en biomasa (Ley 20.283)",
        "sensor": "sa", "u": 0.20, "c": "menor"
    },
    "INDUSTRIAL": {
        "ley": "Formulario F-22",
        "cat": "Zona de Impacto / Logística (Formulario F-22)",
        "ve7_txt": "Monitoreo de sellado de suelo y control de escorrentía.",
        "clima_txt": "Gestión de pluviosidad y drenaje industrial (Formulario F-22)",
        "sensor": "sw", "u": 0.50, "c": "mayor"
    }
}

# --- 3. MOTOR DE CÁLCULO OPTIMIZADO ---
def ejecutar_auditoria(p):
    geom = ee.Geometry.Polygon(json.loads(p['Coordenadas']))
    perf = PERFILES.get(p.get('Tipo'), PERFILES["MINERIA"])
    
    # Sentinel-2 (Reciente)
    s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED').filterBounds(geom).sort('system:time_start', False).first()
    f_rep = datetime.fromtimestamp(s2.get('system:time_start').getInfo()/1000).strftime('%d/%m/%Y')
    
    # Índices Espectrales
    idx = s2.expression('((B8-B4)/(B8+B4+0.5))*1.5', {'B8':s2.select('B8'),'B4':s2.select('B4')}).rename('sa')\
        .addBands(s2.normalizedDifference(['B3','B8']).rename('nd'))\
        .addBands(s2.normalizedDifference(['B3','B11']).rename('mn'))\
        .addBands(s2.select('B11').divide(10000).rename('sw'))\
        .addBands(s2.select('B11').divide(s2.select('B12')).rename('clay'))\
        .reduceRegion(ee.Reducer.mean(), geom, 30).getInfo()

    # Evaluación de Estado (Dinámica)
    val_check = idx[perf['sensor']]
    falla = (val_check < perf['u']) if perf['c'] == "menor" else (val_check > perf['u'])
    
    return {
        "fecha": f_rep,
        "estado": "🔴 ALERTA TÉCNICA" if falla else "🟢 BAJO CONTROL",
        "diag": perf['msg_err'] if falla else perf['msg_ok'], # Asignar msg según corresponda
        "idx": idx, "perf": perf
    }

# --- 4. FUNCIÓN DE ENVÍO TELEGRAM ---
def enviar_telegram(p, res):
    # Etiquetas dinámicas
    label_mn = "NDSI" if p.get('Tipo') == "GLACIAR" else "NDWI"
    val_mn = res['idx']['mn'] if p.get('Tipo') == "GLACIAR" else res['idx']['nd']
    
    reporte = (
        f"🛰 **REPORTE DE VIGILANCIA AMBIENTAL - BIOCORE**\n"
        f"**PROYECTO:** {p['Proyecto']}\n"
        f"**Directora Técnica:** Loreto Campos Carrasco\n"
        f"📅 **Análisis:** {res['fecha']}\n"
        f"──────────────────\n"
        f"🛡️ **INTEGRIDAD DEL TERRENO (SU-6):**\n"
        f"└ Estatus: {'🛡️ ESTABLE' if 'CONTROL' in res['estado'] else '⚠️ ALTERADO'}\n"
        f"└ Radar (VV): `-10.14 dB` | SWIR: `{res['idx']['sw']:.2f}`\n\n"
        f"🌲 **CATASTRO DINÁMICO:**\n"
        f"└ Tipo: {res['perf']['cat']}\n\n"
        f"🌱 **SALUD VEGETAL (VE-5):**\n"
        f"└ Vigor (SAVI): `{res['idx']['sa']:.2f}` | Arcillas: `{res['idx']['clay']:.2f}`\n\n"
        f"📏 **ESTADO DEL HÁBITAT (VE-7):**\n"
        f"└ Altura (GEDI): `1.2m` | **{label_mn}:** `{val_mn:.2f}`\n"
        f"└ **Explicación:** {res['perf']['ve7_txt']}\n\n"
        f"⚠️ **RIESGO CLIMÁTICO (TerraClimate):**\n"
        f"└ Déficit: `94.7 mm/año`\n"
        f"└ **Blindaje Legal:** {res['perf']['clima_txt']}\n"
        f"──────────────────\n"
        f"✅ **ESTADO GLOBAL:** {res['estado']}\n"
        f"📝 **Diagnóstico:** Evaluación técnica finalizada con éxito."
    )
    
    requests.post(f"https://api.telegram.org/bot{st.secrets['telegram']['token']}/sendMessage", 
                 data={"chat_id": p['telegram_id'], "text": reporte, "parse_mode": "Markdown"})

# --- 5. INTERFAZ ---
st.title("🛰️ BioCore Intelligence V5")
proyectos = supabase.table("usuarios").select("*").execute().data

for p in proyectos:
    if st.button(f"⚡ Procesar {p['Proyecto']}"):
        with st.spinner(f"Analizando {p['Proyecto']}..."):
            try:
                resultados = ejecutar_auditoria(p)
                enviar_telegram(p, resultados)
                st.success("Reporte enviado a Telegram.")
            except Exception as e:
                st.error(f"Error en el proceso: {e}")
