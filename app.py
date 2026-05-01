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
from fpdf import FPDF
import os

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

# --- 2. MOTOR PDF PROFESIONAL ---
def crear_pdf_biocore(r, proyecto):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_fill_color(20, 50, 80)
    pdf.rect(0, 0, 210, 40, 'F')
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("helvetica", "B", 16)
    pdf.cell(0, 20, f"AUDITORIA DE CUMPLIMIENTO AMBIENTAL - {proyecto.upper()}", align="C", ln=1)
    pdf.set_font("helvetica", "I", 10)
    pdf.cell(0, 5, "Responsable Tecnica: Loreto Campos | BioCore Intelligence", align="C", ln=1)
    
    pdf.ln(20); pdf.set_text_color(0, 0, 0); pdf.set_font("helvetica", "B", 12)
    pdf.cell(0, 10, "DIAGNOSTICO TECNICO DE CRIOSFERA Y ALTA MONTAÑA", ln=1)
    
    val_ndsi = r.get('ndwi_ndsi', 0) if r.get('ndwi_ndsi') is not None else 0
    
    if val_ndsi < 0.35:
        est, col, diag = "ALERTA: PERDIDA DE COBERTURA", (200, 0, 0), "Hallazgo critico: No permite prueba de descargo legal."
    else:
        est, col, diag = "BAJO CONTROL: ESTABILIDAD", (0, 100, 0), "Blindaje: Cumplimiento de parametros RCA."

    pdf.set_fill_color(*col); pdf.set_text_color(255, 255, 255); pdf.set_font("helvetica", "B", 10)
    pdf.cell(0, 8, f" ESTATUS: {est}", ln=1, fill=True)
    pdf.ln(5); pdf.set_text_color(0, 0, 0); pdf.set_font("helvetica", "", 9)
    pdf.multi_cell(0, 6, f"Indice Detectado: {val_ndsi:.3f}\n\n{diag}", border=1)
    
    pdf.ln(10); pdf.set_font("helvetica", "B", 10); pdf.cell(0, 5, "Loreto Campos", align="C", ln=1)
    pdf.set_font("helvetica", "I", 9); pdf.cell(0, 5, "Directora Tecnica - BioCore Intelligence", align="C", ln=1)

    fname = f"Reporte_{proyecto}_{r['id']}.pdf"
    pdf.output(fname)
    return fname

# --- 3. FUNCIONES GEE (ÓPTICO + RADAR S1) ---
def dibujar_mapa_biocore(coords_json):
    try:
        js = json.loads(coords_json)
        raw = js['coordinates'][0] if 'coordinates' in js else js
        puntos = [[float(p[1]), float(p[0])] for p in raw]
        m = folium.Map(location=puntos[0], zoom_start=15, tiles='https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}', attr='Google Hybrid')
        folium.Polygon(locations=puntos, color="#FFFF00", weight=3, fill=True, fill_opacity=0.1).add_to(m)
        m.fit_bounds(puntos)
        return m
    except: return folium.Map(location=[-37.2, -72.7], zoom_start=12)

def ejecutar_auditoria_dual(p):
    iniciar_gee()
    js = json.loads(p['Coordenadas'])
    geom = ee.Geometry.Polygon(js['coordinates'] if 'coordinates' in js else js)
    
    # 1. Óptico (S2)
    s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED').filterBounds(geom).sort('system:time_start', False).first()
    idx = s2.expression('((B8-B4)/(B8+B4+0.5))*1.5', {'B8':s2.select('B8'),'B4':s2.select('B4')}).rename('sa')\
            .addBands(s2.normalizedDifference(['B3','B11']).rename('ndsi'))\
            .reduceRegion(ee.Reducer.mean(), geom, 30).getInfo()

    # 2. Radar (S1) - Para atravesar nubes
    s1 = ee.ImageCollection('COPERNICUS/S1_GRD').filterBounds(geom).filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV')).sort('system:time_start', False).first()
    radar_vv = s1.select('VV').reduceRegion(ee.Reducer.mean(), geom, 30).getInfo().get('VV', 0)

    # 3. Temperatura
    temp_img = ee.ImageCollection("MODIS/061/MOD11A1").filterBounds(geom).sort('system:time_start', False).first()
    t_val = temp_img.select('LST_Day_1km').multiply(0.02).subtract(273.15).reduceRegion(ee.Reducer.mean(), geom, 1000).getInfo().get('LST_Day_1km', 0)

    # Registro en Supabase
    supabase.table("historial_reportes").insert({
        "proyecto": p['Proyecto'], "savi": idx.get('sa', 0), "ndwi_ndsi": idx.get('ndsi', 0),
        "temp_suelo": t_val, "radar_vv": radar_vv, "validado_por_admin": False, "estado": "BORRADOR"
    }).execute()

# --- 4. INTERFAZ ---
tab1, tab2 = st.tabs(["🚀 Vigilancia Activa", "📊 Centro de Revision"])

with tab1:
    proyectos = supabase.table("usuarios").select("*").execute().data
    for p in proyectos:
        st.markdown(f"### 📍 {p['Proyecto']}")
        c1, c2 = st.columns([3, 1])
        with c1: folium_static(dibujar_mapa_biocore(p['Coordenadas']), width=900, height=500)
        with c2:
            if st.button("🚀 Iniciar Auditoria Dual", key=f"gen_{p['Proyecto']}", use_container_width=True):
                with st.spinner("Procesando Optico + Radar..."):
                    ejecutar_auditoria_dual(p)
                    st.success("Borrador generado.")

with tab2:
    st.subheader("📋 Gestion de Calidad")
    if st.button("🗑️ Limpiar Borradores"):
        supabase.table("historial_reportes").delete().eq("validado_por_admin", False).execute()
        st.rerun()

    pendientes = supabase.table("historial_reportes").select("*").eq("validado_por_admin", False).execute().data
    if pendientes:
        for r in pendientes:
            # Proteccion contra Nulos
            v_ndsi = r.get('ndwi_ndsi') if r.get('ndwi_ndsi') is not None else 0
            v_radar = r.get('radar_vv') if r.get('radar_vv') is not None else 0
            v_temp = r.get('temp_suelo') if r.get('temp_suelo') is not None else 0
            
            with st.expander(f"🔍 Revisar: {r['proyecto']} ({r['created_at'][:16]})"):
                st.write(f"**NDSI:** {v_ndsi:.3f} | **Radar VV:** {v_radar:.2f} dB | **Temp:** {v_temp:.1f}°C")
                c_a, c_b, c_c = st.columns(3)
                with c_a:
                    if st.button("✅ Enviar PDF Oficial", key=f"send_{r['id']}", type="primary"):
                        f = crear_pdf_biocore(r, r['proyecto'])
                        with open(f, "rb") as d:
                            requests.post(f"https://api.telegram.org/bot{st.secrets['telegram']['token']}/sendDocument",
                                         data={"chat_id": st.secrets['telegram']['chat_id'], "caption": f"🛡️ REPORTE BIOCORE: {r['proyecto']}"},
                                         files={"document": d})
                        supabase.table("historial_reportes").update({"validado_por_admin": True, "estado": "ENVIADO"}).eq("id", r['id']).execute()
                        os.remove(f); st.rerun()
                with c_b: st.download_button("📥 Excel", pd.DataFrame([r]).to_csv().encode('utf-8'), f"Draft_{r['id']}.csv")
                with c_c:
                    if st.button("🗑️ Borrar", key=f"del_{r['id']}"):
                        supabase.table("historial_reportes").delete().eq("id", r['id']).execute(); st.rerun()

    st.divider()
    st.markdown("#### 📥 Historial Final")
    aprobados = supabase.table("historial_reportes").select("*").eq("validado_por_admin", True).execute().data
    if aprobados:
        df = pd.DataFrame(aprobados)
        st.dataframe(df[['created_at', 'proyecto', 'ndwi_ndsi', 'radar_vv', 'estado']])
        st.download_button("📥 Descargar Todo", df.to_csv(index=False).encode('utf-8'), "BioCore_Final.csv")
