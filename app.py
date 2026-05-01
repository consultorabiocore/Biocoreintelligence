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

# --- 1. CONFIGURACIÓN E INICIALIZACIÓN ---
st.set_page_config(page_title="BioCore V5 - Auditoría Histórica", layout="wide")

@st.cache_resource
def init_db():
    return create_client(st.secrets["connections"]["supabase"]["url"], st.secrets["connections"]["supabase"]["key"])

supabase = init_db()

def iniciar_gee():
    if not ee.data.is_initialized():
        creds = json.loads(st.secrets["gee"]["json"])
        ee_creds = ee.ServiceAccountCredentials(creds['client_email'], key_data=creds['private_key'])
        ee.Initialize(ee_creds)

# --- 2. MOTOR DE COMPARACIÓN HISTÓRICA ---
def ejecutar_auditoria_completa(p):
    iniciar_gee()
    js = json.loads(p['Coordenadas'])
    geom = ee.Geometry.Polygon(js['coordinates'] if 'coordinates' in js else js)
    
    # A. Análisis Actual (2026)
    s2_now = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED').filterBounds(geom).sort('system:time_start', False).first()
    f_rep = datetime.fromtimestamp(s2_now.get('system:time_start').getInfo()/1000).strftime('%d/%m/%Y')
    
    idx_now = s2_now.expression('((B8-B4)/(B8+B4+0.5))*1.5', {'B8':s2_now.select('B8'),'B4':s2_now.select('B4')})\
                    .addBands(s2_now.normalizedDifference(['B3','B8']).rename('nd'))\
                    .reduceRegion(ee.Reducer.mean(), geom, 30).getInfo()

    # B. Análisis Línea de Base (Año configurado en SQL, ej: 2017)
    anio_base = p.get('anio_linea_base', 2017)
    fecha_base = ee.Date.fromYMD(anio_base, 1, 1)
    s2_base = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')\
                .filterBounds(geom).filterDate(fecha_base, fecha_base.advance(1, 'year'))\
                .sort('CLOUDY_PIXEL_PERCENTAGE').first()
    
    idx_base = s2_base.expression('((B8-B4)/(B8+B4+0.5))*1.5', {'B8':s2_base.select('B8'),'B4':s2_base.select('B4')})\
                      .reduceRegion(ee.Reducer.mean(), geom, 30).getInfo()

    # C. Lógica de Diagnóstico y Alerta
    s_now = idx_now.get('constant', 0)
    s_base = idx_base.get('constant', 0)
    variacion = ((s_now / s_base) - 1) * 100 if s_base > 0 else 0
    
    motivos = []
    if s_now < 0.1: motivos.append("Vigor vegetativo crítico (SAVI < 0.1)")
    if variacion < -15: motivos.append(f"Pérdida de biomasa significativa ({variacion:.1f}%)")
    
    diag_final = " / ".join(motivos) if motivos else "Sin anomalías significativas detectadas"
    estado_global = "🔴 ALERTA" if motivos else "🟢 BAJO CONTROL"

    # D. Envío a Telegram (Formato Largo)
    reporte_tg = (
        f"🛰 **REPORTE DE VIGILANCIA AMBIENTAL - BIOCORE**\n"
        f"**PROYECTO:** {p['Proyecto']}\n"
        f"📅 **Análisis:** {f_rep} | **Línea Base:** {anio_base}\n"
        f"──────────────────\n"
        f"🌱 **COMPARATIVA DE VIGOR (VE-5):**\n"
        f"└ Actual (2026): `{s_now:.3f}`\n"
        f"└ Base ({anio_base}): `{s_base:.3f}`\n"
        f"└ Variación: `{variacion:.1f}%` respecto al original.\n\n"
        f"⚠️ **DETECCIÓN DE ANOMALÍAS:**\n"
        f"└ Diagnóstico: {diag_final}\n"
        f"──────────────────\n"
        f"✅ **ESTADO GLOBAL:** {estado_global}\n"
        f"📝 **Diagnóstico:** Evaluación histórica finalizada."
    )
    
    # E. Guardado en Supabase (Alimentación Excel)
    supabase.table("historial_reportes").insert({
        "proyecto": p['Proyecto'],
        "savi": s_now,
        "savi_base": s_base,
        "variacion_porcentual": round(variacion, 2),
        "motivo_alerta": diag_final,
        "estado": estado_global
    }).execute()

    return reporte_tg, s_now, s_base

# --- 3. INTERFAZ STREAMLIT ---
t1, t2 = st.tabs(["🚀 Vigilancia Activa", "📊 Historial y Excel"])

try:
    proyectos = supabase.table("usuarios").select("*").execute().data
except:
    proyectos = []

with t1:
    for p in proyectos:
        with st.expander(f"📍 {p['Proyecto']} (Base: {p.get('anio_linea_base', 2017)})", expanded=True):
            col_m, col_a = st.columns([2, 1])
            with col_a:
                if st.button("🔍 Ejecutar Auditoría Histórica", key=p['Proyecto']):
                    with st.spinner("Comparando con línea de base..."):
                        txt, v_now, v_base = ejecutar_auditoria_completa(p)
                        # Enviar Telegram
                        requests.post(f"https://api.telegram.org/bot{st.secrets['telegram']['token']}/sendMessage", 
                                     data={"chat_id": p['telegram_id'], "text": txt, "parse_mode": "Markdown"})
                        
                        # Gráfico Rápido
                        fig = go.Figure(data=[
                            go.Bar(name='Línea Base', x=['SAVI'], y=[v_base], marker_color='gray'),
                            go.Bar(name='Actual', x=['SAVI'], y=[v_now], marker_color='green')
                        ])
                        st.plotly_chart(fig, use_container_width=True)
                        st.success("Reporte enviado y Excel alimentado.")

with t2:
    st.subheader("Base de Datos Consolidada (Excel)")
    hist = supabase.table("historial_reportes").select("*").execute().data
    if hist:
        df = pd.DataFrame(hist)
        # Mostrar columnas clave para el usuario
        st.dataframe(df[['created_at', 'proyecto', 'savi_base', 'savi', 'variacion_porcentual', 'motivo_alerta', 'estado']])
        st.download_button("📥 Descargar Reporte para Auditoría (CSV)", df.to_csv(index=False).encode('utf-8'), "BioCore_Auditoria.csv")
