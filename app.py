import streamlit as st
import ee
import json
import pandas as pd
import requests
from google.oauth2 import service_account
from googleapiclient.discovery import build
from datetime import datetime, timedelta
from fpdf import FPDF
import folium
from streamlit_folium import folium_static

# --- 1. CONFIGURACIÓN ESTRATÉGICA ---
st.set_page_config(page_title="BioCore Intelligence Console", layout="wide")

T_TOKEN = st.secrets["telegram"]["token"]
T_ID = st.secrets["telegram"]["chat_id"]
DIRECTORA = "Loreto Campos Carrasco"

def clean(text):
    return text.encode('latin-1', 'replace').decode('latin-1')

# --- 2. BASE DE DATOS DE PROYECTOS ---
CLIENTES = {
 "Laguna Señoraza (Laja)": {
    "coords": [[-72.715,-37.275],[-72.715,-37.285],[-72.690,-37.285],[-72.690,-37.270]], 
    "tipo": "HUMEDAL", "glaciar": False,
    "sheet_id": "1x6yAXNNlea3e43rijJu0aqcRpe4oP3BEnzgSgLuG1vU", "pestaña": "ID_CARPETA_1"
 },
 "Pascua Lama (Cordillera)": {
    "coords": [[-70.033,-29.316],[-70.016,-29.316],[-70.016,-29.333],[-70.033,-29.333]], 
    "tipo": "MINERIA", "glaciar": True,
    "sheet_id": "1UTrDs939rPlVIR1OTIwbJ6rM3FazgjX43YnJdue-Dmc", "pestaña": "ID_CARPETA_2"
 }
}

# --- 3. INICIALIZACIÓN DE SERVICIOS ---
@st.cache_resource
def iniciar_servicios():
    try:
        creds_info = json.loads(st.secrets["gee"]["json"])
        creds = service_account.Credentials.from_service_account_info(
            creds_info, scopes=['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/earthengine']
        )
        try: ee.Initialize(credentials=creds)
        except: pass
        return build('sheets', 'v4', credentials=creds)
    except Exception as e:
        st.sidebar.error(f"Error de conexión: {e}")
        return None

service = iniciar_servicios()

# --- 5. PANEL LATERAL (Pestaña Izquierda) ---
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/satellite.png", width=80)
    st.title("BioCore Admin")
    st.markdown(f"**Directora:** {DIRECTORA}")
    st.divider()
    
    menu = st.radio(
        "Navegación:",
        ["🛰️ Monitor en Vivo", "📊 Historial de Datos", "🔥 Alertas de Incendios", "📜 Reportes Legales"]
    )
    
    st.divider()
    st.info("Sensores Activos:\n- Sentinel 1/2\n- Landsat 8/9\n- FIRMS (Incendios)\n- GEDI (Altura)")

# --- 6. LÓGICA DE NAVEGACIÓN ---

if service:
    sel = st.selectbox("🎯 Polígono de Auditoría:", list(CLIENTES.keys()))
    info = CLIENTES[sel]

    if menu == "🛰️ Monitor en Vivo":
        col_map, col_ctrl = st.columns([2, 1])

        with col_map:
            st.subheader("Visualización Satelital")
            avg_lat = sum(p[1] for p in info['coords']) / len(info['coords'])
            avg_lon = sum(p[0] for p in info['coords']) / len(info['coords'])
            m = folium.Map(location=[avg_lat, avg_lon], zoom_start=14)
            folium.TileLayer('https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}', attr='Google', name='Google Sat').add_to(m)
            folium.Polygon(locations=[[p[1], p[0]] for p in info['coords']], color='#2ecc71', fill=True, opacity=0.4).add_to(m)
            folium_static(m)

        with col_ctrl:
            st.subheader("Acciones")
            if st.button("🚀 ESCANEO TOTAL"):
                with st.spinner("Procesando telemetría..."):
                    try:
                        p = ee.Geometry.Polygon(info['coords'])
                        
                        # Sentinel-2 & Índices
                        s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED').filterBounds(p).sort('system:time_start', False).first()
                        f_rep = datetime.fromtimestamp(s2.get('system:time_start').getInfo()/1000).strftime('%d/%m/%Y')
                        idx = s2.expression('((B8-B4)/(B8+B4+0.5))*1.5', {'B8':s2.select('B8'),'B4':s2.select('B4')}).rename('sa')\
                            .addBands(s2.normalizedDifference(['B3','B8']).rename('nd'))\
                            .addBands(s2.normalizedDifference(['B3','B11']).rename('mn'))\
                            .reduceRegion(ee.Reducer.mean(), p, 30).getInfo()

                        # Landsat (Temperatura)
                        l8 = ee.ImageCollection('LANDSAT/LC08/C02/T1_L2').filterBounds(p).sort('system:time_start', False).first()
                        lst = l8.select('ST_B10').multiply(0.00341802).add(149.0).subtract(273.15).reduceRegion(ee.Reducer.mean(), p, 30).getInfo().get('ST_B10', 0)

                        st.session_state['res'] = {"fecha": f_rep, "savi": idx['sa'], "ndsi": idx['mn'], "temp": lst, "poligono": sel}
                        
                        # Guardar en Sheet
                        service.spreadsheets().values().append(
                            spreadsheetId=info['sheet_id'], range=f"{info['pestaña']}!A2", 
                            valueInputOption="USER_ENTERED", body={'values': [[f_rep, idx['sa'], idx['nd'], idx['mn'], lst]]}
                        ).execute()
                        st.success("Sincronizado con Sheets.")
                    except Exception as e: st.error(f"Error: {e}")

            if 'res' in st.session_state:
                st.metric("Vigor SAVI", f"{st.session_state['res']['savi']:.2f}")
                st.metric("Temp. Superficie", f"{st.session_state['res']['temp']:.1f}°C")

    elif menu == "📊 Historial de Datos":
        st.subheader("Base de Datos BioCore (Google Sheets)")
        try:
            res = service.spreadsheets().values().get(spreadsheetId=info['sheet_id'], range=f"{info['pestaña']}!A:E").execute()
            df = pd.DataFrame(res.get('values', [])[1:], columns=["Fecha", "SAVI", "NDWI", "NDSI", "Temp"])
            st.dataframe(df, use_container_width=True)
            st.line_chart(df.set_index("Fecha")["SAVI"])
        except: st.warning("No hay datos históricos para este proyecto.")

    elif menu == "🔥 Alertas de Incendios":
        st.subheader("Monitoreo de Focos de Calor (FIRMS)")
        p = ee.Geometry.Polygon(info['coords'])
        fire = ee.ImageCollection('FIRMS').filterBounds(p).filterDate((datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d'), datetime.now().strftime('%Y-%m-%d'))
        count = fire.size().getInfo()
        if count > 0:
            st.error(f"⚠️ ¡ALERTA! Se han detectado {count} focos térmicos en los últimos 7 días.")
        else:
            st.success("✅ Sin incendios detectados en el área recientemente.")

    elif menu == "📜 Reportes Legales":
        st.subheader("Gestión de Evidencia")
        if 'res' in st.session_state:
            st.write(f"Último análisis disponible: {st.session_state['res']['fecha']}")
            if st.button("📧 Enviar Reporte PDF a Telegram"):
                # Lógica de PDF que ya tenemos...
                st.info("Transmitiendo reporte...")
        else:
            st.warning("Debe ejecutar un escaneo en 'Monitor en Vivo' primero.")
