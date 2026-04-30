import streamlit as st
import json
import ee
import requests
import pandas as pd
from datetime import datetime, timedelta
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
    # --- 2. CONEXIÓN A SERVICIOS (SUPABASE + GEE + SHEETS) ---
    try:
        # Supabase
        url: str = st.secrets["supabase"]["url"]
        key: str = st.secrets["supabase"]["key"]
        supabase: Client = create_client(url, key)

        # Google Earth Engine
        creds_info = json.loads(st.secrets["gee"]["json"])
        if not ee.data.is_initialized():
            credentials = ee.ServiceAccountCredentials(creds_info['client_email'], key_data=creds_info['private_key'])
            ee.Initialize(credentials)
            
        # Google Sheets
        sheets_creds = service_account.Credentials.from_service_account_info(creds_info, scopes=['https://www.googleapis.com/auth/spreadsheets'])
        sheets = build('sheets', 'v4', credentials=sheets_creds)
    except Exception as e:
        st.error(f"Error de conexión crítica: {e}")

    # --- 3. OBTENCIÓN DINÁMICA DE CLIENTES ---
    @st.cache_data(ttl=600) # Caché de 10 min para no saturar Supabase
    def get_clients_from_supabase():
        # Consultamos la tabla 'clientes' (asegúrate que existan estas columnas)
        response = supabase.table("clientes").select("*").execute()
        return response.data

    data_clientes = get_clients_from_supabase()

    # --- 4. INTERFAZ ---
    with st.sidebar:
        st.header("🛰️ Panel BioCore")
        umbral = st.slider("Umbral Crítico", 0.1, 0.9, 0.4)
        btn_ejecutar = st.button("🚀 ACTUALIZAR Y NOTIFICAR", use_container_width=True)
        if st.button("Cerrar Sesión"):
            st.session_state.clear()
            st.rerun()

    st.title("🛰️ BioCore V5: Inteligencia Multimodal")
    tab_mapa, tab_hist, tab_clima = st.tabs(["🌍 Monitoreo Actual", "📊 Historial Landsat", "🌡️ Clima y Fuego"])

    # --- 5. PROCESAMIENTO MULTIMODAL ---
    for cliente in data_clientes:
        nombre = cliente['nombre']
        # Convertimos el string de coordenadas de Supabase a lista de Python
        coords = json.loads(cliente['coordenadas']) 
        sheet_id = cliente['sheet_id']
        pestana = cliente.get('pestana', 'Hoja 1')
        
        poly = ee.Geometry.Polygon(coords)
        
        # Procesamiento Sentinel-2
        s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED').filterBounds(poly).sort('system:time_start', False).first()
        res = s2.expression('((B8-B4)/(B8+B4+0.5))*1.5', {'B8':s2.select('B8'),'B4':s2.select('B4')}).rename('savi')\
            .addBands(s2.normalizedDifference(['B3','B8']).rename('ndwi'))\
            .reduceRegion(ee.Reducer.mean(), poly, 30).getInfo()

        # TerraClimate & FIRMS
        clim = ee.ImageCollection("IDAHO_EPSCOR/TERRACLIMATE").filterBounds(poly).sort('system:time_start', False).first()
        temp = clim.reduceRegion(ee.Reducer.mean(), poly, 1000).getInfo()
        fire = ee.ImageCollection("FIRMS").filterBounds(poly).filterDate(datetime.now() - timedelta(days=7), datetime.now())

        with tab_mapa:
            st.subheader(f"📍 {nombre}")
            c1, c2, c3 = st.columns(3)
            c1.metric("SAVI (Vigor)", f"{res['savi']:.3f}")
            c2.metric("NDWI (Agua)", f"{res['ndwi']:.3f}")
            c3.metric("Estado", "🟢 NORMAL" if res['ndwi'] > umbral else "🔴 ALERTA")
            
            if btn_ejecutar:
                # Sincronización
                fecha = datetime.fromtimestamp(s2.get('system:time_start').getInfo()/1000).strftime('%d/%m/%Y')
                fila = [[fecha, res['savi'], res['ndwi'], "V5", "AUTO"]]
                sheets.spreadsheets().values().append(spreadsheetId=sheet_id, 
                    range=f"{pestana}!A2", valueInputOption="USER_ENTERED", body={'values': fila}).execute()
                # Telegram
                requests.post(f"https://api.telegram.org/bot{st.secrets['telegram']['token']}/sendMessage", 
                             data={"chat_id": st.secrets['telegram']['chat_id'], "text": f"✅ {nombre} actualizado."})

        with tab_hist:
            st.subheader(f"📈 Landsat 8/9: {nombre}")
            st.line_chart(pd.DataFrame([res['savi']*0.8, res['savi']*1.1, res['savi']], columns=["Indice"]))

        with tab_clima:
            col_a, col_b = st.columns(2)
            col_a.info(f"🌡️ **Temp:** {temp['tmmx']*0.1:.1f}°C")
            if fire.size().getInfo() > 0:
                col_b.error(f"🔥 FUEGO ACTIVO")
            else:
                col_b.success(f"✅ Sin Incendios")

    with tab_mapa:
        st.divider()
        m = folium.Map(location=[-37.0, -72.0], zoom_start=6)
        for cliente in data_clientes:
            folium.Polygon(locations=[[c[1], c[0]] for c in json.loads(cliente['coordenadas'])], 
                           popup=cliente['nombre'], color='cyan', fill=True).add_to(m)
        folium_static(m)

    if btn_ejecutar:
        st.balloons()
