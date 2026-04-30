import streamlit as st
import pandas as pd
import json
import ee
import requests
from datetime import datetime, timedelta
from googleapiclient.discovery import build
from google.oauth2 import service_account
from streamlit_folium import folium_static
import folium

# --- 1. CONFIGURACIÓN E IDENTIDAD ---
st.set_page_config(page_title="BioCore Omnimodal V5", layout="wide", page_icon="🛰️")
T_TOKEN = st.secrets["telegram"]["token"]
T_ID = st.secrets["telegram"]["chat_id"]
UMBRAL_CRITICO = 0.4
DIRECTORA = "Loreto Campos Carrasco"

# --- 2. DICCIONARIO MAESTRO (Los 5 Tipos de Proyecto) ---
CLIENTES = {
    "Laguna Señoraza (Laja)": {
        "coords": [[-72.715,-37.275],[-72.715,-37.285],[-72.690,-37.285],[-72.690,-37.270]], 
        "tipo": "HUMEDAL", "sheet_id": "1x6yAXNNlea3e43rijJu0aqcRpe4oP3BEnzgSgLuG1vU", "pestaña": "Humedales"
    },
    "Pascua Lama (Cordillera)": {
        "coords": [[-70.033,-29.316],[-70.016,-29.316],[-70.016,-29.333],[-70.033,-29.333]], 
        "tipo": "GLACIAR", "sheet_id": "1UTrDs939rPlVIR1OTIwbJ6rM3FazgjX43YnJdue-Dmc", "pestaña": "Mineria"
    },
    "Predio Forestal Biobío": {
        "coords": [[-72.50, -37.50], [-72.48, -37.50], [-72.48, -37.52], [-72.50, -37.52]],
        "tipo": "FORESTAL", "sheet_id": "TU_ID_3", "pestaña": "Forestal"
    }
}

# --- 3. FUNCIONES CORE ---
def enviar_telegram(m):
    try:
        requests.post(f"https://api.telegram.org/bot{T_TOKEN}/sendMessage", 
                      data={"chat_id": T_ID, "text": m, "parse_mode": "Markdown"})
    except: pass

@st.cache_resource
def init_biocore():
    try:
        creds_json = json.loads(st.secrets["gee"]["json"])
        creds = service_account.Credentials.from_service_account_info(creds_json, 
                scopes=['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/earthengine'])
        ee.Initialize(creds)
        return creds
    except Exception as e:
        st.error(f"Error de conexión: {e}")
        return None

# --- 4. INTERFAZ ---
st.title("🛰️ BioCore Intelligence Console V5")
st.write(f"**Directora Técnica:** {DIRECTORA}")

with st.sidebar:
    st.header("Módulos de Vigilancia")
    btn_ejecutar = st.button("🚀 Ejecutar BioCore Total", use_container_width=True)
    st.divider()
    st.info(f"Umbral de Alerta: {UMBRAL_CRITICO}")

# --- 5. LÓGICA DEL MOTOR OMNIMODAL ---
if btn_ejecutar:
    creds = init_biocore()
    if creds:
        sheets_service = build('sheets', 'v4', credentials=creds)
        bar = st.progress(0)
        
        for idx, (nombre, info) in enumerate(CLIENTES.items()):
            try:
                p = ee.Geometry.Polygon(info['coords'])
                
                # A. Módulo 5: Incendios (FIRMS - 72h)
                rango_fuego = datetime.now() - timedelta(days=3)
                fuegos = ee.ImageCollection("FIRMS").filterBounds(p).filterDate(rango_fuego.strftime('%Y-%m-%d'), datetime.now().strftime('%Y-%m-%d')).size().getInfo()
                
                # B. Sensores Satelitales
                s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED').filterBounds(p).sort('system:time_start', False).first()
                s1 = ee.ImageCollection('COPERNICUS/S1_GRD').filterBounds(p).filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV')).sort('system:time_start', False).first()
                f_rep = datetime.fromtimestamp(s2.get('system:time_start').getInfo()/1000).strftime('%d/%m/%Y')

                # C. Índices y GEDI (Altura)
                indices = s2.expression('((B8-B4)/(B8+B4+0.5))*1.5', {'B8':s2.select('B8'),'B4':s2.select('B4')}).rename('savi')\
                    .addBands(s2.normalizedDifference(['B3','B8']).rename('ndwi'))\
                    .addBands(s2.normalizedDifference(['B3','B11']).rename('ndsi'))\
                    .addBands(s2.select('B11').divide(s2.select('B12')).rename('clay'))\
                    .addBands(s2.select('B11').divide(10000).rename('swir'))\
                    .reduceRegion(ee.Reducer.mean(), p, 30).getInfo()
                
                try:
                    gedi = ee.ImageCollection("LARSE/GEDI/L2A_002").filterBounds(p).sort('system:time_start', False).first()
                    alt = gedi.reduceRegion(ee.Reducer.mean(), p, 30).getInfo().get('rh98', 1.2)
                except: alt = 0.0

                # D. Lógica de Diagnóstico Dinámico
                estado = "🟢 BAJO CONTROL"
                diagnostico = "Sin desviaciones detectadas."
                
                if fuegos > 0:
                    estado = "🚨 EMERGENCIA: FUEGO"
                    diagnostico = f"Detección de {fuegos} focos térmicos activos."
                elif info['tipo'] == "HUMEDAL" and indices['ndwi'] < UMBRAL_CRITICO:
                    estado = "🔴 ALERTA TÉCNICA"; diagnostico = "Estrés hídrico (NDWI crítico)."
                elif info['tipo'] == "GLACIAR" and indices['ndsi'] < UMBRAL_CRITICO:
                    estado = "🔴 ALERTA TÉCNICA"; diagnostico = "Pérdida de cobertura de nieve/hielo."
                elif info['tipo'] == "FORESTAL" and indices['savi'] < UMBRAL_CRITICO:
                    estado = "🔴 ALERTA TÉCNICA"; diagnostico = "Degradación de dosel vegetativo."
                elif info['tipo'] == "MINERIA" and indices['swir'] > UMBRAL_CRITICO:
                    estado = "🔴 ALERTA TÉCNICA"; diagnostico = "Posible movimiento de estériles."

                # E. Sincronización y Reporte
                sar_val = s1.reduceRegion(ee.Reducer.mean(), p, 30).getInfo().get('VV', 0)
                
                # Guardar en Google Sheets
                fila = [[f_rep, indices['savi'], indices['ndsi'], indices['ndwi'], sar_val, estado]]
                sheets_service.spreadsheets().values().append(spreadsheetId=info['sheet_id'], range=f"{info['pestaña']}!A2", valueInputOption="USER_ENTERED", body={'values': fila}).execute()

                # Reporte en Telegram
                reporte = (
                    f"🛰 **BIOCORE OMNIMODAL V5**\n"
                    f"**{nombre}** ({info['tipo']})\n"
                    f"📅 **Análisis:** {f_rep}\n"
                    f"──────────────────\n"
                    f"🛡️ **ESTADO:** {estado}\n"
                    f"🔥 **Fuego:** {'🚨 DETECTADO' if fuegos > 0 else '✅ Negativo'}\n"
                    f"🌿 **SAVI:** `{indices['savi']:.2f}` | 📏 **Altura:** `{alt:.1f}m`\n"
                    f"📡 **Radar VV:** `{sar_val:.2f} dB`\n"
                    f"──────────────────\n"
                    f"📝 **Diagnóstico:** {diagnostico}"
                )
                enviar_telegram(reporte)
                st.success(f"Sincronizado: {nombre}")

            except Exception as e_proy:
                st.warning(f"Error en {nombre}: {e_proy}")
            
            bar.progress((idx + 1) / len(CLIENTES))
        
        st.balloons()
