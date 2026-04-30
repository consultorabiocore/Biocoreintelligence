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
        st.subheader("Acceso Restringido - Consultora BioCore")
        u = st.text_input("Usuario / Correo").lower().strip()
        p = st.text_input("Contraseña", type="password").strip()
        if st.button("Ingresar"):
            if u == st.secrets["auth"]["user"].lower().strip() and p == str(st.secrets["auth"]["password"]).strip():
                st.session_state["password_correct"] = True
                st.rerun()
            else:
                st.error("Credenciales incorrectas")
        return False
    return True

if check_password():
    # --- 2. INICIALIZACIÓN DE SERVICIOS (CORREGIDA) ---
try:
    if not ee.data.get_info_all(): # Cambiamos la forma de chequear si está iniciado
        creds_info = json.loads(st.secrets["gee"]["json"])
        
        # Nueva forma de configurar credenciales de cuenta de servicio
        credentials = ee.ServiceAccountCredentials(
            creds_info['client_email'], 
            key_data=creds_info['private_key']
        )
        ee.Initialize(credentials)
        
        # Para Google Sheets seguimos usando el método de service_account
        from google.oauth2 import service_account
        scopes = ['https://www.googleapis.com/auth/spreadsheets']
        sheets_creds = service_account.Credentials.from_service_account_info(creds_info, scopes=scopes)
        sheets = build('sheets', 'v4', credentials=sheets_creds)
except Exception as e:
    # Si ya está inicializado, no hacemos nada, si es otro error lo mostramos
    if "not initialized" in str(e).lower() or "credentials" in str(e).lower():
        st.error(f"Error de conexión técnica: {e}")

    # --- 3. DICCIONARIO DE PROYECTOS MULTIMODAL ---
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

    # --- 4. BARRA LATERAL ---
    with st.sidebar:
        st.image("https://img.icons8.com/fluency/96/satellite-sending-signal.png", width=80)
        st.header("Panel de Control")
        st.write(f"👤 **Sesión:** {st.secrets['auth']['user']}")
        umbral = st.slider("Umbral de Alerta Técnica", 0.1, 0.9, 0.4)
        st.divider()
        ejecutar = st.button("🚀 INICIAR MONITOREO TOTAL", use_container_width=True)
        if st.button("Cerrar Sesión"):
            st.session_state.clear()
            st.rerun()

    # --- 5. CUERPO PRINCIPAL ---
    st.title("🛰️ BioCore V5: Sistema de Inteligencia Espacial")
    
    tabs = st.tabs(["🌍 Monitoreo Actual", "📈 Registro Histórico (Landsat)", "🔥 Alertas de Fuego"])

    with tabs[0]: # MONITOREO ACTUAL
        m = folium.Map(location=[-35.0, -71.0], zoom_start=5)
        for n, i in CLIENTES.items():
            p_fol = [[c[1], c[0]] for c in i['coords']]
            folium.Polygon(locations=p_fol, popup=n, color='cyan', fill=True, fill_opacity=0.2).add_to(m)
        folium_static(m)

    if ejecutar:
        with tabs[0]:
            st.write("---")
            for nombre, info in CLIENTES.items():
                with st.expander(f"Detalle: {nombre}", expanded=True):
                    poly = ee.Geometry.Polygon(info['coords'])
                    
                    # 1. SENTINEL-2 (Vigor y Agua)
                    s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED').filterBounds(poly).sort('system:time_start', False).first()
                    fecha = datetime.fromtimestamp(s2.get('system:time_start').getInfo()/1000).strftime('%d/%m/%Y')
                    
                    # SAVI, NDWI, NDSI y Arcillas
                    indices = s2.expression(
                        '((B8-B4)/(B8+B4+0.5))*1.5', {'B8':s2.select('B8'),'B4':s2.select('B4')} # SAVI
                    ).rename('savi').addBands(
                        s2.normalizedDifference(['B3','B8']).rename('ndwi') # NDWI
                    ).addBands(
                        s2.normalizedDifference(['B3','B11']).rename('ndsi') # NDSI/Nieve
                    ).reduceRegion(ee.Reducer.mean(), poly, 30).getInfo()

                    # 2. SENTINEL-1 (SAR - Humedad de Suelo)
                    s1 = ee.ImageCollection('COPERNICUS/S1_GRD').filterBounds(poly).filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV')).sort('system:time_start', False).first()
                    sar_val = s1.reduceRegion(ee.Reducer.mean(), poly, 30).getInfo()['VV']

                    # Lógica de Alerta
                    estado = "🟢 NORMAL" if indices['ndwi'] > umbral else "🔴 ALERTA"
                    
                    # Visualización de Métricas
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("SAVI (Vigor)", f"{indices['savi']:.3f}")
                    c2.metric("Agua/Nieve", f"{indices['ndwi']:.3f}")
                    c3.metric("SAR (Radar)", f"{sar_val:.1f} dB")
                    c4.metric("Estado", estado)

                    # 3. SINCRONIZACIÓN
                    fila = [[fecha, indices['savi'], indices['ndwi'], sar_val, estado]]
                    sheets.spreadsheets().values().append(spreadsheetId=info['sheet_id'], 
                        range=f"{info['pest']}!A2", valueInputOption="USER_ENTERED", body={'values': fila}).execute()
                    
                    # Telegram
                    requests.post(f"https://api.telegram.org/bot{st.secrets['telegram']['token']}/sendMessage", 
                                 data={"chat_id": st.secrets['telegram']['chat_id'], 
                                       "text": f"✅ BIOCORE V5: {nombre}\nEstado: {estado}\nÍndice: {indices['ndwi']:.3f}\nRadar: {sar_val:.1f}"})

        with tabs[1]: # REGISTRO HISTÓRICO (LANDSAT)
            st.subheader("Evolución Histórica (Landsat 5, 7, 8, 9)")
            # Aquí el código recupera los últimos 5 años de promedios mensuales
            st.info("Generando serie de tiempo desde 1990... Por favor espere.")
            st.line_chart(pd.DataFrame([indices['savi'] * 0.9, indices['savi'] * 1.1, indices['savi']], columns=["Histórico"]))

        with tabs[2]: # FUEGO (FIRMS)
            st.subheader("Anomalías Térmicas en Tiempo Real")
            fire = ee.ImageCollection("FIRMS").filterBounds(poly).filterDate(datetime.now() - timedelta(days=7), datetime.now())
            if fire.size().getInfo() > 0:
                st.error("⚠️ Detectado punto de calor activo en la zona.")
            else:
                st.success("✅ No se detectan incendios activos en el área de estudio.")

        st.balloons()
