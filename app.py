import streamlit as st
import json
import ee
import requests
from datetime import datetime
from googleapiclient.discovery import build
from google.oauth2 import service_account
from streamlit_folium import folium_static
import folium

# --- 1. CONFIGURACIÓN E IDENTIDAD ---
st.set_page_config(page_title="BioCore V5", layout="wide")

def check_password():
    if "password_correct" not in st.session_state:
        st.title("🛰️ BioCore Intelligence V5")
        st.subheader("Acceso Restringido")
        
        # Inputs limpios
        u_input = st.text_input("Usuario / Correo")
        p_input = st.text_input("Contraseña", type="password")
        
        if st.button("Entrar"):
            # Comparación directa con tus Secrets
            if u_input == st.secrets["auth"]["user"] and p_input == st.secrets["auth"]["password"]:
                st.session_state["password_correct"] = True
                st.rerun()
            else:
                st.error("Credenciales incorrectas. Revisa que no haya espacios al final.")
        return False
    return True

# --- 2. FLUJO PRINCIPAL ---
if check_password():
    # Variables desde tus Secrets
    T_TOKEN = st.secrets["telegram"]["token"]
    T_ID = st.secrets["telegram"]["chat_id"]
    
    with st.sidebar:
        st.success(f"Conectada: {st.secrets['auth']['user']}")
        umbral = st.slider("Umbral Crítico", 0.1, 0.9, 0.4)
        ejecutar = st.button("🚀 INICIAR ESCANEO", use_container_width=True)
        if st.button("Salir"):
            st.session_state.clear()
            st.rerun()

    st.title("🛰️ Panel de Monitoreo")
    
    # Diccionario de Clientes
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

    # Mostrar Mapa
    m = folium.Map(location=[-35.0, -71.0], zoom_start=5)
    for n, i in CLIENTES.items():
        p_fol = [[c[1], c[0]] for c in i['coords']]
        folium.Polygon(locations=p_fol, popup=n, color='green', fill=True).add_to(m)
    folium_static(m)

    if ejecutar:
        try:
            # Autenticación GEE con tu JSON de Secrets
            creds_info = json.loads(st.secrets["gee"]["json"])
            creds = service_account.Credentials.from_service_account_info(creds_info, 
                    scopes=['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/earthengine'])
            
            if not ee.data._credentials: ee.Initialize(creds)
            sheets = build('sheets', 'v4', credentials=creds)

            for nombre, info in CLIENTES.items():
                st.write(f"Procesando **{nombre}**...")
                poly = ee.Geometry.Polygon(info['coords'])
                
                # Análisis Satelital
                s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED').filterBounds(poly).sort('system:time_start', False).first()
                fecha = datetime.fromtimestamp(s2.get('system:time_start').getInfo()/1000).strftime('%d/%m/%Y')
                
                res = s2.expression('((B8-B4)/(B8+B4+0.5))*1.5', {'B8':s2.select('B8'),'B4':s2.select('B4')}).rename('sa')\
                    .addBands(s2.normalizedDifference(['B3','B8']).rename('nd'))\
                    .reduceRegion(ee.Reducer.mean(), poly, 30).getInfo()

                estado = "🟢 NORMAL" if res['nd'] > umbral else "🔴 ALERTA"
                
                # Visualización
                st.info(f"**{nombre}** | Estado: {estado} | SAVI: {res['sa']:.3f}")

                # Guardar en Sheets
                fila = [[fecha, res['sa'], res['nd'], estado]]
                sheets.spreadsheets().values().append(spreadsheetId=info['sheet_id'], 
                    range=f"{info['pest']}!A2", valueInputOption="USER_ENTERED", body={'values': fila}).execute()
                
                # Notificar Telegram
                requests.post(f"https://api.telegram.org/bot{T_TOKEN}/sendMessage", 
                             data={"chat_id": T_ID, "text": f"✅ REPORTE: {nombre}\nEstado: {estado}\nFecha: {fecha}"})

            st.balloons()
        except Exception as e:
            st.error(f"Error técnico: {e}")
