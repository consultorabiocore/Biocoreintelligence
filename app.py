import streamlit as st
import pandas as pd
import json
import ee
import requests
from datetime import datetime
from dateutil.relativedelta import relativedelta
from fpdf import FPDF

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="BioCore Intelligence", layout="wide")

# --- FUNCIONES DE SEGURIDAD Y PAGOS ---
def verificar_estado_pago(fecha_inicio_str, meses_pagados):
    """Calcula si el cliente está al día basado en la fecha de inicio."""
    try:
        fecha_inicio = datetime.strptime(fecha_inicio_str, "%d/%m/%Y")
        fecha_limite = fecha_inicio + relativedelta(months=int(meses_pagados))
        if datetime.now() > fecha_limite:
            return "DEUDA"
        return "AL_DIA"
    except:
        return "ERROR_FORMATO"

# --- PROCESAMIENTO SATELITAL (GEE) ---
def analizar_indices(poligono, tipo_proyecto):
    """Calcula SAVI, Temperatura y Arcilla/NDWI según el tipo."""
    # Nota: Requiere ee.Initialize() con tu cuenta de servicio
    roi = ee.Geometry.Polygon(poligono)
    
    # Selección de Colecciones
    s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED').filterBounds(roi).sort('CLOUDY_PIXEL_PERCENTAGE').first()
    l8 = ee.ImageCollection('LANDSAT/LC08/C02/T1_L2').filterBounds(roi).sort('CLOUD_COVER').first()

    # Índices Base (SAVI y LST)
    savi = s2.expression('((B8-B4)/(B8+B4+0.5))*1.5', {
        'B8': s2.select('B8'), 'B4': s2.select('B4')
    }).reduceRegion(ee.Reducer.mean(), roi, 30).getInfo().get('B8', 0)
    
    temp = l8.select('ST_B10').multiply(0.00341802).add(149.0).subtract(273.15)
    lst = temp.reduceRegion(ee.Reducer.mean(), roi, 30).getInfo().get('ST_B10', 0)

    # Índices Específicos
    resultado = {"SAVI": savi, "TEMP": lst, "EXTRA": 0, "ETIQUETA_EXTRA": ""}
    
    if tipo_proyecto == "MINERIA":
        # Índice de Minerales de Arcilla (SWIR1/SWIR2)
        arcilla = s2.normalizedDifference(['B11', 'B12'])
        resultado["EXTRA"] = arcilla.reduceRegion(ee.Reducer.mean(), roi, 30).getInfo().get('nd', 0)
        resultado["ETIQUETA_EXTRA"] = "Índice de Arcillas"
    elif tipo_proyecto == "HUMEDAL":
        # NDWI (Agua)
        ndwi = s2.normalizedDifference(['B3', 'B8'])
        resultado["EXTRA"] = ndwi.reduceRegion(ee.Reducer.mean(), roi, 30).getInfo().get('nd', 0)
        resultado["ETIQUETA_EXTRA"] = "Espejo de Agua (NDWI)"
        
    return resultado

# --- GENERADOR DE PDF CON BLINDAJE LEGAL ---
def crear_pdf(user_data, indices):
    pdf = FPDF()
    pdf.add_page()
    
    # Encabezado
    pdf.set_font("helvetica", "B", 16)
    pdf.cell(0, 10, f"REPORTE BIOCORE: {user_data['Proyecto']}", ln=True, align="C")
    pdf.ln(10)
    
    # Cuerpo
    pdf.set_font("helvetica", "", 12)
    pdf.cell(0, 10, f"Fecha: {datetime.now().strftime('%d/%m/%Y')}", ln=True)
    pdf.cell(0, 10, f"Vigor Vegetal (SAVI): {indices['SAVI']:.2f}", ln=True)
    pdf.cell(0, 10, f"Temperatura de Superficie: {indices['TEMP']:.1f}°C", ln=True)
    
    if indices["ETIQUETA_EXTRA"]:
        pdf.cell(0, 10, f"{indices['ETIQUETA_EXTRA']}: {indices['EXTRA']:.2f}", ln=True)
    
    # Bloque Legal (Blindaje)
    pdf.ln(20)
    pdf.set_font("helvetica", "I", 8)
    pdf.set_text_color(120, 120, 120)
    legal = ("NOTA DE ALCANCE TÉCNICO: Este reporte ha sido generado mediante teledetección satelital. "
             "La información es referencial y constituye un apoyo a la decisión. BioCore no se hace responsable "
             "por interpretaciones o acciones de terceros. Se recomienda validación en terreno.")
    pdf.multi_cell(0, 5, legal, align="C")
    
    return pdf.output(dest='S').encode('latin-1')

# --- INTERFAZ PRINCIPAL ---
st.title("🌿 BioCore Intelligence")

# 1. Login (Simulado desde tu Sheets)
with st.sidebar:
    st.header("Acceso Clientes")
    user_email = st.text_input("Email")
    user_pass = st.text_input("Password", type="password")
    # Aquí conectarías con tu Sheets ID: 1x6yAXNNlea3e43rijJu0aqcRpe4oP3BEnzgSgLuG1vU

# 2. Lógica de Sesión (Ejemplo con datos cargados)
if user_email: 
    # Supongamos que recuperamos estos datos del Excel
    user_data = {
        "Proyecto": "Auditoría Pascua Lama",
        "Tipo": "MINERIA",
        "Coordenadas": [[-70.03,-29.31], [-70.01,-29.31], [-70.01,-29.33], [-70.03,-29.33]],
        "Fecha_Inicio": "01/04/2026",
        "Meses_Pagados": 1,
        "Telegram_ID": "12345678"
    }
    
    # Verificar Pago
    estado = verificar_estado_pago(user_data["Fecha_Inicio"], user_data["Meses_Pagados"])
    
    if estado == "DEUDA":
        st.error("⚠️ Suscripción Pendiente de Pago")
        st.info(f"Su plan de {user_data['Proyecto']} requiere renovación para descargar nuevos reportes.")
        btn_bloqueado = True
    else:
        st.success(f"Bienvenido a la consola de {user_data['Proyecto']}")
        btn_bloqueado = False

    # 3. Botón de Acción
    if st.button("Ejecutar Escaneo Satelital", disabled=btn_bloqueado):
        with st.spinner("Procesando datos de NASA y ESA..."):
            res = analizar_indices(user_data["Coordenadas"], user_data["Tipo"])
            st.metric("Vigor Vegetal", f"{res['SAVI']:.2f}")
            st.metric("Temperatura", f"{res['TEMP']:.1f} °C")
            
            pdf_bytes = crear_pdf(user_data, res)
            st.download_button("📥 Descargar Reporte PDF", pdf_bytes, "Reporte_BioCore.pdf", "application/pdf")
