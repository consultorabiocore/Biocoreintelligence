import streamlit as st
import json
import ee
import requests
import pandas as pd
from datetime import datetime, timedelta
from supabase import create_client, Client
from streamlit_folium import folium_static
import folium

# --- 1. CONFIGURACIÓN E INICIO ---
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
    except Exception as e:
        st.error(f"Error de conexión: {e}")
        st.stop()

    # --- 3. FUNCIONES DE ANÁLISIS ---
    def enviar_reporte_telegram(mensaje):
        token = st.secrets["telegram"]["token"]
        chat_id = st.secrets["telegram"]["chat_id"]
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        requests.post(url, data={"chat_id": chat_id, "text": mensaje, "parse_mode": "Markdown"})

    @st.cache_data(ttl=600)
    def obtener_proyectos():
        res = supabase.table("usuarios").select("*").execute()
        return res.data

    # --- 4. INTERFAZ ---
    tab1, tab2, tab3 = st.tabs(["🌍 Monitoreo por Tipo", "📊 Historial", "🌡️ Clima"])
    data_proyectos = obtener_proyectos()

    with st.sidebar:
        st.header("🛰️ Panel de Control")
        tipo_filtro = st.multiselect("Filtrar por Tipo", ["Minería", "Humedal"], default=["Minería", "Humedal"])
        btn_reporte = st.button("🚀 ENVIAR REPORTE AL CELULAR", use_container_width=True)

    # --- 5. PROCESAMIENTO Y REPORTES ---
    resumen_reporte = "📋 *REPORTE BIOCORE V5*\n" + datetime.now().strftime("%d/%m/%Y %H:%M") + "\n\n"

    for proy in data_proyectos:
        # Lógica de tipos de proyecto
        tipo = "Minería" if "Pascua" in proy['Proyecto'] else "Humedal"
        if tipo not in tipo_filtro: continue

        nombre = proy['Proyecto']
        coords = json.loads(proy['Coordenadas'])
        poly = ee.Geometry.Polygon(coords)

        # Análisis Sentinel-2
        img = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED').filterBounds(poly).sort('system:time_start', False).first()
        stats = img.expression('((B8-B4)/(B8+B4+0.5))*1.5', {'B8':img.select('B8'),'B4':img.select('B4')}).rename('savi')\
                   .reduceRegion(ee.Reducer.mean(), poly, 30).getInfo()
        
        val_savi = stats['savi']
        resumen_reporte += f"📍 *{nombre}* ({tipo})\n• SAVI: {val_savi:.3f}\n"

        # Mostrar en Pestaña 1
        with tab1:
            color = "orange" if tipo == "Minería" else "green"
            st.markdown(f"### {nombre} <span style='color:{color}'>({tipo})</span>", unsafe_allow_html=True)
            st.metric("Índice SAVI", f"{val_savi:.3f}")

    # Ejecución del reporte al celular
    if btn_reporte:
        enviar_reporte_telegram(resumen_reporte)
        st.toast("Reporte enviado a Telegram ✅")

    # Mapa General
    with tab1:
        st.divider()
        m = folium.Map(location=[-29.3, -70.0], zoom_start=9)
        for p in data_proyectos:
            if p.get('Coordenadas'):
                color_map = "red" if "Pascua" in p['Proyecto'] else "blue"
                folium.Polygon(locations=[[c[1], c[0]] for c in json.loads(p['Coordenadas'])], 
                               popup=p['Proyecto'], color=color_map).add_to(m)
        folium_static(m)
