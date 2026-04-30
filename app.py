import streamlit as st
import pandas as pd
import json
import ee
import requests
from datetime import datetime
from googleapiclient.discovery import build
from google.oauth2 import service_account
from streamlit_folium import folium_static
import folium

# --- 1. CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="BioCore Intelligence V5", layout="wide", page_icon="🛰️")

# --- 2. SISTEMA DE SEGURIDAD ---
def check_password():
    if "password_correct" not in st.session_state:
        st.title("🔐 Acceso BioCore V5")
        u = st.text_input("Usuario / Correo", key="input_user")
        p = st.text_input("Contraseña", type="password", key="input_pass")
        
        if st.button("Ingresar"):
            # Comprobación contra los Secrets que acabas de configurar
            if u == st.secrets["auth"]["user"] and p == st.secrets["auth"]["password"]:
                st.session_state["password_correct"] = True
                st.session_state["usuario_actual"] = u
                st.rerun()
            else:
                st.error("❌ Credenciales incorrectas. Revisa tus Secrets en Streamlit.")
        return False
    return True

if check_password():
    # --- 3. INICIALIZACIÓN DE SERVICIOS ---
    T_TOKEN = st.secrets["telegram"]["token"]
    T_ID = st.secrets["telegram"]["chat_id"]
    UMBRAL_CRITICO = 0.4

    # Diccionario de Proyectos (Laja y Pascua Lama)
    CLIENTES = {
        "Laguna Señoraza (Laja)": {
            "coords": [[-72.715,-37.275],[-72.715,-37.285],[-72.690,-37.285],[-72.690,-37.270]], 
            "tipo": "HUMEDAL", "sheet_id": "1x6yAXNNlea3e43rijJu0aqcRpe4oP3BEnzgSgLuG1vU", "pestaña": "Humedales"
        },
        "Pascua Lama (Cordillera)": {
            "coords": [[-70.033,-29.316],[-70.016,-29.316],[-70.016,-29.333],[-70.033,-29.333]], 
            "tipo": "GLACIAR", "sheet_id": "1UTrDs939rPlVIR1OTIwbJ6rM3FazgjX43YnJdue-Dmc", "pestaña": "Mineria"
        }
    }

    # --- 4. BARRA LATERAL (CONTROL) ---
    with st.sidebar:
        st.header("🌐 BioCore Panel")
        st.write(f"Conectado como: **{st.session_state['usuario_actual']}**")
        umbral = st.slider("Ajustar Umbral Crítico", 0.1, 0.9, UMBRAL_CRITICO)
        st.divider()
        ejecutar = st.button("🚀 INICIAR MONITOREO", use_container_width=True)
        if st.button("Cerrar Sesión"):
            st.session_state.clear()
            st.rerun()

    # --- 5. CUERPO PRINCIPAL ---
    st.title("🛰️ BioCore Intelligence V5")
    
    tab1, tab2 = st.tabs(["🌍 Vista Espacial", "📊 Reporte Técnico"])

    with tab1:
        st.subheader("Mapa de Áreas de Estudio")
        m = folium.Map(location=[-33.0, -70.0], zoom_start=5)
        for n, i in CLIENTES.items():
            p_fol = [[c[1], c[0]] for c in i['coords']]
            folium.Polygon(locations=p_fol, popup=n, color='blue', fill=True, fill_opacity=0.3).add_to(m)
        folium_static(m)

    if ejecutar:
        with tab2:
            try:
                # Conexión con GEE usando tu nuevo JSON
                creds_info = json.loads(st.secrets["gee"]["json"])
                creds = service_account.Credentials.from_service_account_info(creds_info, 
                        scopes=['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/earthengine'])
                
                if not ee.data._credentials: ee.Initialize(creds)
                
                # Conexión con Google Sheets
                sheets = build('sheets', 'v4', credentials=creds)

                for nombre, info in CLIENTES.items():
                    st.write(f"### Analizando: {nombre}")
                    p = ee.Geometry.Polygon(info['coords'])
                    
                    # Captura Sentinel-2
                    s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED').filterBounds(p).sort('system:time_start', False).first()
                    f_rep = datetime.fromtimestamp(s2.get('system:time_start').getInfo()/1000).strftime('%d/%m/%Y')
                    
                    # Cálculo de SAVI y NDWI/NDSI
                    idx = s2.expression('((B8-B4)/(B8+B4+0.5))*1.5', {'B8':s2.select('B8'),'B4':s2.select('B4')}).rename('sa')\
                        .addBands(s2.normalizedDifference(['B3','B8']).rename('nd'))\
                        .reduceRegion(ee.Reducer.mean(), p, 30).getInfo()

                    # Evaluación de Estado
                    estado = "🟢 NORMAL"
                    if idx['nd'] < umbral: 
                        estado = "🔴 ALERTA CRÍTICA"

                    # Mostrar métricas
                    c1, c2 = st.columns(2)
                    c1.metric("Estado", estado)
                    c2.metric("Valor del Índice", f"{idx['nd']:.3f}")
                    
                    # Sincronizar con Google Sheets
                    fila = [[f_rep, idx['sa'], idx['nd'], estado]]
                    sheets.spreadsheets().values().append(spreadsheetId=info['sheet_id'], 
                        range=f"{info['pestaña']}!A2", valueInputOption="USER_ENTERED", body={'values': fila}).execute()
                    
                    # Notificar a Telegram
                    requests.post(f"https://api.telegram.org/bot{T_TOKEN}/sendMessage", 
                                 data={"chat_id": T_ID, "text": f"✅ REPORTE BIOCORE: {nombre}\nEstado: {estado}\nFecha: {f_rep}"})

                st.balloons()
                st.success("Monitoreo finalizado y datos respaldados.")

            except Exception as e:
                st.error(f"Error en el motor: {e}")
