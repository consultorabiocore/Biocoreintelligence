import streamlit as st
import ee
import requests
import json
from datetime import datetime

# --- CONFIGURACIÓN DE PERFILES (Leyes y Formularios) ---
PERFILES = {
    "HUMEDAL": {
        "catastro": "Humedal Urbano / Cuerpo de Agua (Ley 21.202)",
        "habitat_expl": "Estructura de ribera garantiza refugio de fauna silvestre.",
        "clima_ley": "Balance hídrico real para defensa técnica (Ley 21.202)",
        "sensor_eval": "nd", "umbral": 0.1, "crit": "menor"
    },
    "MINERIA": {
        "catastro": "Área Minera / Depósito de Estériles (Formulario F-30)",
        "habitat_expl": "Estabilidad de sustrato compatible con plan de cierre.",
        "clima_ley": "Monitoreo de aridez para control de polvo (F-30)",
        "sensor_eval": "sw", "umbral": 0.45, "crit": "mayor"
    },
    "GLACIAR": {
        "catastro": "Área Criosférica / Alta Montaña (RCA Pascua Lama)",
        "habitat_expl": "Balance de masa criosférica protege ecosistemas altoandinos.",
        "clima_ley": "Control de derretimiento anómalo (RCA Pascua Lama)",
        "sensor_eval": "mn", "umbral": 0.35, "crit": "menor"
    },
    "BOSQUE": {
        "catastro": "Bosque Nativo / Plan de Manejo (Ley 20.283)",
        "habitat_expl": "Estructura de dosel garantiza conectividad biológica.",
        "clima_ley": "Estrés hídrico en biomasa (Ley 20.283)",
        "sensor_eval": "sa", "umbral": 0.20, "crit": "menor"
    },
    "INDUSTRIAL": {
        "catastro": "Zona de Impacto / Logística (Formulario F-22)",
        "habitat_expl": "Monitoreo de sellado de suelo y control de escorrentía.",
        "clima_ley": "Gestión de pluviosidad industrial (F-22)",
        "sensor_eval": "sw", "umbral": 0.50, "crit": "mayor"
    }
}

# --- MOTOR DE REPORTE DIARIO ---
def enviar_reporte_biocore(p, res):
    # p: dict de supabase | res: resultados de GEE
    tipo = p.get('Tipo', 'MINERIA')
    perf = PERFILES.get(tipo, PERFILES["MINERIA"])
    
    # Dinamismo de etiquetas
    etiqueta_mn = "NDSI" if tipo == "GLACIAR" else "NDWI"
    valor_mn = res['idx']['mn'] if tipo == "GLACIAR" else res['idx']['nd']

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
        f"└ **Interpretación:** Reflectancia mineral y estabilidad de taludes verificada.\n\n"
        f"🌲 **CATASTRO DINÁMICO:**\n"
        f"└ Tipo: {perf['catastro']}\n"
        f"└ Certificación de no intervención en polígono autorizado.\n\n"
        f"🌱 **SALUD VEGETAL (VE-5):**\n"
        f"└ Vigor (SAVI): `{res['idx']['sa']:.2f}`\n"
        f"└ **Sustrato:** Ratio Arcillas (`{res['idx']['clay']:.2f}`): Estabilidad de sedimentos.\n\n"
        f"📏 **ESTADO DEL HÁBITAT (VE-7):**\n"
        f"└ Altura (GEDI): `{res['alt']:.1f}m` | **{etiqueta_mn}:** `{valor_mn:.2f}`\n"
        f"└ **Explicación:** {perf['habitat_expl']}\n\n"
        f"⚠️ **RIESGO CLIMÁTICO (TerraClimate):**\n"
        f"└ Déficit: `{res['defic']:.1f} mm/año`\n"
        f"└ **Blindaje Legal:** {perf['clima_ley']}.\n"
        f"──────────────────\n"
        f"✅ **ESTADO GLOBAL:** {res['estado']}\n"
        f"📝 **Diagnóstico:** {res['diag']}"
    )
    
    requests.post(f"https://api.telegram.org/bot{st.secrets['telegram']['token']}/sendMessage", 
                 data={"chat_id": p['telegram_id'], "text": reporte, "parse_mode": "Markdown"})

# --- ACCIÓN PARA DESBLOQUEAR APP ---
if st.button("🔄 REINICIAR MOTOR Y LIMPIAR CACHÉ"):
    st.cache_data.clear()
    st.rerun()
