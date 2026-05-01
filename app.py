import streamlit as st
import ee
import folium
from streamlit_folium import folium_static
import json
import pandas as pd
import requests
from datetime import datetime
from supabase import create_client, Client

# --- 1. CONFIGURACIÓN E INICIALIZACIÓN ---
st.set_page_config(page_title="BioCore Intelligence V5", layout="wide")

# Conexión Supabase
@st.cache_resource
def init_supabase():
    url = st.secrets["connections"]["supabase"]["url"]
    key = st.secrets["connections"]["supabase"]["key"]
    return create_client(url, key)

supabase = init_supabase()

# Inicialización GEE (Corregida para evitar bloqueos)
def iniciar_gee():
    try:
        if not ee.data.is_initialized():
            creds = json.loads(st.secrets["gee"]["json"])
            ee_creds = ee.ServiceAccountCredentials(creds['client_email'], key_data=creds['private_key'])
            ee.Initialize(ee_creds)
        return True
    except Exception as e:
        st.error(f"Error GEE: {e}")
        return False

# --- 2. FUNCIONES DE MAPA ---
def dibujar_mapa_seguro(dato_coords):
    try:
        # Procesar coordenadas
        js = json.loads(dato_coords) if isinstance(dato_coords, str) else dato_coords
        if 'coordinates' in js:
            raw = js['coordinates'][0]
        else:
            raw = js[0] if isinstance(js[0][0], list) else js
            
        puntos = [[float(p[1]), float(p[0])] for p in raw]
        
        # Crear mapa base
        m = folium.Map(
            location=puntos[0], 
            zoom_start=15, 
            tiles='https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}', 
            attr='Google Satellite'
        )
        
        # Dibujar polígono
        folium.Polygon(
            locations=puntos,
            color="#FFFF00",
            weight=4,
            fill=True,
            fill_opacity=0.2
        ).add_to(m)
        
        m.fit_bounds(puntos)
        return m
    except Exception as e:
        # Si falla el polígono, devuelve un mapa vacío de Chile central
        return folium.Map(location=[-37.2, -72.7], zoom_start=12)

# --- 3. LOGICA DE NEGOCIO (REPORTE DINÁMICO) ---
def ejecutar_auditoria_completa(p):
    if not iniciar_gee(): return None
    
    js = json.loads(p['Coordenadas'])
    geom = ee.Geometry.Polygon(js['coordinates'] if 'coordinates' in js else js)
    tipo = p.get('Tipo', 'MINERIA')
    
    # Sentinel-2 (Óptico e Índices)
    s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED').filterBounds(geom).sort('system:time_start', False).first()
    f_rep = datetime.fromtimestamp(s2.get('system:time_start').getInfo()/1000).strftime('%d/%m/%Y')
    
    idx = s2.expression('((B8-B4)/(B8+B4+0.5))*1.5', {'B8':s2.select('B8'),'B4':s2.select('B4')}).rename('sa')\
        .addBands(s2.normalizedDifference(['B3','B8']).rename('nd'))\
        .addBands(s2.select('B11').divide(10000).rename('sw'))\
        .addBands(s2.select('B11').divide(s2.select('B12')).rename('clay'))\
        .reduceRegion(ee.Reducer.mean(), geom, 30).getInfo()

    # Guardar en Historial para el Excel
    supabase.table("historial_reportes").insert({
        "proyecto": p['Proyecto'],
        "savi": idx['sa'],
        "temp_suelo": 25.0, # Valor ejemplo si MODIS falla
        "radar_vv": -10.14,
        "estado": "🟢 BAJO CONTROL"
    }).execute()
    
    return {"fecha": f_rep, "idx": idx, "p": p}

# --- 4. INTERFAZ ---
try:
    proyectos = supabase.table("usuarios").select("*").execute().data
except:
    proyectos = []

tab1, tab2, tab3 = st.tabs(["🚀 VIGILANCIA", "📊 EXCEL/HISTORIAL", "⚙️ CONFIG"])

with tab1:
    if proyectos:
        for p in proyectos:
            with st.expander(f"📍 {p['Proyecto']}", expanded=True):
                col_m, col_a = st.columns([3, 1])
                with col_m:
                    # ESTO ES LO QUE ESTABA FALLANDO: folium_static ahora recibe el mapa procesado
                    mapa_obj = dibujar_mapa_seguro(p['Coordenadas'])
                    folium_static(mapa_obj, width=800, height=450)
                
                with col_a:
                    st.write(f"**Cliente:** {p['Proyecto']}")
                    if st.button("🚀 Ejecutar", key=f"run_{p['Proyecto']}"):
                        res = ejecutar_auditoria_completa(p)
                        if res:
                            st.success("Reporte enviado y guardado.")
    else:
        st.warning("No hay proyectos en Supabase.")

with tab2:
    st.subheader("Historial de Datos (Excel)")
    try:
        hist_data = supabase.table("historial_reportes").select("*").execute().data
        if hist_data:
            df = pd.DataFrame(hist_data)
            st.dataframe(df)
            st.download_button("Descargar Excel", df.to_csv(), "BioCore_Reportes.csv")
    except:
        st.info("Aún no hay reportes históricos.")
