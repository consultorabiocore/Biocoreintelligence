import streamlit as st
import pandas as pd
import json
import ee
from datetime import datetime
from dateutil.relativedelta import relativedelta
from fpdf import FPDF

# --- 1. INICIALIZACIÓN DE SERVICIOS ---
# Asegúrate de haber configurado los Secretos de Streamlit para GEE
try:
    if not ee.data._credentials:
        ee.Initialize()
except Exception as e:
    st.error(f"Error de conexión con Google Earth Engine: {e}")

# --- 2. FUNCIONES DE LÓGICA DE NEGOCIO ---

def verificar_pago(fecha_inicio_str, meses_pagados):
    """Calcula si el cliente tiene acceso basado en su suscripción."""
    try:
        inicio = datetime.strptime(fecha_inicio_str, "%d/%m/%Y")
        vencimiento = inicio + relativedelta(months=int(meses_pagados))
        if datetime.now() > vencimiento:
            return False, vencimiento.strftime("%d/%m/%Y")
        return True, vencimiento.strftime("%d/%m/%Y")
    except:
        return False, "Error en fecha"

def procesar_satelite(coords_json, tipo_proyecto):
    """Cálculo de índices específicos (SAVI, Temp, Arcilla)."""
    try:
        # Convertir texto del Excel a geometría de GEE
        area = ee.Geometry.Polygon(json.loads(coords_json))
        
        # Colecciones (Sentinel-2 y Landsat 8)
        s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED').filterBounds(area).sort('CLOUDY_PIXEL_PERCENTAGE').first()
        l8 = ee.ImageCollection('LANDSAT/LC08/C02/T1_L2').filterBounds(area).sort('CLOUD_COVER').first()

        # SAVI (Vigor Vegetal)
        savi = s2.expression('((B8-B4)/(B8+B4+0.5))*1.5', {
            'B8': s2.select('B8'), 'B4': s2.select('B4')
        }).reduceRegion(ee.Reducer.mean(), area, 30).getInfo().get('B8', 0)

        # LST (Temperatura Superficie)
        temp = l8.select('ST_B10').multiply(0.00341802).add(149.0).subtract(273.15)
        lst = temp.reduceRegion(ee.Reducer.mean(), area, 30).getInfo().get('ST_B10', 0)

        res = {"SAVI": round(savi, 2), "TEMP": round(lst, 1), "EXTRA": 0, "ETIQUETA": ""}

        # Lógica por tipo de proyecto
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
        st.error(f"Error en procesamiento satelital: {e}")
        return None

# --- 3. INTERFAZ DE USUARIO ---

st.set_page_config(page_title="BioCore Intelligence", page_icon="🌿")
st.title("🌿 BioCore: Monitoreo Ambiental Pro")

# Sidebar de Login
with st.sidebar:
    st.image("https://via.placeholder.com/150?text=BioCore+Logo") # Aquí puedes poner tu logo
    email_input = st.text_input("Usuario (Email)")
    pass_input = st.text_input("Contraseña", type="password")

# Simulación de carga de datos desde tu Google Sheets
# Nota: Aquí debes usar tu lógica de st.connection("gsheets", ...)
# Por ahora simulamos que 'df' es tu tabla de Excel
if email_input and pass_input:
    # --- BUSCAR USUARIO ---
    # df = tu_conexion_a_sheets() 
    # (Simulación de fila encontrada)
    user_found = True # Esto vendría de validar email/pass en el df
    
    if user_found:
        # Extraemos datos de la fila (Asegúrate que los nombres coincidan con tu Excel)
        u_data = {
            "Proyecto": "Auditoría Pascua Lama", # Columna C
            "Tipo": "MINERIA",                  # Columna G
            "Coordenadas": "[[-70.03, -29.31], [-70.01, -29.31], [-70.01, -29.33], [-70.03, -29.33]]", # Columna E
            "Fecha_Inicio": "01/01/2026",        # Columna H
            "Meses_Pagados": 5                   # Columna I
        }

        # Validar Suscripción
        esta_al_dia, fecha_vence = verificar_pago(u_data["Fecha_Inicio"], u_data["Meses_Pagados"])

        if not esta_al_dia:
            st.error(f"❌ SUSCRIPCIÓN VENCIDA (Expiró el {fecha_vence})")
            st.warning("Por favor regularice su pago para acceder a los nuevos reportes.")
        else:
            st.success(f"✅ CONECTADO: {u_data['Proyecto']}")
            st.info(f"Suscripción activa hasta: {fecha_vence}")

            # --- ACCIONES PRINCIPALES ---
            col1, col2 = st.columns(2)
            
            with col1:
                if st.button("🚀 Iniciar Escaneo Satelital"):
                    with st.spinner("Analizando espectro electromagnético..."):
                        resultados = procesar_satelite(u_data["Coordenadas"], u_data["Tipo"])
                        if resultados:
                            st.metric("Vigor Vegetal (SAVI)", resultados["SAVI"])
                            st.metric("Temperatura Suelo", f"{resultados['TEMP']} °C")
                            if resultados["ETIQUETA"]:
                                st.metric(resultados["ETIQUETA"], resultados["EXTRA"])
                            
                            # Generación de PDF
                            pdf = FPDF()
                            pdf.add_page()
                            pdf.set_font("Arial", "B", 16)
                            pdf.cell(40, 10, f"Reporte BioCore - {u_data['Proyecto']}")
                            pdf.ln(20)
                            pdf.set_font("Arial", "", 12)
                            pdf.cell(40, 10, f"SAVI: {resultados['SAVI']}")
                            pdf.ln(10)
                            pdf.set_font("Arial", "I", 8)
                            pdf.multi_cell(0, 5, "\n\nDISCLAIMER: Este reporte es referencial. BioCore no se responsabiliza por decisiones de terceros.")
                            
                            pdf_output = pdf.output(dest='S').encode('latin-1')
                            st.download_button("📥 Descargar Reporte PDF", pdf_output, "BioCore_Reporte.pdf")

            with col2:
                st.write("### Mapa de Área de Interés")
                # Aquí iría tu código de folium para mostrar el polígono
                st.map() # Mapa simplificado por ahora
