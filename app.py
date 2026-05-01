import streamlit as st
import ee
import folium
from streamlit_folium import folium_static
import json
import pandas as pd
import requests
from datetime import datetime
from fpdf import FPDF
from docx import Document
import os
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

# --- 2. MOTOR DE DOCUMENTOS (PDF + WORD) ---

def generar_documentos(r):
    proyecto = r.get('proyecto', 'Proyecto_BioCore')
    # Protección contra Nulos (None)
    v_ndsi = float(r.get('ndwi_ndsi') or 0)
    v_radar = float(r.get('radar_vv') or 0)
    v_temp = float(r.get('temp_suelo') or 0)
    v_savi = float(r.get('savi') or 0)
    
    # Lógica de Diagnóstico
    color = (200, 0, 0) if v_ndsi < 0.35 else (0, 100, 0)
    est = "ALERTA: PERDIDA DE COBERTURA" if v_ndsi < 0.35 else "CONTROL: ESTABILIDAD"
    diag_txt = (f"Indice NDSI ({v_ndsi:.3f}) bajo umbral critico. Riesgo de degradacion detectado." 
                if v_ndsi < 0.35 else f"Indice NDSI ({v_ndsi:.3f}) estable. Blindaje RCA vigente.")

    # A. PDF PROFESIONAL
    pdf = FPDF()
    pdf.add_page()
    pdf.set_fill_color(20, 50, 80)
    pdf.rect(0, 0, 210, 40, 'F')
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("helvetica", "B", 16)
    pdf.cell(0, 20, f"AUDITORIA AMBIENTAL - {str(proyecto).upper()}", align="C", ln=1)
    pdf.set_font("helvetica", "I", 10)
    pdf.cell(0, 5, "Responsable Tecnica: Loreto Campos | BioCore Intelligence", align="C", ln=1)
    
    pdf.ln(25); pdf.set_text_color(0, 0, 0); pdf.set_font("helvetica", "B", 12)
    pdf.cell(0, 10, "DIAGNOSTICO TECNICO DE ALTA MONTAÑA", ln=1)
    
    pdf.set_fill_color(*color); pdf.set_text_color(255, 255, 255); pdf.set_font("helvetica", "B", 10)
    pdf.cell(0, 8, f" ESTATUS: {est}", ln=1, fill=True)
    
    pdf.ln(5); pdf.set_text_color(0, 0, 0); pdf.set_font("helvetica", "", 10)
    pdf.multi_cell(0, 7, f"{diag_txt}\n\nDatos:\n- Radar VV: {v_radar:.2f} dB\n- Temp: {v_temp:.1f}C", border=1)
    
    pdf_p = f"Reporte_{proyecto}.pdf"
    pdf.output(pdf_p)

    # B. WORD EDITABLE
    doc = Document()
    doc.add_heading(f"AUDITORIA: {proyecto}", 0)
    doc.add_paragraph(f"Responsable Tecnica: Loreto Campos")
    doc.add_heading("Diagnostico", level=1)
    p = doc.add_paragraph(); p.add_run(f"ESTADO: {est}").bold = True
    doc.add_paragraph(diag_txt)
    doc_p = f"Reporte_{proyecto}_Editable.docx"
    doc.save(doc_p)
    
    return pdf_p, doc_p

def enviar_a_telegram(pdf_p, doc_p, proyecto):
    token = st.secrets['telegram']['token']
    chat_id = st.secrets['telegram']['chat_id']
    for path in [pdf_p, doc_p]:
        if os.path.exists(path):
            with open(path, "rb") as f:
                requests.post(f"https://api.telegram.org/bot{token}/sendDocument",
                             data={"chat_id": chat_id, "caption": f"🛡️ BioCore: {proyecto}"},
                             files={"document": f})

# --- 3. FUNCIONES DE GEOMETRÍA Y ANÁLISIS ---

def extraer_geometria(p):
    """Extrae la geometría de forma segura independientemente del formato JSON"""
    try:
        coords_raw = p['Coordenadas']
        js = json.loads(coords_raw) if isinstance(coords_raw, str) else coords_raw
        # Maneja formatos GeoJSON {'type': 'Polygon', 'coordinates': [...]} o solo la lista
        if isinstance(js, dict) and 'coordinates' in js:
            return ee.Geometry.Polygon(js['coordinates'])
        return ee.Geometry.Polygon(js)
    except Exception as e:
        st.error(f"Error en formato de coordenadas para {p['Proyecto']}: {e}")
        return None

def ejecutar_auditoria_dual(p):
    iniciar_gee()
    geom = extraer_geometria(p)
    if not geom: return

    # S2 Óptico
    s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED').filterBounds(geom).sort('CLOUDY_PIXEL_PERCENTAGE').first()
    ndsi = s2.normalizedDifference(['B3','B11']).reduceRegion(ee.Reducer.mean(), geom, 30).getInfo().get('nd', 0)
    
    # S1 Radar
    s1 = ee.ImageCollection('COPERNICUS/S1_GRD').filterBounds(geom).filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV')).first()
    radar = s1.select('VV').reduceRegion(ee.Reducer.mean(), geom, 30).getInfo().get('VV', 0)
    
    # MODIS Temp
    temp = ee.ImageCollection("MODIS/061/MOD11A1").filterBounds(geom).sort('system:time_start', False).first()\
           .select('LST_Day_1km').multiply(0.02).subtract(273.15).reduceRegion(ee.Reducer.mean(), geom, 1000).getInfo().get('LST_Day_1km', 0)

    supabase.table("historial_reportes").insert({
        "proyecto": p['Proyecto'], "ndwi_ndsi": ndsi, "radar_vv": radar, 
        "temp_suelo": temp, "validado_por_admin": False, "estado": "BORRADOR"
    }).execute()

# --- 4. INTERFAZ ---

t1, t2 = st.tabs(["🚀 Vigilancia Activa", "📊 Centro de Revision"])

with t1:
    proyectos = supabase.table("usuarios").select("*").execute().data
    for p in proyectos:
        st.markdown(f"### 📍 {p['Proyecto']}")
        c_m, c_o = st.columns([3, 1])
        with c_o:
            if st.button(f"Iniciar Auditoria", key=f"g_{p['Proyecto']}"):
                with st.spinner("Analizando satelites..."):
                    ejecutar_auditoria_dual(p)
                    st.success("Borrador generado.")

with t2:
    st.subheader("📋 Gestion de Calidad")
    pendientes = supabase.table("historial_reportes").select("*").eq("validado_por_admin", False).execute().data
    if pendientes:
        for r in pendientes:
            v_ndsi = float(r.get('ndwi_ndsi') or 0)
            v_radar = float(r.get('radar_vv') or 0)
            
            with st.expander(f"Revision: {r['proyecto']} ({r['created_at'][:16]})"):
                st.write(f"NDSI: {v_ndsi:.3f} | Radar: {v_radar:.2f}")
                c_env, c_man, c_del = st.columns(3)
                
                with c_env:
                    if st.button("🚀 Enviar Pack Oficial", key=f"env_{r['id']}", type="primary"):
                        pdf, doc = generar_documentos(r)
                        enviar_a_telegram(pdf, doc, r['proyecto'])
                        supabase.table("historial_reportes").update({"validado_por_admin": True, "estado": "ENVIADO"}).eq("id", r['id']).execute()
                        st.rerun()
                
                with c_man:
                    if st.button("📩 Reenvio Manual", key=f"man_{r['id']}"):
                        pdf, doc = generar_documentos(r)
                        enviar_a_telegram(pdf, doc, r['proyecto'])
                        st.info("Reenviado.")

                with c_del:
                    if st.button("🗑️ Borrar", key=f"del_{r['id']}"):
                        supabase.table("historial_reportes").delete().eq("id", r['id']).execute(); st.rerun()
