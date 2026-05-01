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

# --- 2. MOTOR DE INFORMES (PDF AZUL + WORD) ---

def generar_documentos(r):
    proyecto = r.get('proyecto', 'Proyecto_BioCore')
    # Limpieza y conversión de datos para evitar TypeErrors
    v_ndsi = float(r.get('ndwi_ndsi') or 0)
    v_radar = float(r.get('radar_vv') or 0)
    v_temp = float(r.get('temp_suelo') or 0)
    
    # Lógica de Estatus
    color = (200, 0, 0) if v_ndsi < 0.35 else (0, 100, 0)
    est = "ALERTA: PERDIDA DE COBERTURA" if v_ndsi < 0.35 else "CONTROL: ESTABILIDAD"
    
    # A. PDF CON BORDE/BANNER AZUL MARINO
    pdf = FPDF()
    pdf.add_page()
    # Banner Azul Superior
    pdf.set_fill_color(20, 50, 80)
    pdf.rect(0, 0, 210, 40, 'F')
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("helvetica", "B", 16)
    pdf.cell(0, 20, f"AUDITORIA AMBIENTAL - {str(proyecto).upper()}", align="C", ln=1)
    pdf.set_font("helvetica", "I", 10)
    pdf.cell(0, 5, "Responsable Tecnica: Loreto Campos | BioCore Intelligence", align="C", ln=1)
    
    pdf.ln(30); pdf.set_text_color(0, 0, 0)
    pdf.set_font("helvetica", "B", 12); pdf.cell(0, 10, "DIAGNOSTICO TECNICO", ln=1)
    
    # Estatus Resaltado
    pdf.set_fill_color(*color); pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 8, f" ESTATUS: {est}", ln=1, fill=True)
    
    pdf.ln(5); pdf.set_text_color(0, 0, 0); pdf.set_font("helvetica", "", 10)
    pdf.multi_cell(0, 7, f"Analisis de Criósfera:\n- Indice NDSI: {v_ndsi:.3f}\n- Radar VV: {v_radar:.2f} dB\n- Temperatura: {v_temp:.1f}C", border=1)
    
    pdf_p = f"Reporte_{proyecto}.pdf"
    pdf.output(pdf_p)

    # B. WORD EDITABLE
    doc = Document()
    doc.add_heading(f"INFORME EDITABLE: {proyecto}", 0)
    doc.add_paragraph(f"Estado Detectado: {est}")
    doc.add_paragraph(f"NDSI: {v_ndsi:.3f} | Radar: {v_radar:.2f}")
    doc_p = f"Reporte_{proyecto}_Editable.docx"
    doc.save(doc_p)
    
    return pdf_p, doc_p

def enviar_a_telegram(pdf_p, doc_p, proyecto):
    token = st.secrets['telegram']['token']
    chat_id = st.secrets['telegram']['chat_id']
    exito = False
    for path in [pdf_p, doc_p]:
        if os.path.exists(path):
            with open(path, "rb") as f:
                resp = requests.post(f"https://api.telegram.org/bot{token}/sendDocument",
                                     data={"chat_id": chat_id, "caption": f"🛡️ BioCore: {proyecto}"},
                                     files={"document": f})
                if resp.status_code == 200: exito = True
    return exito

# --- 3. ANALISIS ESPACIAL BLINDADO ---

def extraer_geom_segura(p):
    try:
        js = json.loads(p['Coordenadas']) if isinstance(p['Coordenadas'], str) else p['Coordenadas']
        if isinstance(js, dict) and 'coordinates' in js:
            return ee.Geometry.Polygon(js['coordinates'])
        return ee.Geometry.Polygon(js)
    except: return None

def ejecutar_auditoria_completa(p):
    iniciar_gee()
    geom = extraer_geom_segura(p)
    if not geom: return st.error("Error en formato de coordenadas.")

    # S2 y S1
    s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED').filterBounds(geom).sort('CLOUDY_PIXEL_PERCENTAGE').first()
    ndsi = s2.normalizedDifference(['B3','B11']).reduceRegion(ee.Reducer.mean(), geom, 30).getInfo().get('nd', 0)
    
    s1 = ee.ImageCollection('COPERNICUS/S1_GRD').filterBounds(geom).filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV')).first()
    radar = s1.select('VV').reduceRegion(ee.Reducer.mean(), geom, 30).getInfo().get('VV', 0)

    supabase.table("historial_reportes").insert({
        "proyecto": p['Proyecto'], "ndwi_ndsi": ndsi, "radar_vv": radar, 
        "validado_por_admin": False, "estado": "PENDIENTE"
    }).execute()

# --- 4. INTERFAZ ---

t1, t2 = st.tabs(["🚀 Vigilancia", "📊 Centro de Revision"])

with t1:
    proyectos = supabase.table("usuarios").select("*").execute().data
    for p in proyectos:
        st.markdown(f"### 📍 {p['Proyecto']}")
        if st.button(f"Iniciar Auditoria", key=f"g_{p['Proyecto']}"):
            with st.spinner("Analizando..."):
                ejecutar_auditoria_completa(p)
                st.success("Borrador listo.")

with t2:
    pendientes = supabase.table("historial_reportes").select("*").eq("validado_por_admin", False).execute().data
    if pendientes:
        for r in pendientes:
            with st.expander(f"Revision: {r['proyecto']}"):
                c1, c2, c3 = st.columns(3)
                with c1:
                    if st.button("🚀 Enviar Oficial", key=f"env_{r['id']}", type="primary"):
                        pdf, doc = generar_documentos(r)
                        if enviar_a_telegram(pdf, doc, r['proyecto']):
                            supabase.table("historial_reportes").update({"validado_por_admin": True, "estado": "ENVIADO"}).eq("id", r['id']).execute()
                            st.success("Enviado a Telegram"); st.rerun()
                with c2:
                    if st.button("📩 Reenvio Manual", key=f"man_{r['id']}"):
                        pdf, doc = generar_documentos(r)
                        enviar_a_telegram(pdf, doc, r['proyecto'])
                        st.info("Copia enviada.")
                with c3:
                    if st.button("🗑️ Borrar", key=f"del_{r['id']}"):
                        supabase.table("historial_reportes").delete().eq("id", r['id']).execute(); st.rerun()
