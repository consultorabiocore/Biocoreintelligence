import streamlit as st
import pandas as pd
import json
import ee
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from fpdf import FPDF
from supabase import create_client

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="BioCore Intelligence", layout="wide")

@st.cache_resource
def init_supabase():
    return create_client(st.secrets["connections"]["supabase"]["url"], st.secrets["connections"]["supabase"]["key"])

def init_gee():
    try:
        gee_json = json.loads(st.secrets["gee"]["json"])
        credentials = ee.ServiceAccountCredentials(gee_json['client_email'], key_data=gee_json['private_key'])
        ee.Initialize(credentials, project=gee_json['project_id'])
        return True
    except Exception as e:
        st.error(f"Error GEE: {e}")
        return False

# --- 2. MOTOR HISTÓRICO (Días a Años) ---
def obtener_serie_historica(poligono_str, meses_atras=24):
    roi = ee.Geometry.Polygon(json.loads(poligono_str))
    ahora = datetime.now()
    inicio = ahora - timedelta(days=meses_atras * 30)
    
    # Colección Sentinel-2
    coleccion = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED') \
        .filterBounds(roi) \
        .filterDate(inicio.strftime('%Y-%m-%d'), ahora.strftime('%Y-%m-%d')) \
        .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20))

    def calcular_punto(img):
        savi = img.expression('((B8-B4)/(B8+B4+0.5))*1.5', {
            'B8': img.select('B8'), 'B4': img.select('B4')
        })
        stats = savi.reduceRegion(ee.Reducer.mean(), roi, 30).getInfo()
        return img.set('savi_val', stats.get('constant', 0))

    serie = coleccion.map(calcular_punto).aggregate_array('savi_val').getInfo()
    fechas = coleccion.aggregate_array('system:time_start').getInfo()
    fechas_dt = [datetime.fromtimestamp(f/1000).strftime('%Y-%m') for f in fechas]
    
    return pd.DataFrame({'Fecha': fechas_dt, 'SAVI': serie}).groupby('Fecha').mean().reset_index()

# --- 3. INTERFAZ ---
st.title("🌿 BioCore Intelligence")

if 'auth' not in st.session_state: st.session_state.auth = False

with st.sidebar:
    if not st.session_state.auth:
        email = st.text_input("Email").lower().strip()
        passw = st.text_input("Password", type="password")
        if st.button("Acceder"):
            res = init_supabase().table("usuarios").select("*").eq("Email", email).execute()
            if res.data and str(res.data[0]['Password']) == passw:
                st.session_state.auth, st.session_state.user = True, res.data[0]
                st.rerun()
    else:
        if st.button("Cerrar Sesión"): st.session_state.auth = False; st.rerun()

if st.session_state.auth:
    u = st.session_state.user
    st.header(f"Panel de Control: {u['Proyecto']}")
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("Análisis Actual")
        if st.button("🚀 Escanear Hoy"):
            if init_gee():
                with st.spinner("Calculando..."):
                    # Aquí llamarías a tu función de índices actuales
                    st.metric("Vigor Actual", "0.42") 
                    st.success("Escaneo completado.")

    with col2:
        st.subheader("📈 Registro Histórico (Evolución)")
        años = st.slider("Años de historial", 1, 5, 2)
        if st.button("Generar Línea de Tiempo"):
            if init_gee():
                with st.spinner(f"Extrayendo datos satelitales de los últimos {años} años..."):
                    df_hist = obtener_serie_historica(u['Coordenadas'], años * 12)
                    
                    # Gráfico Profesional
                    fig, ax = plt.subplots(figsize=(10, 4))
                    ax.plot(df_hist['Fecha'], df_hist['SAVI'], color='#2ecc71', linewidth=2, marker='o', markersize=4)
                    plt.xticks(rotation=45)
                    ax.set_ylabel("Vigor Vegetal (SAVI)")
                    ax.grid(True, alpha=0.3)
                    st.pyplot(fig)
                    
                    st.write("Este gráfico muestra la salud del ecosistema detectada por el satélite Sentinel-2 en cada paso sobre el área.")
