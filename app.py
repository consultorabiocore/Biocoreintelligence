import streamlit as st
import pandas as pd
import json
import ee
import requests
from datetime import datetime
from dateutil.relativedelta import relativedelta
from fpdf import FPDF
from supabase import create_client, Client

# --- 1. CONFIGURACIÓN INICIAL ---
st.set_page_config(page_title="BioCore Intelligence", layout="wide")

# Inicializar Supabase
@st.cache_resource
def init_supabase():
    return create_client(st.secrets["connections"]["supabase"]["url"], st.secrets["connections"]["supabase"]["key"])

supabase = init_supabase()

# Inicializar Google Earth Engine
def init_gee():
    try:
        if not ee.data._credentials:
            gee_json = json.loads(st.secrets["gee"]["json"])
            credentials = ee.ServiceAccountCredentials(gee_json['client_email'], key_data=gee_json['private_key'])
            ee.Initialize(credentials, project=gee_json['project_id'])
        return True
    except Exception as e:
        st.error(f"Error GEE: {e}")
        return False

# --- 2. FUNCIONES DE SEGURIDAD Y PAGOS ---
def verificar_estado_pago(fecha_inicio_str, meses_pagados):
    try:
        fecha_inicio = datetime.strptime(fecha_inicio_str, "%d/%m/%Y")
        fecha_limite = fecha_inicio + relativedelta(months=int(meses_pagados))
        return "AL_DIA" if datetime.now() <= fecha_limite else "DEUDA"
    except:
        return "ERROR_FORMATO"

# --- 3. PROCESAMIENTO SATELITAL INTEGRADO ---
def analizar_indices(poligono_str, tipo_proyecto):
    poligono = json.loads(poligono_str)
    roi = ee.Geometry.Polygon(poligono)
    
    # Sentinel-2 (Vigor y Agua/Arcilla)
    s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')\
        .filterBounds(roi).filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 20))\
        .sort('system:time_start', False).first().clip(roi)
    
    # Landsat 8 (Temperatura)
    l8 = ee.ImageCollection('LANDSAT/LC08/C02/T1_L2')\
        .filterBounds(roi).sort('system:time_start', False).first().clip(roi)

    # SAVI (Soil Adjusted Vegetation Index)
    savi = s2.expression('((B8-B4)/(B8+B4+0.5))*1.5', {
        'B8': s2.select('B8'), 'B4': s2.select('B4')
    }).reduceRegion(ee.Reducer.mean(), roi, 30).getInfo().get('constant', 0)
    
    # Temperatura de Superficie (LST)
    temp_img = l8.select('ST_B10').multiply(0.00341802).add(149.0).subtract(273.15)
    lst = temp_img.reduceRegion(ee.Reducer.mean(), roi, 30).getInfo().get('ST_B10', 0)

    resultado = {"SAVI": round(savi, 3), "TEMP": round(lst, 1), "EXTRA": 0, "ETIQUETA_EXTRA": ""}
    
    if tipo_proyecto == "MINERIA":
        arcilla = s2.normalizedDifference(['B11', 'B12'])
        resultado["EXTRA"] = round(arcilla.reduceRegion(ee.Reducer.mean(), roi, 30).getInfo().get('nd', 0), 3)
        resultado["ETIQUETA_EXTRA"] = "Índice de Arcillas"
    elif tipo_proyecto == "HUMEDAL":
        ndwi = s2.normalizedDifference(['B3', 'B8'])
        resultado["EXTRA"] = round(ndwi.reduceRegion(ee.Reducer.mean(), roi, 30).getInfo().get('nd', 0), 3)
        resultado["ETIQUETA_EXTRA"] = "Espejo de Agua (NDWI)"
        
    return resultado

# --- 4. GENERADOR DE PDF CON BLINDAJE LEGAL ---
def crear_pdf(user_data, indices):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("helvetica", "B", 16)
    pdf.cell(0, 10, f"REPORTE BIOCORE: {user_data['Proyecto']}", ln=True, align="C")
    pdf.ln(10)
    
    pdf.set_font("helvetica", "", 12)
    pdf.cell(0, 10, f"Fecha: {datetime.now().strftime('%d/%m/%Y')}", ln=True)
    pdf.cell(0, 10, f"Vigor Vegetal (SAVI): {indices['SAVI']}", ln=True)
    pdf.cell(0, 10, f"Temperatura de Superficie: {indices['TEMP']}°C", ln=True)
    
    if indices["ETIQUETA_EXTRA"]:
        pdf.cell(0, 10, f"{indices['ETIQUETA_EXTRA']}: {indices['EXTRA']}", ln=True)
    
    pdf.ln(20)
    pdf.set_font("helvetica", "I", 8)
    pdf.set_text_color(120, 120, 120)
    legal = ("NOTA DE ALCANCE TÉCNICO: Este reporte ha sido generado mediante teledetección satelital. "
             "La información es referencial y constituye un apoyo a la decisión. BioCore no se hace responsable "
             "por interpretaciones o acciones de terceros. Se recomienda validación en terreno.")
    pdf.multi_cell(0, 5, legal, align="C")
    return pdf.output(dest='S').encode('latin-1')

# --- 5. INTERFAZ ---
st.title("🌿 BioCore Intelligence")

if 'auth' not in st.session_state: st.session_state.auth = False

with st.sidebar:
    st.header("Acceso Clientes")
    if not st.session_state.auth:
        email = st.text_input("Email").lower().strip()
        password = st.text_input("Password", type="password")
        if st.button("Ingresar"):
            res = supabase.table("usuarios").select("*").eq("Email", email).execute()
            if res.data and str(res.data[0]['Password']) == password:
                st.session_state.auth = True
                st.session_state.user = res.data[0]
                st.rerun()
            else:
                st.error("Credenciales incorrectas")
    else:
        if st.button("Cerrar Sesión"):
            st.session_state.auth = False
            st.rerun()

if st.session_state.auth:
    u = st.session_state.user
    estado = verificar_estado_pago(u["Fecha_Inicio"], u["Meses_Pagados"])
    
    if estado == "DEUDA":
        st.error(f"⚠️ Suscripción de {u['Proyecto']} vencida. Contacte a soporte.")
    else:
        st.success(f"Consola activa: {u['Proyecto']}")
        if st.button("🚀 Ejecutar Escaneo Satelital"):
            if init_gee():
                with st.spinner("Analizando bandas multiespectrales..."):
                    res = analizar_indices(u["Coordenadas"], u["Tipo"])
                    
                    c1, c2, c3 = st.columns(3)
                    c1.metric("SAVI", res['SAVI'])
                    c2.metric("Temp. Superficie", f"{res['TEMP']} °C")
                    c3.metric(res['ETIQUETA_EXTRA'], res['EXTRA'])
                    
                    pdf_bytes = crear_pdf(u, res)
                    st.download_button("📥 Descargar Reporte PDF", pdf_bytes, f"Reporte_{u['Proyecto']}.pdf", "application/pdf")
