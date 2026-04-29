import streamlit as st
import pandas as pd
import json
import ee
from datetime import datetime
from dateutil.relativedelta import relativedelta
from fpdf import FPDF

# --- 1. CONEXIÓN SEGURA CON GOOGLE EARTH ENGINE ---
def inicializar_ee():
    try:
        # Forma moderna de inicializar sin errores de '_credentials'
        ee.Initialize(project='tu-proyecto-gee') # Cambia por tu ID de proyecto de Google Cloud
        return True
    except Exception:
        try:
            # Intento alternativo para entornos locales
            ee.Authenticate()
            ee.Initialize()
            return True
        except Exception as e:
            st.error(f"Error crítico de GEE: {e}")
            return False

# --- 2. LÓGICA DE NEGOCIO ---

def verificar_pago(fecha_inicio_str, meses_pagados):
    try:
        inicio = datetime.strptime(str(fecha_inicio_str), "%d/%m/%Y")
        vencimiento = inicio + relativedelta(months=int(meses_pagados))
        if datetime.now() > vencimiento:
            return False, vencimiento.strftime("%d/%m/%Y")
        return True, vencimiento.strftime("%d/%m/%Y")
    except:
        return False, "Error de fecha"

def procesar_satelite(coords_json, tipo_proyecto):
    try:
        # Parsear coordenadas (limpiando posibles saltos de línea del Excel)
        coords_limpias = coords_json.replace('\n', '').strip()
        area = ee.Geometry.Polygon(json.loads(coords_limpias))
        
        # Sentinel-2 y Landsat 8
        s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED').filterBounds(area).sort('CLOUDY_PIXEL_PERCENTAGE').first()
        l8 = ee.ImageCollection('LANDSAT/LC08/C02/T1_L2').filterBounds(area).sort('CLOUD_COVER').first()

        # SAVI
        savi_img = s2.expression('((B8-B4)/(B8+B4+0.5))*1.5', {
            'B8': s2.select('B8'), 'B4': s2.select('B4')
        })
        savi_val = savi_img.reduceRegion(ee.Reducer.mean(), area, 30).getInfo().get('B8', 0)

        # Temperatura
        temp_img = l8.select('ST_B10').multiply(0.00341802).add(149.0).subtract(273.15)
        lst_val = temp_img.reduceRegion(ee.Reducer.mean(), area, 30).getInfo().get('ST_B10', 0)

        res = {"SAVI": round(savi_val, 2), "TEMP": round(lst_val, 1), "EXTRA": 0, "ETIQUETA": ""}

        if tipo_proyecto == "MINERIA":
            arcilla = s2.normalizedDifference(['B11', 'B12'])
            res["EXTRA"] = round(arcilla.reduceRegion(ee.Reducer.mean(), area, 30).getInfo().get('nd', 0), 2)
            res["ETIQUETA"] = "Índice de Arcillas"
        elif tipo_proyecto == "HUMEDAL":
            ndwi = s2.normalizedDifference(['B3', 'B8'])
            res["EXTRA"] = round(ndwi.reduceRegion(ee.Reducer.mean(), area, 30).getInfo().get('nd', 0), 2)
            res["ETIQUETA"] = "Índice de Agua (NDWI)"
            
        return res
    except Exception as e:
        st.error(f"Error en datos satelitales: {e}")
        return None

# --- 3. INTERFAZ STREAMLIT ---

st.set_page_config(page_title="BioCore Intelligence", page_icon="🌿")
st.title("🌿 BioCore Intelligence")

# Inicializar GEE una sola vez
if 'ee_ready' not in st.session_state:
    st.session_state.ee_ready = inicializar_ee()

with st.sidebar:
    st.header("Acceso de Auditoría")
    email_in = st.text_input("Email Corporativo")
    pass_in = st.text_input("Contraseña", type="password")

# CONEXIÓN A GOOGLE SHEETS
# (Aquí usas tu st.connection de siempre)
# Supongamos que cargamos el df de usuarios:
# df = conn.read()

if email_in and pass_in:
    # IMPORTANTE: El email debe ser idéntico al del Excel
    # fila = df[df['Email'] == email_in]
    
    # SIMULACIÓN DE DATOS (Lo que tu App leería del Excel corregido)
    # Reemplaza esto por: user_data = fila.iloc[0].to_dict()
    user_data = {
        "Proyecto": "Pascua Lama", 
        "Tipo": "MINERIA",
        "Coordenadas": "[[-70.03, -29.31], [-70.01, -29.31], [-70.01, -29.33], [-70.03, -29.33]]",
        "Fecha_Inicio": "01/01/2026",
        "Meses_Pagados": 12 
    }

    pago_ok, vence = verificar_pago(user_data["Fecha_Inicio"], user_data["Meses_Pagados"])

    if not pago_ok:
        st.error(f"⚠️ CUENTA SUSPENDIDA. Venció el {vence}")
    else:
        st.success(f"Sesión iniciada: {user_data['Proyecto']}")
        
        if st.button("🚀 Ejecutar Análisis Satelital"):
            if st.session_state.ee_ready:
                with st.spinner("Procesando índices..."):
                    datos = procesar_satelite(user_data["Coordenadas"], user_data["Tipo"])
                    if datos:
                        c1, c2, c3 = st.columns(3)
                        c1.metric("Vigor (SAVI)", datos["SAVI"])
                        c2.metric("Temp. Suelo", f"{datos['TEMP']}°C")
                        if datos["ETIQUETA"]:
                            c3.metric(datos["ETIQUETA"], datos["EXTRA"])

                        # PDF
                        pdf = FPDF()
                        pdf.add_page()
                        pdf.set_font("Arial", "B", 16)
                        pdf.cell(0, 10, f"Auditoría BioCore: {user_data['Proyecto']}", ln=True)
                        pdf.set_font("Arial", "", 12)
                        pdf.ln(10)
                        pdf.cell(0, 10, f"Resultado SAVI: {datos['SAVI']}", ln=True)
                        pdf.ln(20)
                        pdf.set_font("Arial", "I", 8)
                        pdf.multi_cell(0, 5, "NOTA LEGAL: Reporte informativo basado en ESA/NASA. BioCore no se responsabiliza por el uso de estos datos.")
                        
                        st.download_button("📥 Descargar PDF", pdf.output(dest='S').encode('latin-1'), "BioCore.pdf")
