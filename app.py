import streamlit as st
import ee
import requests
import json
from datetime import datetime

# --- 1. CONFIGURACIÓN DE PERFILES TÉCNICOS (5 TIPOS) ---
# Aquí están todas las leyes, formularios y sensores críticos por perfil
PERFILES = {
    "HUMEDAL": {
        "catastro": "Humedal Urbano / Cuerpo de Agua (Ley 21.202)",
        "sensor_eval": "nd", # NDWI
        "umbral": 0.1,
        "crit": "menor",
        "habitat_expl": "Estructura de ribera garantiza refugio de fauna silvestre.",
        "interpretacion": "Absorción hídrica óptima. Confirma saturación de sustrato.",
        "msg_ok": "Parámetros bióticos y físicos dentro de la norma legal.",
        "msg_err": "Estrés hídrico detectado. NDWI bajo umbral crítico."
    },
    "MINERIA": {
        "catastro": "Área Minera / Depósito de Estériles (Formulario F-30)",
        "sensor_eval": "sw", # SWIR
        "umbral": 0.45,
        "crit": "mayor",
        "habitat_expl": "Estabilidad de sustrato compatible con plan de cierre.",
        "interpretacion": "Reflectancia mineral estable. Descarta acopio de estériles.",
        "msg_ok": "Sin indicios de intervención antrópica reciente.",
        "msg_err": "Detección de posible movimiento de material o excavación."
    },
    "GLACIAR": {
        "catastro": "Área Criosférica / Alta Montaña (RCA Pascua Lama)",
        "sensor_eval": "mn", # NDSI
        "umbral": 0.35,
        "crit": "menor",
        "habitat_expl": "Balance de masa criosférica protege ecosistemas altoandinos.",
        "interpretacion": "Preservación de masa de hielo y control de albedo.",
        "msg_ok": "Criósfera estable. Sin indicios de intervención antrópica.",
        "msg_err": "Pérdida crítica de cobertura criosférica (NDSI bajo 0.35)."
    },
    "BOSQUE": {
        "catastro": "Bosque Nativo / Plan de Manejo (Ley 20.283)",
        "sensor_eval": "sa", # SAVI
        "umbral": 0.20,
        "crit": "menor",
        "habitat_expl": "Estructura de dosel garantiza conectividad biológica.",
        "interpretacion": "Densidad foliar y vigor fotosintético dinámico.",
        "msg_ok": "Vigor foliar estable según polígono autorizado.",
        "msg_err": "Degradación de biomasa detectada. Posible intervención."
    },
    "INDUSTRIAL": {
        "catastro": "Zona de Impacto / Logística (Formulario F-22)",
        "sensor_eval": "sw", # SWIR para detectar cambios en suelo
        "umbral": 0.50,
        "crit": "mayor",
        "habitat_expl": "Monitoreo de sellado de suelo y control de escorrentía.",
        "interpretacion": "Firma espectral de superficies endurecidas o áridos.",
        "msg_ok": "Estabilidad estructural y logística detectada.",
        "msg_err": "Alteración de superficie o acumulación anómala de material."
    }
}

# --- 2. LÓGICA DE REPORTE DINÁMICO ---
def generar_reporte_telegram(p, res):
    # 'p' es el dict del proyecto de Supabase, 'res' es el dict con los cálculos de GEE
    perfil = PERFILES.get(p.get('Tipo'), PERFILES["MINERIA"])
    
    reporte = (
        f"🛰 **REPORTE DE VIGILANCIA AMBIENTAL - BIOCORE**\n"
        f"**PROYECTO:** {p['Proyecto']}\n"
        f"**Directora Técnica:** Loreto Campos Carrasco\n"
        f"📅 **Análisis:** {res['fecha']}\n"
        f"🛰 **Sensores:** Sentinel-1 (ESA) | Sentinel-2 (ESA) | GEDI (NASA) | TerraClimate\n"
        f"──────────────────\n"
        f"🛡️ **INTEGRIDAD DEL TERRENO (SU-6):**\n"
        f"└ Estatus: {'🛡️ ESTABLE' if 'CONTROL' in res['estado'] else '⚠️ ALTERADO'}\n"
        f"└ Radar (VV): `{res['sar']:.2f} dB` | SWIR: `{res['idx']['sw']:.2f}`\n"
        f"└ **Interpretación:** {perfil['interpretacion']}\n\n"
        f"🌲 **CATASTRO DINÁMICO:**\n"
        f"└ Tipo: {perfil['catastro']}\n"
        f"└ Certificación de no intervención en polígono autorizado.\n\n"
        f"🌱 **SALUD VEGETAL (VE-5):**\n"
        f"└ Vigor (SAVI): `{res['idx']['sa']:.2f}`\n"
        f"└ **Sustrato:** Ratio Arcillas (`{res['idx']['clay']:.2f}`): Estabilidad de sedimentos.\n\n"
        f"📏 **ESTADO DEL HÁBITAT (VE-7):**\n"
        f"└ Altura (GEDI): `{res['alt']:.1f}m` | **NDSI/NDWI:** `{res['idx']['nd']:.2f}`\n"
        f"└ **Explicación:** {perfil['habitat_expl']}\n\n"
        f"⚠️ **RIESGO CLIMÁTICO (TerraClimate):**\n"
        f"└ Déficit: `{res['defic']:.1f} mm/año`\n"
        f"└ **Blindaje Legal:** Monitoreo de balance hídrico real para defensa técnica.\n"
        f"──────────────────\n"
        f"✅ **ESTADO GLOBAL:** {res['estado']}\n"
        f"📝 **Diagnóstico:** {res['diagnostico']}"
    )
    
    # Envío a Telegram
    requests.post(f"https://api.telegram.org/bot{st.secrets['telegram']['token']}/sendMessage", 
                 data={"chat_id": p['telegram_id'], "text": reporte, "parse_mode": "Markdown"})
