import streamlit as st
import ee
import folium
from streamlit_folium import folium_static
import json
import pandas as pd
import requests
from datetime import datetime, timedelta
from fpdf import FPDF
from docx import Document
import os
from supabase import create_client, Client

# --- 1. CONFIGURACIÓN E INICIALIZACIÓN ---
st.set_page_config(page_title="BioCore Intelligence V5.1", layout="wide")

@st.cache_resource
def init_db():
    return create_client(st.secrets["connections"]["supabase"]["url"], st.secrets["connections"]["supabase"]["key"])

supabase = init_db()

def iniciar_gee():
    if not ee.data.is_initialized():
        creds = json.loads(st.secrets["gee"]["json"])
        ee_creds = ee.ServiceAccountCredentials(creds['client_email'], key_data=creds['private_key'])
        ee.Initialize(ee_creds)

# --- 2. MOTOR DE INFORMES (CON VISTA PREVIA) ---

def generar_documentos(r):
    proyecto = r.get('proyecto', 'Proyecto_BioCore')
    v_ndsi = float(r.get('ndwi_ndsi') or 0)
    v_radar = float(r.get('radar_vv') or 0)
    
    color = (200, 0, 0) if v_ndsi < 0.35 else (0, 100, 0)
    est = "ALERTA: PERDIDA DE COBERTURA" if v_ndsi < 0.35 else "CONTROL: ESTABILIDAD"

    # PDF con estética pericial (Borde Azul)
    pdf = FPDF()
    pdf.add_page()
    pdf.set_fill_color(20, 50, 80)
    pdf.rect(0, 0, 210, 40, 'F')
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("helvetica", "B", 16)
    pdf.cell(0, 20, f"AUDITORIA AMBIENTAL - {str(proyecto).upper()}", align="C", ln=1)
    
    pdf.ln(30); pdf.set_text_color(0, 0, 0)
    pdf.set_font("helvetica", "B", 12); pdf.cell(0, 10, "DIAGNOSTICO TECNICO", ln=1)
    pdf.set_fill_color(*color); pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 8, f" ESTATUS: {est}", ln=1, fill=True)
    
    pdf_p = f"Reporte_{proyecto}.pdf"
    pdf.output(pdf_p)

    # WORD Editable
    doc = Document()
    doc.add_heading(f"INFORME EDITABLE: {proyecto}", 0)
    doc.add_paragraph(f"NDSI: {v_ndsi:.3f} | Radar: {v_radar:.2f}")
    doc_p = f"Reporte_{proyecto}_Editable.docx"
    doc.save(doc_p)
    
    return pdf_p, doc_p

# --- 3. ANÁLISIS SATELITAL POR RANGO DE FECHAS ---

def ejecutar_auditoria_rango(p, fecha_inicio, fecha_fin):
    iniciar_gee()
    try:
        js = json.loads(p['Coordenadas']) if isinstance(p['Coordenadas'], str) else p['Coordenadas']
        geom = ee.Geometry.Polygon(js['coordinates'] if isinstance(js, dict) and 'coordinates' in js else js)

        # Filtrar por el rango elegido por el usuario
        s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')\
               .filterBounds(geom)\
               .filterDate(fecha_inicio.strftime('%Y-%m-%d'), fecha_fin.strftime('%Y-%m-%d'))\
               .sort('CLOUDY_PIXEL_PERCENTAGE').first()
        
        if not s2.getInfo():
            st.warning(f"No hay imágenes despejadas para {p['Proyecto']} en ese rango.")
            return

        ndsi = s2.normalizedDifference(['B3','B11']).reduceRegion(ee.Reducer.mean(), geom, 30).getInfo().get('nd', 0)
        
        s1 = ee.ImageCollection('COPERNICUS/S1_GRD').filterBounds(geom)\
               .filterDate(fecha_inicio.strftime('%Y-%m-%d'), fecha_fin.strftime('%Y-%m-%d'))\
               .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV')).first()
        radar = s1.select('VV').reduceRegion(ee.Reducer.mean(), geom, 30).getInfo().get('VV', 0)

        supabase.table("historial_reportes").insert({
            "proyecto": p['Proyecto'], "ndwi_ndsi": ndsi, "radar_vv": radar, 
            "validado_por_admin": False, "estado": "BORRADOR"
        }).execute()
        st.success(f"Análisis completado para el periodo seleccionado.")
    except Exception as e:
        st.error(f"Error: {e}")

# --- 4. INTERFAZ MEJORADA ---

t1, t2 = st.tabs(["🚀 Vigilancia Activa", "📊 Centro de Revision"])

with t1:
    proyectos = supabase.table("usuarios").select("*").execute().data
    
    # NUEVO: Selector de Rango Global
    st.sidebar.header("Configuración de Análisis")
    rango = st.sidebar.date_input("Selecciona rango de análisis", [datetime.now() - timedelta(days=7), datetime.now()])
    
    for p in proyectos:
        with st.container(border=True):
            st.markdown(f"### 📍 {p['Proyecto']}")
            c_map, c_btn = st.columns([2, 1])
            with c_btn:
                if st.button(f"Ejecutar periodo seleccionado", key=f"run_{p['Proyecto']}"):
                    if len(rango) == 2:
                        ejecutar_auditoria_rango(p, rango[0], rango[1])
                    else:
                        st.error("Selecciona fecha inicio y fin.")

with t2:
    st.subheader("📋 Revisión y Vista Previa")
    pendientes = supabase.table("historial_reportes").select("*").eq("validado_por_admin", False).execute().data
    
    if pendientes:
        for r in pendientes:
            with st.expander(f"REVISAR: {r['proyecto']} ({r['created_at'][:10]})"):
                # VISTA PREVIA DE DATOS
                col1, col2 = st.columns(2)
                col1.metric("NDSI (Nieve/Hielo)", f"{float(r['ndwi_ndsi'] or 0):.3f}")
                col2.metric("Radar VV", f"{float(r['radar_vv'] or 0):.2f} dB")
                
                c_env, c_man, c_del = st.columns(3)
                with c_env:
                    if st.button("🚀 Enviar Oficial", key=f"env_{r['id']}", type="primary"):
                        pdf, doc = generar_documentos(r)
                        # Envío a Telegram
                        files = [('document', open(pdf, 'rb')), ('document', open(doc, 'rb'))]
                        requests.post(f"https://api.telegram.org/bot{st.secrets['telegram']['token']}/sendMultipleDocuments", 
                                      data={"chat_id": st.secrets['telegram']['chat_id']}, files=files)
                        
                        supabase.table("historial_reportes").update({"validado_por_admin": True}).eq("id", r['id']).execute()
                        st.rerun()
                
                with c_man:
                    # Vista previa antes de enviar
                    if st.button("👀 Generar Vista Previa", key=f"pre_{r['id']}"):
                        pdf, doc = generar_documentos(r)
                        with open(pdf, "rb") as f:
                            st.download_button("📥 Descargar PDF para revisar", f, file_name=pdf)
