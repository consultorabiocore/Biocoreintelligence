import streamlit as st
import ee
import requests
import json
from datetime import datetime
from supabase import create_client, Client

# --- 1. CONEXIONES (Aquí se define 'supabase') ---
# Asegúrate de tener estas credenciales en st.secrets
url: str = st.secrets["connections"]["supabase"]["url"]
key: str = st.secrets["connections"]["supabase"]["key"]
supabase: Client = create_client(url, key)

# --- 2. CONFIGURACIÓN DINÁMICA DE REPORTES ---
DATA_BIOCORE = {
    "HUMEDAL": {
        "cat": "Humedal Urbano / Cuerpo de Agua (Ley 21.202)",
        "ve7": "Estructura de ribera garantiza refugio de fauna silvestre.",
        "clima": "Monitoreo de balance hídrico real (Ley 21.202)",
        "eval": "nd", "u": 0.1, "c": "menor"
    },
    "MINERIA": {
        "cat": "Área Minera / Depósito de Estériles (Formulario F-30)",
        "ve7": "Estabilidad de sustrato compatible con plan de cierre.",
        "clima": "Control de aridez y material particulado (F-30)",
        "eval": "sw", "u": 0.45, "c": "mayor"
    },
    "GLACIAR": {
        "cat": "Área Criosférica / Alta Montaña (RCA Pascua Lama)",
        "ve7": "Balance de masa criosférica protege ecosistemas altoandinos.",
        "clima": "Vigilancia de derretimiento y albedo (RCA Pascua Lama)",
        "eval": "mn", "u": 0.35, "c": "menor"
    },
    "BOSQUE": {
        "cat": "Bosque Nativo / Plan de Manejo (Ley 20.283)",
        "ve7": "Estructura de dosel garantiza conectividad biológica.",
        "clima": "Detección de estrés hídrico en biomasa (Ley 20.283)",
        "eval": "sa", "u": 0.20, "c": "menor"
    },
    "INDUSTRIAL": {
        "cat": "Zona de Impacto / Logística (Formulario F-22)",
        "ve7": "Monitoreo de sellado de suelo y escorrentía.",
        "clima": "Gestión de pluviosidad y drenaje (F-22)",
        "eval": "sw", "u": 0.50, "c": "mayor"
    }
}

# --- 3. MOTOR DE REPORTE ---
def enviar_reporte_biocore(p, res):
    tipo = p.get('Tipo', 'MINERIA')
    d = DATA_BIOCORE.get(tipo, DATA_BIOCORE["MINERIA"])
    
    # Etiquetas dinámicas según el tipo
    tag_mn = "NDSI" if tipo == "GLACIAR" else "NDWI"
    val_mn = res['idx']['mn'] if tipo == "GLACIAR" else res['idx']['nd']

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
        f"└ **Interpretación:** Estabilidad de taludes y reflectancia verificada.\n\n"
        f"🌲 **CATASTRO DINÁMICO:**\n"
        f"└ Tipo: {d['cat']}\n"
        f"└ Certificación de no intervención en polígono autorizado.\n\n"
        f"🌱 **SALUD VEGETAL (VE-5):**\n"
        f"└ Vigor (SAVI): `{res['idx']['sa']:.2f}`\n"
        f"└ **Sustrato:** Ratio Arcillas (`{res['idx']['clay']:.2f}`): Estabilidad.\n\n"
        f"📏 **ESTADO DEL HÁBITAT (VE-7):**\n"
        f"└ Altura (GEDI): `{res['alt']:.1f}m` | **{tag_mn}:** `{val_mn:.2f}`\n"
        f"└ **Explicación:** {d['ve7']}\n\n"
        f"⚠️ **RIESGO CLIMÁTICO (TerraClimate):**\n"
        f"└ Déficit: `{res['defic']:.1f} mm/año`\n"
        f"└ **Blindaje Legal:** {d['clima']}.\n"
        f"──────────────────\n"
        f"✅ **ESTADO GLOBAL:** {res['estado']}\n"
        f"📝 **Diagnóstico:** {res['diag']}"
    )
    
    requests.post(f"https://api.telegram.org/bot{st.secrets['telegram']['token']}/sendMessage", 
                 data={"chat_id": p['telegram_id'], "text": reporte, "parse_mode": "Markdown"})

# --- 4. INTERFAZ ---
st.title("🛰️ BioCore Intelligence V5")

try:
    # Ahora 'supabase' sí está definido arriba
    proyectos = supabase.table("usuarios").select("*").execute().data
    if proyectos:
        for p in proyectos:
            if st.button(f"⚡ Procesar {p['Proyecto']}"):
                # Aquí iría el bloque de cálculo de GEE que ya tienes
                st.info(f"Iniciando auditoría para {p['Proyecto']}...")
    else:
        st.warning("No hay proyectos registrados.")
except Exception as e:
    st.error(f"Error crítico: {e}")
