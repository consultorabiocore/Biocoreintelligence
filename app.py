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

# --- 1. CONFIGURACIÓN DE PÁGINA Y SEGURIDAD ---
st.set_page_config(page_title="BioCore Intelligence V5", layout="wide")

def check_password():
    """Retorna True si el usuario ingresó credenciales correctas."""
    def password_entered():
        if st.session_state["username"] == st.secrets["auth"]["user"] and \
           st.session_state["password"] == st.secrets["auth"]["password"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # No guardar password
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.title("🔐 Acceso BioCore V5")
        st.text_input("Correo / Usuario", on_change=password_entered, key="username")
        st.text_input("Contraseña", type="password", on_change=password_entered, key="password")
        return False
    elif not st.session_state["password_correct"]:
        st.text_input("Correo / Usuario", on_change=password_entered, key="username")
        st.text_input("Contraseña", type="password", on_change=password_entered, key="password")
        st.error("😕 Credenciales incorrectas")
        return False
    else:
        return True

if check_password():
    # --- 2. CONFIGURACIÓN DE IDENTIDAD ---
    T_TOKEN = st.secrets["telegram"]["token"]
    T_ID = st.secrets["telegram"]["chat_id"]
    UMBRAL_CRITICO = 0.4
    DIRECTORA = "Loreto Campos Carrasco"

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

    # --- 3. BARRA LATERAL (OPCIONES) ---
    with st.sidebar:
        st.image("https://img.icons8.com/fluency/96/guarantee.png", width=80)
        st.header("Panel de Control")
        st.write(f"👤 **Usuario:** {st.session_state['username']}")
        umbral = st.slider("Ajustar Umbral Crítico", 0.1, 0.9, UMBRAL_CRITICO)
        st.divider()
        ejecutar = st.button("🚀 EJECUTAR MONITOREO", use_container_width=True)
        if st.button("Log out"):
            st.session_state.clear()
            st.rerun()

    # --- 4. CUERPO PRINCIPAL ---
    st.title("🛰️ BioCore Intelligence V5")
    st.markdown(f"**Directora Técnica:** {DIRECTORA}")

    # Pestañas para organizar la vista
    tab_mapa, tab_datos = st.tabs(["🌍 Mapa de Cobertura", "📊 Análisis Multimodal"])

    with tab_mapa:
        m = folium.Map(location=[-35.0, -71.0], zoom_start=5)
        for n, i in CLIENTES.items():
            p_fol = [[c[1], c[0]] for c in i['coords']]
            folium.Polygon(locations=p_fol, popup=n, color='green', fill=True, fill_opacity=0.3).add_to(m)
        folium_static(m)

    if ejecutar:
        with tab_datos:
            try:
                creds_info = json.loads(st.secrets["gee"]["json"])
                creds = service_account.Credentials.from_service_account_info(creds_info, 
                        scopes=['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/earthengine'])
                
                if not ee.data._credentials: ee.Initialize(creds)
                sheets = build('sheets', 'v4', credentials=creds)

                for nombre, info in CLIENTES.items():
                    st.subheader(f"📍 {nombre}")
                    p = ee.Geometry.Polygon(info['coords'])
                    
                    # Motor Satelital
                    s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED').filterBounds(p).sort('system:time_start', False).first()
                    f_rep = datetime.fromtimestamp(s2.get('system:time_start').getInfo()/1000).strftime('%d/%m/%Y')
                    
                    idx = s2.expression('((B8-B4)/(B8+B4+0.5))*1.5', {'B8':s2.select('B8'),'B4':s2.select('B4')}).rename('sa')\
                        .addBands(s2.normalizedDifference(['B3','B8']).rename('nd'))\
                        .reduceRegion(ee.Reducer.mean(), p, 30).getInfo()

                    # Lógica BioCore
                    estado = "🟢 NORMAL"
                    if idx['nd'] < umbral: estado = "🔴 ALERTA TÉCNICA"

                    # Métricas
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Estado", estado)
                    c2.metric("SAVI", f"{idx['sa']:.3f}")
                    c3.metric("NDWI/NDSI", f"{idx['nd']:.3f}")

                    # Sincronización
                    fila = [[f_rep, idx['sa'], idx['nd'], estado]]
                    sheets.spreadsheets().values().append(spreadsheetId=info['sheet_id'], 
                        range=f"{info['pestaña']}!A2", valueInputOption="USER_ENTERED", body={'values': fila}).execute()
                    
                    requests.post(f"https://api.telegram.org/bot{T_TOKEN}/sendMessage", 
                                 data={"chat_id": T_ID, "text": f"✅ {nombre}: {estado} ({f_rep})"})
                
                st.balloons()
            except Exception as e:
                st.error(f"Error en el motor: {e}")
