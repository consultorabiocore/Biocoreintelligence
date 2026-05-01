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

# --- 2. FUNCIONES DE PROCESAMIENTO ---

def dibujar_mapa_biocore(coords_json):
    try:
        js = json.loads(coords_json) if isinstance(coords_json, str) else coords_json
        raw = js['coordinates'][0] if 'coordinates' in js else js
        puntos = [[float(p[1]), float(p[0])] for p in raw]
        m = folium.Map(location=puntos[0], zoom_start=15, 
                       tiles='https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}', 
                       attr='Google Satellite Hybrid')
        folium.Polygon(locations=puntos, color="#FFFF00", weight=4, fill=True, fill_opacity=0.2).add_to(m)
        m.fit_bounds(puntos)
        return m
    except:
        return folium.Map(location=[-37.2, -72.7], zoom_start=12)

def generar_reporte_total(p):
    iniciar_gee()
    js = json.loads(p['Coordenadas'])
    geom = ee.Geometry.Polygon(js['coordinates'] if 'coordinates' in js else js)
    
    # Datos Actuales
    s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED').filterBounds(geom).sort('system:time_start', False).first()
    f_rep = datetime.fromtimestamp(s2.get('system:time_start').getInfo()/1000).strftime('%d/%m/%Y')
    
    idx = s2.expression('((B8-B4)/(B8+B4+0.5))*1.5', {'B8':s2.select('B8'),'B4':s2.select('B4')}).rename('sa')\
        .addBands(s2.normalizedDifference(['B3','B8']).rename('nd'))\
        .addBands(s2.select('B11').divide(10000).rename('sw'))\
        .addBands(s2.select('B11').divide(s2.select('B12')).rename('clay'))\
        .reduceRegion(ee.Reducer.mean(), geom, 30).getInfo()

    # Temperatura e Incendios
    temp_img = ee.ImageCollection("MODIS/061/MOD11A1").filterBounds(geom).sort('system:time_start', False).first()
    t_val = temp_img.select('LST_Day_1km').multiply(0.02).subtract(273.15).reduceRegion(ee.Reducer.mean(), geom, 1000).getInfo().get('LST_Day_1km', 0)
    focos = ee.ImageCollection("FIRMS").filterBounds(geom).filterDate(ee.Date(datetime.now()).advance(-3, 'day')).size().getInfo()

    # Línea de Base
    anio_b = p.get('anio_linea_base', 2017)
    s2_b = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED').filterBounds(geom)\
             .filterDate(f"{anio_b}-01-01", f"{anio_b}-12-31").sort('CLOUDY_PIXEL_PERCENTAGE').first()
    s_base = s2_b.expression('((B8-B4)/(B8+B4+0.5))*1.5', {'B8':s2_b.select('B8'),'B4':s2_b.select('B4')})\
                 .reduceRegion(ee.Reducer.mean(), geom, 30).getInfo().get('constant', 0)

    variacion = ((idx['sa'] / s_base) - 1) * 100 if s_base > 0 else 0
    est_global = "🔴 ALERTA" if (focos > 0 or variacion < -15) else "🟢 BAJO CONTROL"
    diag = f"Variación del {variacion:.1f}% respecto a {anio_b}."

    # Guardar en Borrador
    supabase.table("historial_reportes").insert({
        "proyecto": p['Proyecto'], "savi": idx['sa'], "savi_base": s_base,
        "variacion_porcentual": round(variacion, 2), "temp_suelo": t_val, 
        "estado": est_global, "validado_por_admin": False, "motivo_alerta": diag
    }).execute()

    return f_rep, idx['sa'], s_base, est_global, t_val, focos, diag

# --- 3. INTERFAZ ---

if 'PERFILES' not in st.session_state:
    st.session_state.PERFILES = {
        "MINERIA": {"cat": "F-30 Minería", "ve7": "Estabilidad sustrato.", "clima": "Control aridez."},
        "GLACIAR": {"cat": "RCA Criosfera", "ve7": "Protección hídrica.", "clima": "Vigilancia albedo."}
    }

t1, t2 = st.tabs(["🚀 Vigilancia Activa", "📊 Centro de Revisión"])

with t1:
    proyectos = supabase.table("usuarios").select("*").execute().data
    for p in proyectos:
        st.markdown(f"### 📍 Proyecto: {p['Proyecto']}")
        c_map, c_ops = st.columns([2.5, 1])
        with c_map:
            folium_static(dibujar_mapa_biocore(p['Coordenadas']), width=850, height=500)
        with c_ops:
            if st.button("🚀 Generar Informe", key=f"gen_{p['Proyecto']}", use_container_width=True):
                with st.spinner("Analizando..."):
                    generar_reporte_total(p)
                    st.success("Borrador creado en Pestaña 2")

with t2:
    st.subheader("📋 Control de Calidad")
    
    # Botón para limpiar duplicados rápidamente
    if st.button("🗑️ Limpiar todos los borradores"):
        supabase.table("historial_reportes").delete().eq("validado_por_admin", False).execute()
        st.rerun()

    pendientes = supabase.table("historial_reportes").select("*").eq("validado_por_admin", False).execute().data
    if pendientes:
        for report in pendientes:
            with st.expander(f"🔍 Revisar: {report['proyecto']} ({report['created_at'][:16]})"):
                st.write(f"**SAVI:** {report['savi']} | **Base:** {report['savi_base']}")
                st.write(f"**Temp:** {report['temp_suelo']}°C | **Variación:** {report['variacion_porcentual']}%")
                
                c1, c2, c3 = st.columns(3)
                with c1:
                    st.download_button("📥 Bajar para revisar", pd.DataFrame([report]).to_csv().encode('utf-8'), f"Review_{report['id']}.csv")
                with c2:
                    if st.button("🚀 Enviar Cliente", key=f"app_{report['id']}", type="primary"):
                        supabase.table("historial_reportes").update({"validado_por_admin": True}).eq("id", report['id']).execute()
                        # Aquí puedes añadir el requests.post de Telegram si deseas que se envíe al aprobar
                        st.rerun()
                with c3:
                    if st.button("🗑️ Borrar", key=f"del_{report['id']}"):
                        supabase.table("historial_reportes").delete().eq("id", report['id']).execute()
                        st.rerun()

    st.divider()
    st.markdown("#### 📥 Historial Final (Visible para Cliente)")
    aprobados = supabase.table("historial_reportes").select("*").eq("validado_por_admin", True).execute().data
    if aprobados:
        df = pd.DataFrame(aprobados)
        st.dataframe(df[['created_at', 'proyecto', 'savi', 'estado']])
        st.download_button("📥 Descargar Historial Excel", df.to_csv(index=False).encode('utf-8'), "BioCore_Final.csv", use_container_width=True)
