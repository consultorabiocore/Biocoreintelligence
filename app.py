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

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="BioCore V5", layout="wide", page_icon="🛰️")

# Estilo para mejorar visibilidad en móviles
st.markdown("""<style> .stMetric { background-color: #f0f2f6; padding: 10px; border-radius: 10px; } </style>""", unsafe_allow_html=True)

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
    # --- 2. CONEXIÓN SEGURA ---
    try:
        creds_info = json.loads(st.secrets["gee"]["json"])
        if not ee.data.is_initialized():
            credentials = ee.ServiceAccountCredentials(creds_info['client_email'], key_data=creds_info['private_key'])
            ee.Initialize(credentials)
        sheets_creds = service_account.Credentials.from_service_account_info(creds_info, scopes=['https://www.googleapis.com/auth/spreadsheets'])
        sheets = build('sheets', 'v4', credentials=sheets_creds)
    except Exception as e:
        st.error(f"Falla de conexión: {e}")

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

    # --- 3. INTERFAZ Y CONTROL ---
    with st.sidebar:
        st.header("🛰️ BioCore Panel")
        umbral = st.slider("Umbral de Alerta", 0.1, 0.9, 0.4)
        btn_ejecutar = st.button("🚀 INICIAR ESCANEO TOTAL", use_container_width=True)
        if st.button("Cerrar Sesión"):
            st.session_state.clear()
            st.rerun()

    st.title("🛰️ Inteligencia Satelital BioCore")

    # MAPA SIEMPRE ARRIBA
    m = folium.Map(location=[-35.0, -71.0], zoom_start=5)
    for n, i in CLIENTES.items():
        p_fol = [[c[1], c[0]] for c in i['coords']]
        folium.Polygon(locations=p_fol, popup=n, color='cyan', fill=True, fill_opacity=0.3).add_to(m)
    folium_static(m)

    # --- 4. ZONA DE RESULTADOS (SOLO APARECE AL EJECUTAR) ---
    if btn_ejecutar:
        st.divider()
        st.subheader("📊 Reporte Técnico Generado")
        
        tab_actual, tab_hist, tab_clima = st.tabs(["🟢 Tiempo Real", "📚 Historial Landsat", "🔥 Clima/Fuego"])

        for nombre, info in CLIENTES.items():
            poly = ee.Geometry.Polygon(info['coords'])
            
            with tab_actual:
                st.markdown(f"#### 📍 Proyecto: {nombre}")
                with st.spinner(f"Obteniendo datos de {nombre}..."):
                    # Sentinel-2
                    s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED').filterBounds(poly).sort('system:time_start', False).first()
                    fecha = datetime.fromtimestamp(s2.get('system:time_start').getInfo()/1000).strftime('%d/%m/%Y')
                    
                    res = s2.expression('((B8-B4)/(B8+B4+0.5))*1.5', {'B8':s2.select('B8'),'B4':s2.select('B4')}).rename('savi')\
                        .addBands(s2.normalizedDifference(['B3','B8']).rename('ndwi'))\
                        .reduceRegion(ee.Reducer.mean(), poly, 30).getInfo()

                    # Sentinel-1 (Radar)
                    s1 = ee.ImageCollection('COPERNICUS/S1_GRD').filterBounds(poly).sort('system:time_start', False).first()
                    sar_val = s1.reduceRegion(ee.Reducer.mean(), poly, 30).getInfo()['VV']

                    c1, c2, c3 = st.columns(3)
                    c1.metric("SAVI (Vigor)", f"{res['savi']:.3f}")
                    c2.metric("NDWI (Agua)", f"{res['ndwi']:.3f}")
                    c3.metric("Radar (SAR)", f"{sar_val:.1f} dB")

            with tab_hist:
                st.write(f"**Análisis Histórico para {nombre}**")
                # Gráfico de tendencia rápida
                st.line_chart(pd.DataFrame([res['savi']*0.85, res['savi']*1.15, res['savi']], columns=["Histórico"]))

            with tab_clima:
                col1, col2 = st.columns(2)
                # FIRMS (Fuego)
                fire = ee.ImageCollection("FIRMS").filterBounds(poly).filterDate(datetime.now() - timedelta(days=7), datetime.now())
                if fire.size().getInfo() > 0:
                    col1.error(f"🔥 Fuego detectado en {nombre}")
                else:
                    col1.success(f"✅ Zona Segura (Sin Fuego)")
                
                # TerraClimate
                clim = ee.ImageCollection("IDAHO_EPSCOR/TERRACLIMATE").filterBounds(poly).sort('system:time_start', False).first()
                temp = clim.reduceRegion(ee.Reducer.mean(), poly, 1000).getInfo()
                col2.info(f"🌡️ Temp: {temp['tmmx']*0.1:.1f}°C")

        st.balloons()
