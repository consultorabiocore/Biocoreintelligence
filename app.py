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
st.set_page_config(page_title="BioCore Intelligence V5", layout="wide", page_icon="🛰️")
T_TOKEN = st.secrets["telegram"]["token"]
T_ID = st.secrets["telegram"]["chat_id"]
UMBRAL_CRITICO = 0.4
DIRECTORA = "Loreto Campos Carrasco"

# --- 2. DICCIONARIO MAESTRO (5 TIPOS DE PROYECTO) ---
# Aquí puedes agregar "FORESTAL", "INFRAESTRUCTURA" o "RIESGO" siguiendo la misma estructura.
CLIENTES = {
    "Laguna Señoraza (Laja)": {
        "coords": [[-72.715,-37.275],[-72.715,-37.285],[-72.690,-37.285],[-72.690,-37.270]], 
        "tipo": "HUMEDAL", "sheet_id": "1x6yAXNNlea3e43rijJu0aqcRpe4oP3BEnzgSgLuG1vU", "pestaña": "Humedales"
    },
    "Pascua Lama (Cordillera)": {
        "coords": [[-70.033,-29.316],[-70.016,-29.316],[-70.016,-29.333],[-70.033,-29.333]], 
        "tipo": "MINERIA", "glaciar": True, "sheet_id": "1UTrDs939rPlVIR1OTIwbJ6rM3FazgjX43YnJdue-Dmc", "pestaña": "Mineria"
    }
}

# --- 3. FUNCIONES DE APOYO ---
def enviar_telegram(m):
    try:
        requests.post(f"https://api.telegram.org/bot{T_TOKEN}/sendMessage", 
                      data={"chat_id": T_ID, "text": m, "parse_mode": "Markdown"})
    except: pass

@st.cache_resource
def init_gee():
    try:
        creds_json = json.loads(st.secrets["gee"]["json"])
        creds = service_account.Credentials.from_service_account_info(creds_json, 
                scopes=['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/earthengine'])
        ee.Initialize(creds)
        return creds
    except Exception as e:
        st.error(f"Error de conexión GEE: {e}")
        return None

# --- 4. INTERFAZ PRINCIPAL ---
st.title("🛰️ BioCore Intelligence Console V5")
st.markdown(f"**Directora Técnica:** {DIRECTORA} | **Estado del Sistema:** Operativo")

with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/satellite.png", width=80)
    st.header("Panel de Mando")
    ejecutar = st.button("🚀 INICIAR MONITOREO GLOBAL", use_container_width=True)
    st.divider()
    st.write("🔧 **Configuración:**")
    st.write(f"- Umbral Crítico: `{UMBRAL_CRITICO}`")
    st.write("- Sensores: Sentinel 1/2, FIRMS, GEDI")

# --- 5. LÓGICA DE EJECUCIÓN ---
if ejecutar:
    creds = init_gee()
    if creds:
        sheets_service = build('sheets', 'v4', credentials=creds)
        progress_bar = st.progress(0)
        
        for idx, (nombre, info) in enumerate(CLIENTES.items()):
            try:
                p = ee.Geometry.Polygon(info['coords'])
                
                # A. Módulo Incendios (FIRMS - 48h)
                rango_fuego = datetime.now() - timedelta(days=2)
                fuegos = ee.ImageCollection("FIRMS").filterBounds(p).filterDate(rango_fuego.strftime('%Y-%m-%d'), datetime.now().strftime('%Y-%m-%d')).size().getInfo()
                
                # B. Captura Sentinel (Óptico + Radar)
                s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED').filterBounds(p).sort('system:time_start', False).first()
                s1 = ee.ImageCollection('COPERNICUS/S1_GRD').filterBounds(p).filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV')).sort('system:time_start', False).first()
                
                f_rep = datetime.fromtimestamp(s2.get('system:time_start').getInfo()/1000).strftime('%d/%m/%Y')
                sar_val = s1.reduceRegion(ee.Reducer.mean(), p, 30).getInfo().get('VV', 0)

                # C. Cálculo de Índices Multimodales
                res_idx = s2.expression('((B8-B4)/(B8+B4+0.5))*1.5', {'B8':s2.select('B8'),'B4':s2.select('B4')}).rename('sa')\
                    .addBands(s2.normalizedDifference(['B3','B8']).rename('nd'))\
                    .addBands(s2.normalizedDifference(['B3','B11']).rename('mn'))\
                    .addBands(s2.select('B11').divide(s2.select('B12')).rename('cl'))\
                    .reduceRegion(ee.Reducer.mean(), p, 30).getInfo()

                # D. Diagnóstico BioCore (Lógica de 5 Tipos)
                estado = "🟢 BAJO CONTROL"
                diagnostico = "Sin desviaciones técnicas."
                
                if fuegos > 0:
                    estado = "🚨 EMERGENCIA: FUEGO"
                    diagnostico = f"Detección de {fuegos} focos térmicos activos en el polígono."
                elif info['tipo'] == "HUMEDAL" and res_idx['nd'] < UMBRAL_CRITICO:
                    estado = "🔴 ALERTA TÉCNICA"
                    diagnostico = "Estrés hídrico detectado (NDWI bajo umbral)."
                elif info['tipo'] == "MINERIA" and info.get('glaciar') and res_idx['mn'] < UMBRAL_CRITICO:
                    estado = "🔴 ALERTA TÉCNICA"
                    diagnostico = "Pérdida de cobertura criosférica detectada."

                # E. Sincronización Google Sheets
                fila = [[f_rep, res_idx['sa'], res_idx['nd'], res_idx['mn'], sar_val, estado]]
                sheets.spreadsheets().values().append(
                    spreadsheetId=info['sheet_id'], 
                    range=f"{info['pestaña']}!A2", 
                    valueInputOption="USER_ENTERED", 
                    body={'values': fila}).execute()

                # F. Despliegue en Interfaz
                with st.expander(f"📊 {nombre}", expanded=True):
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Estado", estado)
                    c2.metric("SAVI (Vigor)", f"{res_idx['sa']:.2f}")
                    c3.metric("Radar (Estructura)", f"{sar_val:.2f} dB")
                    if fuegos > 0: st.error(diagnostico)
                    else: st.info(diagnostico)

                # G. Reporte Telegram
                msg = (f"🛰 **REPORTE BIOCORE V5**\n**{nombre}**\n📅 {f_rep}\n"
                       f"──────────────────\n🛡️ **ESTADO:** {estado}\n"
                       f"🌿 SAVI: `{res_idx['sa']:.2f}`\n❄️ NDSI/WI: `{res_idx['nd']:.2f}`\n"
                       f"📡 Radar: `{sar_val:.2f} dB`\n"
                       f"📝 {diagnostico}")
                enviar_telegram(msg)

            except Exception as e_proy:
                st.warning(f"Error procesando {nombre}: {e_proy}")

            progress_bar.progress((idx + 1) / len(CLIENTES))

        st.balloons()
        st.success("✅ Monitoreo finalizado. Datos sincronizados y reportes enviados.")

else:
    # Vista previa del mapa cuando no se está ejecutando
    st.subheader("Mapa de Cobertura Activa")
    m = folium.Map(location=[-33.0, -70.0], zoom_start=4)
    for n, i in CLIENTES.items():
        folium.Polygon(locations=[[p[1], p[0]] for p in i['coords']], popup=n, color='green').add_to(m)
    folium_static(m)
