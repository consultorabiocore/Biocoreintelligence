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
    proyecto = r.get('proyecto', 'Proyecto')
    # Protección contra datos vacíos
    v_ndsi = r.get('ndwi_ndsi') if r.get('ndwi_ndsi') is not None else 0
    v_radar = r.get('radar_vv') if r.get('radar_vv') is not None else 0
    v_temp = r.get('temp_suelo') if r.get('temp_suelo') is not None else 0
    
    # Lógica de Diagnóstico
    color = (200, 0, 0) if v_ndsi < 0.35 else (0, 100, 0)
    est = "ALERTA: PERDIDA DE COBERTURA" if v_ndsi < 0.35 else "CONTROL: ESTABILIDAD"
    diag_txt = (f"Indice NDSI ({v_ndsi:.3f}) bajo umbral critico. Riesgo de exposicion de suelo." 
                if v_ndsi < 0.35 else f"Indice NDSI ({v_ndsi:.3f}) estable. Blindaje RCA vigente.")

    # A. GENERAR PDF PROFESIONAL
    pdf = FPDF()
    pdf.add_page()
    pdf.set_fill_color(20, 50, 80) # Azul BioCore
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
    pdf.multi_cell(0, 7, f"{diag_txt}\n\nDatos de respaldo:\n- Radar VV: {v_radar:.2f} dB\n- Temperatura: {v_temp:.1f}C", border=1)
    
    pdf_path = f"Reporte_{proyecto}.pdf"
    pdf.output(pdf_path)

    # B. GENERAR WORD EDITABLE
    doc = Document()
    doc.add_heading(f"AUDITORIA AMBIENTAL: {proyecto}", 0)
    doc.add_paragraph(f"Responsable Tecnica: Loreto Campos")
    doc.add_heading("Diagnostico", level=1)
    p = doc.add_paragraph(); p.add_run(f"ESTADO: {est}").bold = True
    doc.add_paragraph(diag_txt)
    doc_path = f"Reporte_{proyecto}_Editable.docx"
    doc.save(doc_path)
    
    return pdf_path, doc_path

def enviar_a_telegram(pdf_p, doc_p, proyecto):
    token = st.secrets['telegram']['token']
    chat_id = st.secrets['telegram']['chat_id']
    for f_path in [pdf_p, doc_p]:
        with open(f_path, "rb") as f:
            requests.post(f"https://api.telegram.org/bot{token}/sendDocument",
                         data={"chat_id": chat_id, "caption": f"🛡️ BioCore: {proyecto}"},
                         files={"document": f})

# --- 3. FUNCIONES ESPACIALES (ÓPTICO + RADAR) ---

def dibujar_mapa(coords):
    js = json.loads(coords)
    pts = js['coordinates'][0] if 'coordinates' in js else js
    loc = [[float(p[1]), float(p[0])] for p in pts]
    m = folium.Map(location=loc[0], zoom_start=15, tiles='https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}', attr='Google')
    folium.Polygon(loc, color="yellow", fill=True, fill_opacity=0.1).add_to(m)
    return m

def ejecutar_auditoria(p):
    iniciar_gee()
    geom = ee.Geometry.Polygon(json.loads(p['Coordenadas'])['coordinates'])
    
    # Óptico (S2)
    s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED').filterBounds(geom).sort('CLOUDY_PIXEL_PERCENTAGE').first()
    ndsi = s2.normalizedDifference(['B3','B11']).reduceRegion(ee.Reducer.mean(), geom, 30).getInfo().get('nd', 0)
    
    # Radar (S1)
    s1 = ee.ImageCollection('COPERNICUS/S1_GRD').filterBounds(geom).filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV')).first()
    radar = s1.select('VV').reduceRegion(ee.Reducer.mean(), geom, 30).getInfo().get('VV', 0)
    
    supabase.table("historial_reportes").insert({
        "proyecto": p['Proyecto'], "ndwi_ndsi": ndsi, "radar_vv": radar, 
        "validado_por_admin": False, "estado": "BORRADOR"
    }).execute()

# --- 4. INTERFAZ ---

t1, t2 = st.tabs(["🚀 Vigilancia Activa", "📊 Centro de Revision"])

with t1:
    proyectos = supabase.table("usuarios").select("*").execute().data
    for p in proyectos:
        st.markdown(f"### 📍 {p['Proyecto']}")
        c_m, c_o = st.columns([3, 1])
        with c_m: folium_static(dibujar_mapa(p['Coordenadas']), width=900, height=450)
        with c_o:
            if st.button(f"Generar Auditoria", key=f"g_{p['Proyecto']}"):
                with st.spinner("Analizando..."):
                    ejecutar_auditoria(p)
                    st.success("Borrador listo.")

with t2:
    st.subheader("📋 Gestion y Envio de Pack")
    if st.button("🗑️ Limpiar Borradores"):
        supabase.table("historial_reportes").delete().eq("validado_por_admin", False).execute()
        st.rerun()

    pendientes = supabase.table("historial_reportes").select("*").eq("validado_por_admin", False).execute().data
    if pendientes:
        for r in pendientes:
            with st.expander(f"Revision: {r['proyecto']} ({r['created_at'][:16]})"):
                st.write(f"NDSI: {r.get('ndwi_ndsi', 0):.3f} | Radar: {r.get('radar_vv', 0):.2f}")
                
                c_env, c_man, c_del = st.columns(3)
                with c_env:
                    if st.button("🚀 Enviar Pack Oficial", key=f"env_{r['id']}", type="primary"):
                        pdf, doc = generar_documentos(r)
                        enviar_a_telegram(pdf, doc, r['proyecto'])
                        supabase.table("historial_reportes").update({"validado_por_admin": True, "estado": "ENVIADO"}).eq("id", r['id']).execute()
                        os.remove(pdf); os.remove(doc)
                        st.success("Enviado."); st.rerun()
                
                with c_man:
                    if st.button("📩 Reenvio Manual", key=f"man_{r['id']}"):
                        pdf, doc = generar_documentos(r)
                        enviar_a_telegram(pdf, doc, r['proyecto'])
                        st.info("Reenviado a Telegram.")

                with c_del:
                    if st.button("🗑️ Borrar", key=f"del_{r['id']}"):
                        supabase.table("historial_reportes").delete().eq("id", r['id']).execute(); st.rerun()

    st.divider()
    st.markdown("#### 📥 Historial de Envios")
    aprobados = supabase.table("historial_reportes").select("*").eq("validado_por_admin", True).execute().data
    if aprobados:
        st.dataframe(pd.DataFrame(aprobados)[['created_at', 'proyecto', 'ndwi_ndsi', 'estado']])
