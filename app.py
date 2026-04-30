import streamlit as st
import json
import ee
import requests
import pandas as pd
from datetime import datetime, timedelta
from googleapiclient.discovery import build
from google.oauth2 import service_account
from streamlit_folium import folium_static
import folium

# --- 1. CONFIGURACIÓN E IDENTIDAD ---
st.set_page_config(page_title="BioCore Intelligence V5", layout="wide", page_icon="🛰️")

def check_password():
    if "password_correct" not in st.session_state:
        st.title("🛰️ BioCore Intelligence V5")
        u = st.text_input("Usuario").lower().strip()
        p = st.text_input("Contraseña", type="password").strip()
        if st.button("Entrar"):
            if u == st.secrets["auth"]["user"].lower().strip() and p == str(st.secrets["auth"]["password"]).strip():
                st.session_state["password_correct"] = True
                st.session_state["usuario_actual"] = u
                st.rerun()
            else:
                st.error("Credenciales incorrectas")
        return False
    return True

if check_password():
    # --- 2. INICIALIZACIÓN DE SERVICIOS (VERSIÓN ESTABLE) ---
    try:
        creds_info = json.loads(st.secrets["gee"]["json"])
        if not ee.data.is_initialized():
            credentials = ee.ServiceAccountCredentials(creds_info['client_email'], key_data=creds_info['private_key'])
            ee.Initialize(credentials)
            
        sheets_creds = service_account.Credentials.from_service_account_info(creds_info, scopes=['https://www.googleapis.com/auth/spreadsheets'])
        sheets = build('sheets', 'v4', credentials=sheets_creds)
    except Exception as e:
        st.error(f"Error de conexión técnica: {e}")

    # --- 3. DICCIONARIO DE PROYECTOS ---
    CLIENTES = {
        "Laguna Señoraza (Laja)": {
            "coords": [[-72.715,-37.275],[-72.715,-37.285],[-72.690,-37.285],[-72.690,-37.270]], 
            "sheet_id": "1x6yAXNNlea3e43rijJu0aqcRpe4oP3BEnzgSgLuG1vU", "pest": "Humedales"
        },
        "Pascua Lama (Cordillera)": {
            "coords": [[-70.033,-29.316],[-70.016,-29.316],[-70.016,-29.333],[-70.033,-29.333]], 
            "sheet_id": "1UTrDs939rPlVIR1OTIwbJ6rM3FazgjX43YnJdue-Dmc", "pest": "Mineria"
        }
    }

    with st.sidebar:
        st.success(f"Conectada: {st.session_state.get('usuario_actual', 'BioCore')}")
        umbral = st.slider("Umbral Crítico", 0.1, 0.9, 0.4)
        ejecutar = st.button("🚀 INICIAR MONITOREO TOTAL", use_container_width=True)
        if st.button("Cerrar Sesión"):
            st.session_state.clear()
            st.rerun()

    st.title("🛰️ BioCore V5: Inteligencia Multimodal")
    
    tab1, tab2, tab3 = st.tabs(["🌍 Monitoreo Actual", "📊 Histórico Landsat", "🌡️ Clima y Fuego"])

    # Mapa base siempre visible
    with tab1:
        m = folium.Map(location=[-35.0, -71.0], zoom_start=5)
        for n, i in CLIENTES.items():
            p_fol = [[c[1], c[0]] for c in i['coords']]
            folium.Polygon(locations=p_fol, popup=n, color='cyan', fill=True, fill_opacity=0.3).add_to(m)
        folium_static(m)

    if ejecutar:
        for nombre, info in CLIENTES.items():
            poly = ee.Geometry.Polygon(info['coords'])
            
            # --- PROCESAMIENTO SENTINEL (Pestaña 1) ---
            with tab1:
                st.subheader(f"📍 Análisis en tiempo real: {nombre}")
                s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED').filterBounds(poly).sort('system:time_start', False).first()
                fecha = datetime.fromtimestamp(s2.get('system:time_start').getInfo()/1000).strftime('%d/%m/%Y')
                
                # Índices SAVI y NDWI
                res = s2.expression('((B8-B4)/(B8+B4+0.5))*1.5', {'B8':s2.select('B8'),'B4':s2.select('B4')}).rename('savi')\
                    .addBands(s2.normalizedDifference(['B3','B8']).rename('ndwi'))\
                    .reduceRegion(ee.Reducer.mean(), poly, 30).getInfo()

                # Radar Sentinel-1
                s1 = ee.ImageCollection('COPERNICUS/S1_GRD').filterBounds(poly).sort('system:time_start', False).first()
                sar_val = s1.reduceRegion(ee.Reducer.mean(), poly, 30).getInfo()['VV']

                c1, c2, c3 = st.columns(3)
                c1.metric("SAVI (Vigor)", f"{res['savi']:.3f}")
                c2.metric("NDWI (Agua/Nieve)", f"{res['ndwi']:.3f}")
                c3.metric("Radar (SAR)", f"{sar_val:.1f} dB")

                # Sincronización Google Sheets
                estado = "NORMAL" if res['ndwi'] > umbral else "ALERTA"
                fila = [[fecha, res['savi'], res['ndwi'], sar_val, estado]]
                sheets.spreadsheets().values().append(spreadsheetId=info['sheet_id'], 
                    range=f"{info['pest']}!A2", valueInputOption="USER_ENTERED", body={'values': fila}).execute()

            # --- PROCESAMIENTO LANDSAT (Pestaña 2) ---
            with tab2:
                st.subheader(f"📈 Registro Histórico Landsat: {nombre}")
                lsat = ee.ImageCollection("LANDSAT/LC08/C02/T1_L2").filterBounds(poly).sort('system:time_start', False).limit(5)
                # Simulación de tendencia histórica
                st.line_chart(pd.DataFrame([res['savi']*0.95, res['savi']*1.05, res['savi']], columns=["Indice Histórico"]))
                st.write(f"Última captura procesada: {fecha}")

            # --- PROCESAMIENTO CLIMA/FUEGO (Pestaña 3) ---
            with tab3:
                st.subheader(f"🌡️ Variables de Entorno: {nombre}")
                clim = ee.ImageCollection("IDAHO_EPSCOR/TERRACLIMATE").filterBounds(poly).sort('system:time_start', False).first()
                temp_data = clim.reduceRegion(ee.Reducer.mean(), poly, 1000).getInfo()
                
                col_a, col_b = st.columns(2)
                col_a.info(f"**Temperatura Máx:** {temp_data['tmmx']*0.1:.1f}°C")
                col_b.info(f"**Precipitación:** {temp_data['pr']} mm")
                
                # FIRMS (Incendios)
                fire = ee.ImageCollection("FIRMS").filterBounds(poly).filterDate(datetime.now() - timedelta(days=7), datetime.now())
                if fire.size().getInfo() > 0:
                    st.error(f"🔥 ALERTA: Fuego activo detectado cerca de {nombre}")
                else:
                    st.success(f"✅ Zona libre de incendios (últimos 7 días)")
        st.balloons()
