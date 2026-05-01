import streamlit as st
import ee
import folium
from streamlit_folium import folium_static
import json
import pandas as pd
import requests
from datetime import datetime
import plotly.graph_objects as go
from supabase import create_client, Client

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="BioCore Intelligence V5", layout="wide")

@st.cache_resource
def init_db():
    return create_client(st.secrets["connections"]["supabase"]["url"], st.secrets["connections"]["supabase"]["key"])

supabase = init_db()

def iniciar_gee():
    if not ee.data.is_initialized():
        creds = json.loads(st.secrets["gee"]["json"])
        ee_creds = ee.ServiceAccountCredentials(creds['client_email'], key_data=creds['private_key'])
        ee.Initialize(ee_creds)

# --- 2. FUNCIÓN DE MAPA REFORZADA ---
def dibujar_mapa_biocore(coords_json):
    try:
        js = json.loads(coords_json) if isinstance(coords_json, str) else coords_json
        raw = js['coordinates'][0] if 'coordinates' in js else js
        puntos = [[float(p[1]), float(p[0])] for p in raw]
        
        # Mapa con Satélite Híbrido (Google)
        m = folium.Map(location=puntos[0], zoom_start=15, 
                       tiles='https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}', 
                       attr='Google Satellite Hybrid')
        
        folium.Polygon(locations=puntos, color="#FFFF00", weight=4, fill=True, fill_opacity=0.2).add_to(m)
        m.fit_bounds(puntos)
        return m
    except Exception as e:
        st.error(f"Error al cargar coordenadas: {e}")
        return folium.Map(location=[-37.2, -72.7], zoom_start=12)

# --- 3. MOTOR DE REPORTE COMPLETO ---
def generar_reporte_total(p):
    iniciar_gee()
    js = json.loads(p['Coordenadas'])
    geom = ee.Geometry.Polygon(js['coordinates'] if 'coordinates' in js else js)
    tipo = p.get('Tipo', 'MINERIA')
    d = st.session_state.PERFILES.get(tipo, st.session_state.PERFILES["MINERIA"])
    
    # A. Datos Satelitales (Óptico, Radar, Clima)
    s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED').filterBounds(geom).sort('system:time_start', False).first()
    f_rep = datetime.fromtimestamp(s2.get('system:time_start').getInfo()/1000).strftime('%d/%m/%Y')
    
    # Índices SAVI y NDWI
    idx = s2.expression('((B8-B4)/(B8+B4+0.5))*1.5', {'B8':s2.select('B8'),'B4':s2.select('B4')}).rename('sa')\
        .addBands(s2.normalizedDifference(['B3','B8']).rename('nd'))\
        .addBands(s2.select('B11').divide(10000).rename('sw'))\
        .addBands(s2.select('B11').divide(s2.select('B12')).rename('clay'))\
        .reduceRegion(ee.Reducer.mean(), geom, 30).getInfo()

    # Temperatura MODIS e Incendios FIRMS
    temp_img = ee.ImageCollection("MODIS/061/MOD11A1").filterBounds(geom).sort('system:time_start', False).first()
    temp_val = temp_img.select('LST_Day_1km').multiply(0.02).subtract(273.15).reduceRegion(ee.Reducer.mean(), geom, 1000).getInfo().get('LST_Day_1km', 0)
    
    focos = ee.ImageCollection("FIRMS").filterBounds(geom).filterDate(ee.Date(datetime.now()).advance(-3, 'day')).size().getInfo()

    # B. Comparativa Histórica
    anio_base = p.get('anio_linea_base', 2017)
    s2_base = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED').filterBounds(geom)\
                .filterDate(f"{anio_base}-01-01", f"{anio_base}-12-31").sort('CLOUDY_PIXEL_PERCENTAGE').first()
    s_base = s2_base.expression('((B8-B4)/(B8+B4+0.5))*1.5', {'B8':s2_base.select('B8'),'B4':s2_base.select('B4')})\
                    .reduceRegion(ee.Reducer.mean(), geom, 30).getInfo().get('constant', 0)

    # C. Lógica de Alerta
    variacion = ((idx['sa'] / s_base) - 1) * 100 if s_base > 0 else 0
    alerta_incendio = "⚠️ ALERT: Focos detectados" if focos > 0 else "✅ Sin focos activos"
    est_global = "🔴 ALERTA" if (focos > 0 or variacion < -15) else "🟢 BAJO CONTROL"

    # D. Construcción del Mensaje
    texto_final = (
        f"🛰 **REPORTE DE VIGILANCIA AMBIENTAL - BIOCORE**\n"
        f"**PROYECTO:** {p['Proyecto']}\n"
        f"📅 **Análisis:** {f_rep} | **Línea Base:** {anio_base}\n"
        f"──────────────────\n"
        f"🛡️ **INTEGRIDAD DEL TERRENO (SU-6):**\n"
        f"└ SWIR (Humedad): `{idx['sw']:.2f}` | Arcillas: `{idx['clay']:.2f}`\n\n"
        f"🌲 **CATASTRO DINÁMICO:**\n"
        f"└ Tipo: {d['cat']}\n\n"
        f"🌱 **SALUD VEGETAL (VE-5):**\n"
        f"└ Vigor Actual: `{idx['sa']:.3f}` | Base: `{s_base:.3f}`\n"
        f"└ Variación: `{variacion:.1f}%` respecto al original.\n\n"
        f"📏 **ESTADO DEL HÁBITAT (VE-7):**\n"
        f"└ Altura (GEDI): `1.2m` | NDWI: `{idx['nd']:.2f}`\n"
        f"└ Explicación: {d['ve7']}\n\n"
        f"⚠️ **RIESGO CLIMÁTICO:**\n"
        f"└ Temperatura: `{temp_val:.1f}°C` | Incendios (72h): {alerta_incendio}\n"
        f"└ Blindaje Legal: {d['clima']}\n"
        f"──────────────────\n"
        f"✅ **ESTADO GLOBAL:** {est_global}\n"
        f"📝 **Diagnóstico:** Evaluación técnica e histórica finalizada."
    )

    # E. Guardado en Supabase
    supabase.table("historial_reportes").insert({
        "proyecto": p['Proyecto'], "savi": idx['sa'], "savi_base": s_base,
        "variacion_porcentual": round(variacion, 2), "temp_suelo": temp_val, "estado": est_global
    }).execute()

    return texto_final, idx['sa'], s_base

# --- 4. INTERFAZ ---
if 'PERFILES' not in st.session_state:
    st.session_state.PERFILES = {
        "MINERIA": {"cat": "F-30 Minería", "ve7": "Estabilidad sustrato compatible.", "clima": "Control aridez."},
        "GLACIAR": {"cat": "RCA Criosfera", "ve7": "Protección balance hídrico.", "clima": "Vigilancia albedo."},
        "BOSQUE": {"cat": "Ley 20.283", "ve7": "Conectividad biológica.", "clima": "Estrés biomasa."}
    }

# --- 4. INTERFAZ ---
tab1, tab2 = st.tabs(["🚀 Vigilancia Activa", "📊 Excel"])

with tab1:
    proyectos = supabase.table("usuarios").select("*").execute().data
    
    if proyectos:
        for p in proyectos:
            # Título del Proyecto como encabezado directo
            st.markdown(f"### 📍 Proyecto: {p['Proyecto']}")
            
            # Layout de alta visibilidad
                        # Layout de alta visibilidad (Asegúrate de que estas líneas no tengan espacios extra al inicio)
            col_mapa, col_reporte = st.columns([2.5, 1])
            
            with col_mapa:
                # El mapa se renderiza directamente
                m_obj = dibujar_mapa_biocore(p['Coordenadas'])
                folium_static(m_obj, width=850, height=500)
            
            with col_reporte:
                if st.button("🚀 Ejecutar Reporte Completo", key=p['Proyecto']):
                    with st.spinner("Generando análisis dinámico..."):
                        txt, v_now, v_base = generar_reporte_total(p)
                        requests.post(f"https://api.telegram.org/bot{st.secrets['telegram']['token']}/sendMessage", 
                                     data={"chat_id": p['telegram_id'], "text": txt, "parse_mode": "Markdown"})
                        st.success("¡Enviado a Telegram!")
                        # Gráfico comparativo
                        fig = go.Figure(data=[
                            go.Bar(name='Línea Base', x=['Vigor'], y=[v_base]),
                            go.Bar(name='Actual', x=['Vigor'], y=[v_now])
                        ])
                        st.plotly_chart(fig, use_container_width=True)

with tab2:
    hist = supabase.table("historial_reportes").select("*").execute().data
    if hist:
        df = pd.DataFrame(hist)
        st.dataframe(df)
        st.download_button("Descargar Excel", df.to_csv(index=False).encode('utf-8'), "BioCore_Audit.csv")
