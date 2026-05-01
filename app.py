import streamlit as st
import ee
import requests
import pandas as pd
import json
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime
from fpdf import FPDF
from supabase import create_client, Client
import base64

# --- CONFIGURACIÓN DE IDENTIDAD Y PERFILES ---
DIRECTORA = "Loreto Campos Carrasco"

PERFILES = {
    "HUMEDAL": {
        "catastro": "Humedal Urbano / Cuerpo de Agua (Ley 21.202)",
        "sensor_eval": "nd", # NDWI
        "umbral": 0.1,
        "crit": "menor",
        "msg_ok": "Parámetros bióticos y espejo de agua dentro de la norma legal.",
        "msg_err": "Estrés hídrico detectado. NDWI bajo umbral crítico.",
        "interpretacion": "Absorción hídrica óptima. Confirma saturación de sustrato."
    },
    "MINERIA": {
        "catastro": "Depósito de Estériles / Operación Minera",
        "sensor_eval": "sw", # SWIR
        "umbral": 0.45,
        "crit": "mayor",
        "msg_ok": "Sin indicios de intervención antrópica reciente.",
        "msg_err": "Detección de posible movimiento de material o excavación.",
        "interpretacion": "Reflectancia mineral estable. Descarta acopio de estériles."
    },
    "GLACIAR": {
        "catastro": "Área Criosférica / Alta Montaña (RCA Pascua Lama)",
        "sensor_eval": "mn", # NDSI
        "umbral": 0.35,
        "crit": "menor",
        "msg_ok": "Criósfera estable. Sin indicios de intervención antrópica.",
        "msg_err": "Pérdida crítica de cobertura criosférica (NDSI bajo 0.35).",
        "interpretacion": "Preservación de masa de hielo y control de albedo."
    },
    "BOSQUE": {
        "catastro": "Bosque Nativo / Plan de Manejo (Ley 20.283)",
        "sensor_eval": "sa", # SAVI
        "umbral": 0.20,
        "crit": "menor",
        "msg_ok": "Vigor foliar estable según Plan de Manejo.",
        "msg_err": "Degradación de biomasa detectada. Posible corta no autorizada.",
        "interpretacion": "Densidad foliar y vigor fotosintético dinámico."
    },
    "INDUSTRIAL": {
        "catastro": "Zona de Impacto / Logística",
        "sensor_eval": "sw", # SWIR para suelos desnudos
        "umbral": 0.50,
        "crit": "mayor",
        "msg_ok": "Estabilidad estructural detectada.",
        "msg_err": "Alteración de superficie o acumulación de material.",
        "interpretacion": "Firma espectral de superficies endurecidas o áridos."
    }
}

def clean(text):
    return str(text).encode('latin-1', 'replace').decode('latin-1')

# --- CONEXIÓN CORE ---
if "password_correct" not in st.session_state:
    st.title("🛰️ BioCore V5 - Consola Directiva")
    u = st.text_input("Usuario").strip().lower()
    p = st.text_input("Contraseña", type="password").strip()
    if st.button("Entrar"):
        if u == st.secrets["auth"]["user"] and p == str(st.secrets["auth"]["password"]):
            st.session_state["password_correct"] = True
            st.rerun()
    st.stop()

supabase: Client = create_client(st.secrets["connections"]["supabase"]["url"], st.secrets["connections"]["supabase"]["key"])
creds_info = json.loads(st.secrets["gee"]["json"])
if not ee.data.is_initialized():
    ee.Initialize(ee.ServiceAccountCredentials(creds_info['client_email'], key_data=creds_info['private_key']))

# --- MOTOR DE AUDITORÍA DINÁMICO ---
def realizar_auditoria(p_info):
    geom = ee.Geometry.Polygon(json.loads(p_info['Coordenadas']))
    tipo = p_info.get('Tipo', 'MINERIA')
    perfil = PERFILES.get(tipo, PERFILES["MINERIA"])

    # Captura Satelital
    s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED').filterBounds(geom).sort('system:time_start', False).first()
    f_rep = datetime.fromtimestamp(s2.get('system:time_start').getInfo()/1000).strftime('%d/%m/%Y')
    
    s1 = ee.ImageCollection('COPERNICUS/S1_GRD').filterBounds(geom).filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV')).sort('system:time_start', False).first()
    sar_val = s1.reduceRegion(ee.Reducer.mean(), geom, 30).getInfo().get('VV', 0)

    # Índices (SAVI, NDWI, NDSI, SWIR, Clay)
    idx = s2.expression('((B8-B4)/(B8+B4+0.5))*1.5', {'B8':s2.select('B8'),'B4':s2.select('B4')}).rename('sa')\
        .addBands(s2.normalizedDifference(['B3','B8']).rename('nd'))\
        .addBands(s2.normalizedDifference(['B3','B11']).rename('mn'))\
        .addBands(s2.select('B11').divide(10000).rename('sw'))\
        .addBands(s2.select('B11').divide(s2.select('B12')).rename('clay'))\
        .reduceRegion(ee.Reducer.mean(), geom, 30).getInfo()

    # TerraClimate
    clim = ee.ImageCollection("IDAHO_EPSCOR/TERRACLIMATE").filterBounds(geom).sort('system:time_start', False).first()
    defic = abs(float(clim.reduceRegion(ee.Reducer.mean(), geom, 4638).getInfo().get('pr', 0)) - 100)

    # --- LÓGICA DE EVALUACIÓN NO HARDCODEADA ---
    val_check = idx[perfil['sensor_eval']]
    umbral = perfil['umbral']
    
    # Evaluación binaria basada en el umbral del perfil
    if perfil['crit'] == "menor":
        falla = val_check < umbral
    else:
        falla = val_check > umbral

    estado_global = "🔴 ALERTA TÉCNICA" if falla else "🟢 BAJO CONTROL"
    diagnostico = perfil['msg_err'] if falla else perfil['msg_ok']

    return {
        "fecha": f_rep, "estado": estado_global, "diagnostico": diagnostico,
        "perfil": perfil, "idx": idx, "sar": sar_val, "defic": defic
    }

# --- INTERFAZ DE USUARIO ---
tab1, tab2, tab3 = st.tabs(["🚀 VIGILANCIA", "📊 HISTORIAL", "📄 CONFIGURACIÓN"])

proyectos = supabase.table("usuarios").select("*").execute().data

with tab1:
    st.subheader("Auditoría de Cumplimiento Ambiental")
    for p in proyectos:
        with st.expander(f"📋 {p['Proyecto']} ({p.get('Tipo')})"):
            if st.button(f"Ejecutar Motor BioCore", key=f"btn_{p['Proyecto']}"):
                with st.spinner("Analizando firmas espectrales..."):
                    res = realizar_auditoria(p)
                    
                    reporte = (
                        f"🛰 **REPORTE DE VIGILANCIA AMBIENTAL - BIOCORE**\n"
                        f"**{p['Proyecto']}**\n"
                        f"**Directora Técnica:** {DIRECTORA}\n"
                        f"📅 **Análisis:** {res['fecha']}\n"
                        f"🛰 **Sensores:** Sentinel-1 | Sentinel-2 | TerraClimate\n"
                        f"──────────────────\n"
                        f"🛡️ **INTEGRIDAD DEL TERRENO (SU-6):**\n"
                        f"└ Radar (VV): `{res['sar']:.2f} dB` | SWIR: `{res['idx']['sw']:.2f}`\n"
                        f"└ **Interpretación:** {res['perfil']['interpretacion']}\n\n"
                        f"🌲 **CATASTRO DINÁMICO:**\n"
                        f"└ Tipo: {res['perfil']['catastro']}\n\n"
                        f"🌱 **SALUD VEGETAL:**\n"
                        f"└ SAVI: `{res['idx']['sa']:.2f}` | Clay Ratio: `{res['idx']['clay']:.2f}`\n\n"
                        f"⚠️ **RIESGO CLIMÁTICO:**\n"
                        f"└ Déficit: `{res['defic']:.1f} mm/año`\n"
                        f"──────────────────\n"
                        f"✅ **ESTADO GLOBAL:** {res['estado']}\n"
                        f"📝 **Diagnóstico:** {res['diagnostico']}"
                    )
                    
                    st.markdown(reporte)
                    
                    # Envío a Telegram
                    requests.post(f"https://api.telegram.org/bot{st.secrets['telegram']['token']}/sendMessage", 
                                 data={"chat_id": p['telegram_id'], "text": reporte, "parse_mode": "Markdown"})
                    st.success("Auditoría enviada.")
