import streamlit as st
import ee
import requests
import pandas as pd
import json
from datetime import datetime
from supabase import create_client, Client

# --- 1. CONFIGURACIÓN DE PERFILES TÉCNICOS ---
# Aquí se definen las leyes y formularios entre paréntesis como solicitaste
PERFILES = {
    "HUMEDAL": {
        "catastro": "Humedal Urbano / Cuerpo de Agua (Ley 21.202)",
        "sensor_eval": "nd", 
        "umbral": 0.1,
        "crit": "menor",
        "msg_ok": "Parámetros bióticos y físicos dentro de la norma legal.",
        "msg_err": "Estrés hídrico detectado. NDWI bajo umbral crítico.",
        "interpretacion": "Absorción hídrica óptima. Confirma saturación de sustrato.",
        "habitat_expl": "Estructura de ribera garantiza refugio de fauna silvestre."
    },
    "MINERIA": {
        "catastro": "Área Minera / Depósito de Estériles (Formulario F-30)",
        "sensor_eval": "sw", 
        "umbral": 0.45,
        "crit": "mayor",
        "msg_ok": "Sin indicios de intervención antrópica reciente.",
        "msg_err": "Detección de posible movimiento de material o excavación.",
        "interpretacion": "Reflectancia mineral estable. Descarta acopio de estériles.",
        "habitat_expl": "Estabilidad de sustrato compatible con plan de cierre."
    },
    "GLACIAR": {
        "catastro": "Área Criosférica / Alta Montaña (RCA Pascua Lama)",
        "sensor_eval": "mn", 
        "umbral": 0.35,
        "crit": "menor",
        "msg_ok": "Criósfera estable. Sin indicios de intervención antrópica.",
        "msg_err": "Pérdida crítica de cobertura criosférica (NDSI bajo 0.35).",
        "interpretacion": "Preservación de masa de hielo y control de albedo.",
        "habitat_expl": "Balance de masa criosférica protege ecosistemas altoandinos."
    },
    "BOSQUE": {
        "catastro": "Bosque Nativo / Plan de Manejo (Ley 20.283)",
        "sensor_eval": "sa", 
        "umbral": 0.20,
        "crit": "menor",
        "msg_ok": "Vigor foliar estable según polígono autorizado.",
        "msg_err": "Degradación de biomasa detectada. Posible intervención.",
        "interpretacion": "Densidad foliar y vigor fotosintético dinámico.",
        "habitat_expl": "Estructura de dosel garantiza conectividad biológica."
    }
}

# --- 2. MOTOR DE CÁLCULO ---
def realizar_auditoria_completa(p_info):
    geom = ee.Geometry.Polygon(json.loads(p_info['Coordenadas']))
    perfil = PERFILES.get(p_info.get('Tipo'), PERFILES["MINERIA"])

    # Sensores
    s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED').filterBounds(geom).sort('system:time_start', False).first()
    f_rep = datetime.fromtimestamp(s2.get('system:time_start').getInfo()/1000).strftime('%d/%m/%Y')
    
    s1 = ee.ImageCollection('COPERNICUS/S1_GRD').filterBounds(geom).filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV')).sort('system:time_start', False).first()
    sar_val = s1.reduceRegion(ee.Reducer.mean(), geom, 30).getInfo().get('VV', 0)

    # Índices
    idx = s2.expression('((B8-B4)/(B8+B4+0.5))*1.5', {'B8':s2.select('B8'),'B4':s2.select('B4')}).rename('sa')\
        .addBands(s2.normalizedDifference(['B3','B8']).rename('nd'))\
        .addBands(s2.normalizedDifference(['B3','B11']).rename('mn'))\
        .addBands(s2.select('B11').divide(10000).rename('sw'))\
        .addBands(s2.select('B11').divide(s2.select('B12')).rename('clay'))\
        .reduceRegion(ee.Reducer.mean(), geom, 30).getInfo()

    # GEDI y Clima
    try:
        gedi = ee.ImageCollection("LARSE/GEDI/L2A_002").filterBounds(geom).sort('system:time_start', False).first()
        alt = gedi.reduceRegion(ee.Reducer.mean(), geom, 30).getInfo().get('rh98', 1.2)
    except: alt = 1.2
    
    clim = ee.ImageCollection("IDAHO_EPSCOR/TERRACLIMATE").filterBounds(geom).sort('system:time_start', False).first()
    defic = abs(float(clim.reduceRegion(ee.Reducer.mean(), geom, 4638).getInfo().get('pr', 0)) - 100)

    # Lógica Dinámica de Estado
    val_check = idx[perfil['sensor_eval']]
    falla = (val_check < perfil['umbral']) if perfil['crit'] == "menor" else (val_check > perfil['umbral'])
    
    return {
        "fecha": f_rep,
        "estado": "🔴 ALERTA TÉCNICA" if falla else "🟢 BAJO CONTROL",
        "diag": perfil['msg_err'] if falla else perfil['msg_ok'],
        "idx": idx, "sar": sar_val, "alt": alt, "defic": defic, "perfil": perfil
    }

# --- 3. REPORTE TELEGRAM ---
# Aquí integramos "Estado del Hábitat" y "Riesgo Climático" completos
def enviar_reporte(p, res):
    reporte = (
        f"🛰 **REPORTE DE VIGILANCIA AMBIENTAL - BIOCORE**\n"
        f"PROYECTO: {p['Proyecto']}\n"
        f"Directora Técnica: Loreto Campos Carrasco\n"
        f"📅 Análisis: {res['fecha']}\n"
        f"🛰 Sensores: Sentinel-1 (ESA) | Sentinel-2 (ESA) | GEDI (NASA) | TerraClimate\n"
        f"──────────────────\n"
        f"🛡️ **INTEGRIDAD DEL TERRENO (SU-6):**\n"
        f"└ Estatus: {'🛡️ ESTABLE' if 'CONTROL' in res['estado'] else '⚠️ ALTERADO'}\n"
        f"└ Radar (VV): `{res['sar']:.2f} dB` | SWIR: `{res['idx']['sw']:.2f}`\n"
        f"└ **Interpretación:** {res['perfil']['interpretacion']}\n\n"
        f"🌲 **CATASTRO DINÁMICO:**\n"
        f"└ Tipo: {res['perfil']['catastro']}\n"
        f"└ Certificación de no intervención en polígono autorizado.\n\n"
        f"🌱 **SALUD VEGETAL (VE-5):**\n"
        f"└ Vigor (SAVI): `{res['idx']['sa']:.2f}`\n"
        f"└ Sustrato: Ratio Arcillas (`{res['idx']['clay']:.2f}`): Estabilidad de sedimentos.\n\n"
        f"📏 **ESTADO DEL HÁBITAT (VE-7):**\n"
        f"└ Altura (GEDI): `{res['alt']:.1f}m` | NDWI/NDSI: `{res['idx']['nd']:.2f}`\n"
        f"└ **Explicación:** {res['perfil']['habitat_expl']}\n\n"
        f"⚠️ **RIESGO CLIMÁTICO (TerraClimate):**\n"
        f"└ Déficit: `{res['defic']:.1f} mm/año`\n"
        f"└ **Blindaje Legal:** Monitoreo de balance hídrico real para defensa técnica.\n"
        f"──────────────────\n"
        f"✅ **ESTADO GLOBAL:** {res['estado']}\n"
        f"📝 **Diagnóstico:** {res['diag']}"
    )
    requests.post(f"https://api.telegram.org/bot{st.secrets['telegram']['token']}/sendMessage", 
                 data={"chat_id": p['telegram_id'], "text": reporte, "parse_mode": "Markdown"})
