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
import matplotlib.pyplot as plt
import os

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

# --- 2. MOTOR DE REPORTES PDF (ESTRUCTURA SOLICITADA) ---

def crear_pdf_biocore(reporte, proyecto):
    pdf = FPDF()
    pdf.add_page()
    
    # Banner Azul Marino de Auditoría
    pdf.set_fill_color(20, 50, 80)
    pdf.rect(0, 0, 210, 40, 'F')
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("helvetica", "B", 16)
    pdf.cell(0, 20, f"AUDITORIA DE CUMPLIMIENTO AMBIENTAL - {proyecto.upper()}", align="C", ln=1)
    pdf.set_font("helvetica", "I", 10)
    pdf.cell(0, 5, f"Responsable Técnica: Loreto Campos | BioCore Intelligence", align="C", ln=1)
    
    pdf.ln(20)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("helvetica", "B", 12)
    pdf.cell(0, 10, "DIAGNOSTICO TECNICO DE CRIOSFERA Y ALTA MONTAÑA", ln=1)
    
    # Lógica de Umbral para el Estatus
    val_actual = reporte.get('savi', 0)
    ndsi_val = reporte.get('ndwi_ndsi', val_actual) # Ajuste según variable disponible
    
    if ndsi_val < 0.35:
        estado_txt = "ALERTA TECNICA: PERDIDA DE COBERTURA"
        color_resumen = (200, 0, 0)
        diagnostico = (
            f"1. ESTADO DE GLACIARES: El indice actual ({ndsi_val:.2f}) se encuentra bajo el umbral "
            "critico de presencia de hielo/nieve perenne (0.40). Indica una degradacion de la masa criosferica.\n\n"
            "2. RIESGO TECNICO-LEGAL: La ausencia de firma espectral constituye un hallazgo critico. "
            "No permite generar prueba de descargo por estabilidad ante fiscalizacion.\n\n"
            "3. RECOMENDACION: Inspeccion inmediata para descartar acumulacion de material particulado."
        )
    else:
        estado_txt = "BAJO CONTROL: ESTABILIDAD CRIOSFERICA"
        color_resumen = (0, 100, 0)
        diagnostico = (
            f"1. PROTECCION DE GLACIARES: El indice ({ndsi_val:.2f}) confirma la permanencia de "
            "masa de hielo. Blinda al titular ante acusaciones de daño ambiental reciente.\n\n"
            "2. BLINDAJE: El monitoreo indica cumplimiento de los parametros de preservacion de la RCA."
        )

    pdf.set_fill_color(*color_resumen)
    pdf.set_text_color(255, 255, 255); pdf.set_font("helvetica", "B", 10)
    pdf.cell(0, 8, f" ESTATUS: {estado_txt}", ln=1, fill=True)
    
    pdf.ln(5); pdf.set_text_color(0, 0, 0); pdf.set_font("helvetica", "", 9)
    pdf.multi_cell(0, 6, diagnostico, border=1)

    # Firma
    pdf.ln(10)
    pdf.set_font("helvetica", "B", 10); pdf.cell(0, 5, "Loreto Campos", align="C", ln=1)
    pdf.set_font("helvetica", "I", 9); pdf.cell(0, 5, "Directora Tecnica - BioCore Intelligence", align="C", ln=1)

    fname = f"Reporte_{proyecto}_{reporte['id']}.pdf"
    pdf.output(fname)
    return fname

# --- 3. FUNCIONES DE PROCESAMIENTO GEE ---

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

def generar_auditoria_interna(p):
    iniciar_gee()
    js = json.loads(p['Coordenadas'])
    geom = ee.Geometry.Polygon(js['coordinates'] if 'coordinates' in js else js)
    
    s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED').filterBounds(geom).sort('system:time_start', False).first()
    idx = s2.expression('((B8-B4)/(B8+B4+0.5))*1.5', {'B8':s2.select('B8'),'B4':s2.select('B4')}).rename('sa')\
        .addBands(s2.normalizedDifference(['B3','B8']).rename('nd'))\
        .reduceRegion(ee.Reducer.mean(), geom, 30).getInfo()

    temp_img = ee.ImageCollection("MODIS/061/MOD11A1").filterBounds(geom).sort('system:time_start', False).first()
    t_val = temp_img.select('LST_Day_1km').multiply(0.02).subtract(273.15).reduceRegion(ee.Reducer.mean(), geom, 1000).getInfo().get('LST_Day_1km', 0)

    # Registro inicial (Borrador)
    res = supabase.table("historial_reportes").insert({
        "proyecto": p['Proyecto'], "savi": idx['sa'], "ndwi_ndsi": idx['nd'],
        "temp_suelo": t_val, "validado_por_admin": False, "estado": "PENDIENTE"
    }).execute()
    return res

# --- 4. INTERFAZ ---

t1, t2 = st.tabs(["🚀 Vigilancia Activa", "📊 Centro de Revision"])

with t1:
    proyectos = supabase.table("usuarios").select("*").execute().data
    for p in proyectos:
        st.markdown(f"### 📍 Proyecto: {p['Proyecto']}")
        c_map, c_ops = st.columns([2.5, 1])
        with c_map:
            folium_static(dibujar_mapa_biocore(p['Coordenadas']), width=850, height=500)
        with c_ops:
            if st.button(f"🚀 Generar Auditoria", key=f"btn_{p['Proyecto']}"):
                with st.spinner("Procesando satelites..."):
                    generar_auditoria_interna(p)
                    st.success("Borrador listo en pestaña Revision.")

with t2:
    st.subheader("📋 Gestion de Calidad y Envio")
    
    if st.button("🗑️ Limpiar Borradores"):
        supabase.table("historial_reportes").delete().eq("validado_por_admin", False).execute()
        st.rerun()

    pendientes = supabase.table("historial_reportes").select("*").eq("validado_por_admin", False).execute().data
    if pendientes:
        for r in pendientes:
            with st.expander(f"🔍 Revisar: {r['proyecto']} ({r['created_at'][:16]})"):
                st.write(f"**Valor Detectado:** {r['ndwi_ndsi']:.3f} | **Temp:** {r['temp_suelo']:.1f}°C")
                
                c1, c2, c3 = st.columns(3)
                with c1:
                    if st.button("✅ Aprobar y Enviar PDF", key=f"app_{r['id']}"):
                        with st.spinner("Generando PDF Oficial..."):
                            pdf_file = crear_pdf_biocore(r, r['proyecto'])
                            # Envio Telegram Documento
                            with open(pdf_file, "rb") as doc:
                                requests.post(f"https://api.telegram.org/bot{st.secrets['telegram']['token']}/sendDocument",
                                             data={"chat_id": st.secrets['telegram']['chat_id'], "caption": f"🛡️ REPORTE OFICIAL: {r['proyecto']}"},
                                             files={"document": doc})
                            # Validar en DB
                            supabase.table("historial_reportes").update({"validado_por_admin": True, "estado": "ENVIADO"}).eq("id", r['id']).execute()
                            os.remove(pdf_file) # Limpiar archivo temporal
                            st.rerun()
                with c2:
                    st.download_button("📥 Revisar Borrador", pd.DataFrame([r]).to_csv().encode('utf-8'), f"Draft_{r['id']}.csv")
                with c3:
                    if st.button("🗑️ Borrar", key=f"del_{r['id']}"):
                        supabase.table("historial_reportes").delete().eq("id", r['id']).execute()
                        st.rerun()

    st.divider()
    st.markdown("#### 📥 Historial Final (Visible para Cliente)")
    aprobados = supabase.table("historial_reportes").select("*").eq("validado_por_admin", True).execute().data
    if aprobados:
        df = pd.DataFrame(aprobados)
        st.dataframe(df[['created_at', 'proyecto', 'ndwi_ndsi', 'estado']])
        st.download_button("📥 Descargar Historico Completo", df.to_csv(index=False).encode('utf-8'), "BioCore_Final.csv")
