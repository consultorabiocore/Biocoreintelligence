import streamlit as st
import json
import ee
import requests
import pandas as pd
from datetime import datetime
from supabase import create_client, Client
from googleapiclient.discovery import build
from google.oauth2 import service_account
from streamlit_folium import folium_static
import folium

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="BioCore Intelligence V5", layout="wide", page_icon="🛰️")

def check_password():
    if "password_correct" not in st.session_state:
        st.title("🛰️ BioCore V5 - Acceso")
        u = st.text_input("Usuario").lower().strip()
        p = st.text_input("Contraseña", type="password").strip()
        if st.button("Entrar"):
            if u == st.secrets["auth"]["user"].lower().strip() and p == str(st.secrets["auth"]["password"]).strip():
                st.session_state["password_correct"] = True
                st.rerun()
            else:
                st.error("Credenciales incorrectas")
        return False
    return True

if check_password():
    # --- 2. CONEXIONES ---
    try:
        supabase: Client = create_client(st.secrets["connections"]["supabase"]["url"], st.secrets["connections"]["supabase"]["key"])
        creds_info = json.loads(st.secrets["gee"]["json"])
        if not ee.data.is_initialized():
            ee.Initialize(ee.ServiceAccountCredentials(creds_info['client_email'], key_data=creds_info['private_key']))
        sheets = build('sheets', 'v4', credentials=service_account.Credentials.from_service_account_info(creds_info, scopes=['https://www.googleapis.com/auth/spreadsheets']))
    except Exception as e:
        st.error(f"Error de conexión: {e}")
        st.stop()

    # --- 3. OBTENCIÓN DE DATOS ---
    @st.cache_data(ttl=600)
    def get_projects():
        # Usamos la tabla "usuarios" de tu captura de pantalla
        res = supabase.table("usuarios").select("*").execute()
        return res.data

    proyectos_db = get_projects()

    # --- 4. INTERFAZ ---
    tab1, tab2, tab3 = st.tabs(["🌍 Monitoreo Actual", "📊 Historial", "🌡️ Clima"])
    with st.sidebar:
        st.header("🛰️ Panel BioCore")
        btn_ejecutar = st.button("🚀 PROCESAR Y ENVIAR REPORTE", use_container_width=True)

    # --- 5. BUCLE DE PROCESAMIENTO ---
    for proy in proyectos_db:
        nombre = proy.get('Proyecto', 'Sin Nombre')
        tipo = proy.get('Tipo', 'HUMEDAL').upper()
        # Aseguramos que el JSON de coordenadas sea válido
        try:
            coords = json.loads(proy['Coordenadas'])
            poly = ee.Geometry.Polygon(coords)
        except Exception as e:
            st.error(f"Error en coordenadas de {nombre}: {e}")
            continue

        # Análisis Sentinel-2 e Índices
        try:
            s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED').filterBounds(poly).sort('system:time_start', False).first()
            f_rep = datetime.fromtimestamp(s2.get('system:time_start').getInfo()/1000).strftime('%d/%m/%Y')
            
            # Cálculo de índices según tu protocolo BioCore
            idx = s2.expression({
                'sa': '((B8-B4)/(B8+B4+0.5))*1.5', # SAVI
                'nd': '(B3-B8)/(B3+B8)',          # NDWI/NDSI
                'sw': 'B11 / 10000',              # SWIR
                'clay': 'B11 / B12'               # Clay Ratio
            }, {
                'B8': s2.select('B8'), 'B4': s2.select('B4'),
                'B3': s2.select('B3'), 'B11': s2.select('B11'), 'B12': s2.select('B12')
            }).reduceRegion(ee.Reducer.mean(), poly, 30).getInfo()
            
            sa, nd, sw, clay = idx['sa'], idx['nd'], idx['sw'], idx['clay']
        except Exception as e:
            st.warning(f"GEE no pudo procesar {nombre}. Verifica que el polígono esté bien cerrado.")
            continue

        # Diagnóstico BioCore
        estado = "🟢 BAJO CONTROL"
        if tipo == "HUMEDAL":
            diag = "Hidroestabilidad detectada."
            if nd < 0.1: estado, diag = "🔴 ALERTA", "Estrés hídrico detectado."
        else:
            diag = "Sustrato estable."
            if sw > 0.45: estado, diag = "🔴 ALERTA", "Posible remoción de material."

        # Visualización
        with tab1:
            st.subheader(f"📍 {nombre} ({tipo})")
            c1, c2, c3 = st.columns(3)
            c1.metric("SAVI (Vigor)", f"{sa:.2f}")
            c2.metric("Humedad/Nieve", f"{nd:.2f}")
            c3.metric("Estado", estado)
            st.info(f"**Diagnóstico:** {diag}")

        # Reporte Telegram
        if btn_ejecutar:
            reporte = (f"🛰 **BIOCORE V5: REPORTE TÉCNICO**\n"
                       f"**{nombre}** ({tipo})\n"
                       f"📅 Fecha: {f_rep}\n"
                       f"🌱 SAVI: `{sa:.2f}`\n"
                       f"💧 NDWI/NDSI: `{nd:.2f}`\n"
                       f"✅ Estado: {estado}\n"
                       f"📝 Diagnóstico: {diag}")
            requests.post(f"https://api.telegram.org/bot{st.secrets['telegram']['token']}/sendMessage", 
                         data={"chat_id": st.secrets['telegram']['chat_id'], "text": reporte, "parse_mode": "Markdown"})

    if btn_ejecutar:
        st.success("Reportes enviados al celular ✅")
        st.balloons()
