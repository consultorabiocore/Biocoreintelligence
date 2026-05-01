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

# --- 2. MOTOR DE INFORMES (DISEÑO ORIGINAL AZUL MARINO) ---

def generar_documentos(r):
    proyecto = r.get('proyecto', 'Proyecto_BioCore')
    # Limpieza de nulos para evitar TypeErrors en el formato decimal
    v_ndsi = float(r.get('ndwi_ndsi') or 0)
    v_radar = float(r.get('radar_vv') or 0)
    v_temp = float(r.get('temp_suelo') or 0)
    v_savi = float(r.get('savi') or 0)
    
    # Lógica de Diagnóstico
    color = (200, 0, 0) if v_ndsi < 0.35 else (0, 100, 0)
    est = "ALERTA: PERDIDA DE COBERTURA" if v_ndsi < 0.35 else "CONTROL: ESTABILIDAD"
    diag_txt = (f"Indice detectado ({v_ndsi:.3f}) bajo umbral critico. Riesgo de exposicion de suelo." 
                if v_ndsi < 0.35 else f"Indice detectado ({v_ndsi:.3f}) estable. Blindaje RCA vigente.")

    # A. PDF CON BANNER AZUL MARINO
    pdf = FPDF()
    pdf.add_page()
    pdf.set_fill_color(20, 50, 80) # Azul BioCore
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
    pdf.multi_cell(0, 7, f"{diag_txt}\n\nDatos de Respaldo:\n- Radar VV: {v_radar:.2f} dB\n- Temperatura: {v_temp:.1f}C\n- SAVI: {v_savi:.3f}", border=1)
    
    pdf_path = f"Reporte_{proyecto}.pdf"
    pdf.output(pdf_path)

    # B. WORD EDITABLE
    doc = Document()
    doc.add_heading(f"INFORME AUDITORIA: {proyecto}", 0)
    doc.add_paragraph("Responsable Tecnica: Loreto Campos")
    doc.add_heading("Resultados", level=1)
    p = doc.add_paragraph(); p.add_run(f"ESTATUS: {est}").bold = True
    doc.add_paragraph(diag_txt)
    doc_path = f"Reporte_{proyecto}_Editable.docx"
    doc.save(doc_path)
    
    return pdf_path, doc_path

def enviar_a_telegram(pdf_p, doc_p, proyecto):
    token = st.secrets['telegram']['token']
    chat_id = st.secrets['telegram']['chat_id']
    try:
        for f_path in [pdf_p, doc_p]:
            with open(f_path, "rb") as f:
                requests.post(f"https://api.telegram.org/bot{token}/sendDocument",
                             data={"chat_id": chat_id, "caption": f"🛡️ BioCore: {proyecto}"},
                             files={"document": f})
        return True
    except:
        return False

# --- 3. ANALISIS SATELITAL Y GEOMETRIA SEGURA ---

def dibujar_mapa(coords):
    try:
        js = json.loads(coords) if isinstance(coords, str) else coords
        pts = js['coordinates'][0] if isinstance(js, dict) and 'coordinates' in js else js
        loc = [[float(p[1]), float(p[0])] for p in pts]
        m = folium.Map(location=loc[0], zoom_start=15, tiles='https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}', attr='Google')
        folium.Polygon(loc, color="yellow", fill=True, fill_opacity=0.1).add_to(m)
        return m
    except:
        return folium.Map(location=[-37, -72], zoom_start=4)

def ejecutar_auditoria_v5(p):
    iniciar_gee()
    try:
        # Extracción segura de coordenadas
        coords_raw = p['Coordenadas']
        js = json.loads(coords_raw) if isinstance(coords_raw, str) else coords_raw
        geom = ee.Geometry.Polygon(js['coordinates'] if isinstance(js, dict) and 'coordinates' in js else js)

        # 1. Óptico (S2)
        s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED').filterBounds(geom).sort('CLOUDY_PIXEL_PERCENTAGE').first()
        ndsi = s2.normalizedDifference(['B3','B11']).reduceRegion(ee.Reducer.mean(), geom, 30).getInfo().get('nd', 0)
        savi = s2.expression('((B8-B4)/(B8+B4+0.5))*1.5', {'B8':s2.select('B8'),'B4':s2.select('B4')}).reduceRegion(ee.Reducer.mean(), geom, 30).getInfo().get('constant', 0)
        
        # 2. Radar (S1)
        s1 = ee.ImageCollection('COPERNICUS/S1_GRD').filterBounds(geom).filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV')).first()
        radar = s1.select('VV').reduceRegion(ee.Reducer.mean(), geom, 30).getInfo().get('VV', 0)
        
        # 3. Temp
        temp = ee.ImageCollection("MODIS/061/MOD11A1").filterBounds(geom).sort('system:time_start', False).first().select('LST_Day_1km').multiply(0.02).subtract(273.15).reduceRegion(ee.Reducer.mean(), geom, 1000).getInfo().get('LST_Day_1km', 0)

        supabase.table("historial_reportes").insert({
            "proyecto": p['Proyecto'], "ndwi_ndsi": ndsi, "savi": savi, "radar_vv": radar, 
            "temp_suelo": temp, "validado_por_admin": False, "estado": "BORRADOR"
        }).execute()
        st.success(f"Auditoria lista para {p['Proyecto']}")
    except Exception as e:
        st.error(f"Error en analisis: {e}")

# --- 4. INTERFAZ ---

tab1, tab2 = st.tabs(["🚀 Vigilancia Activa", "📊 Centro de Revision"])

with tab1:
    proyectos = supabase.table("usuarios").select("*").execute().data
    for p in proyectos:
        st.markdown(f"### 📍 {p['Proyecto']}")
        c_map, c_btn = st.columns([3, 1])
        with c_map: folium_static(dibujar_mapa(p['Coordenadas']), width=900, height=450)
        with c_btn:
            if st.button(f"Ejecutar Analisis", key=f"run_{p['Proyecto']}"):
                ejecutar_auditoria_v5(p)

with tab2:
    st.subheader("📋 Revision y Envio")
    pendientes = supabase.table("historial_reportes").select("*").eq("validado_por_admin", False).execute().data
    if pendientes:
        for r in pendientes:
            with st.expander(f"Reporte: {r['proyecto']} ({r['created_at'][:16]})"):
                # Visualización segura
                v_ndsi = float(r.get('ndwi_ndsi') or 0)
                v_radar = float(r.get('radar_vv') or 0)
                st.write(f"**NDSI:** {v_ndsi:.3f} | **Radar:** {v_radar:.2f} dB")
                
                c1, c2, c3 = st.columns(3)
                with c1:
                    if st.button("🚀 Enviar Pack Oficial", key=f"of_{r['id']}", type="primary"):
                        pdf, doc = generar_documentos(r)
                        if enviar_a_telegram(pdf, doc, r['proyecto']):
                            supabase.table("historial_reportes").update({"validado_por_admin": True, "estado": "ENVIADO"}).eq("id", r['id']).execute()
                            st.success("Enviado."); st.rerun()
                with c2:
                    if st.button("📩 Reenvio Manual", key=f"man_{r['id']}"):
                        pdf, doc = generar_documentos(r)
                        enviar_a_telegram(pdf, doc, r['proyecto'])
                        st.info("Copia enviada a Telegram.")
                with c3:
                    if st.button("🗑️ Borrar", key=f"del_{r['id']}"):
                        supabase.table("historial_reportes").delete().eq("id", r['id']).execute(); st.rerun()
