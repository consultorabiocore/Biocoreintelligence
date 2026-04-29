import streamlit as st
import pandas as pd
import json
import ee
from datetime import datetime
from dateutil.relativedelta import relativedelta
from fpdf import FPDF

# --- 1. CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="BioCore Intelligence", layout="wide", page_icon="🌿")

# --- 2. INICIALIZACIÓN DE SERVICIOS (GOOGLE EARTH ENGINE) ---
def iniciar_gee():
    try:
        # Intento de inicialización estándar
        ee.Initialize()
        return True
    except Exception as e:
        st.sidebar.error(f"Error Satelital: {e}")
        return False

# --- 3. FUNCIONES DE APOYO (Lógica de Negocio y PDF) ---

def verificar_estado_pago(fecha_inicio_str, meses_pagados):
    try:
        inicio = datetime.strptime(str(fecha_inicio_str).strip(), "%d/%m/%Y")
        vence = inicio + relativedelta(months=int(meses_pagados))
        if datetime.now() > vence:
            return False, vence.strftime("%d/%m/%Y")
        return True, vence.strftime("%d/%m/%Y")
    except:
        return False, "Error de formato en Excel"

def crear_reporte_pdf(user_data, res):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, f"REPORTE BIOCORE: {user_data['Proyecto']}", ln=True, align="C")
    pdf.ln(10)
    pdf.set_font("Arial", "", 12)
    pdf.cell(0, 10, f"Fecha: {datetime.now().strftime('%d/%m/%Y')}", ln=True)
    pdf.cell(0, 10, f"Vigor Vegetal (SAVI): {res.get('SAVI', 'N/A')}", ln=True)
    pdf.cell(0, 10, f"Temperatura: {res.get('TEMP', 'N/A')} C", ln=True)
    if res.get('ETIQUETA'):
        pdf.cell(0, 10, f"{res['ETIQUETA']}: {res['EXTRA']}", ln=True)
    
    # Blindaje Legal
    pdf.ln(20)
    pdf.set_font("Arial", "I", 8)
    pdf.set_text_color(100, 100, 100)
    disclaimer = ("NOTA DE ALCANCE TÉCNICO: Este reporte es referencial y basado en teledetección. "
                  "BioCore no se responsabiliza por decisiones de terceros. Se sugiere validación en terreno.")
    pdf.multi_cell(0, 5, disclaimer, align="C")
    return pdf.output(dest='S').encode('latin-1')

# --- 4. INTERFAZ PRINCIPAL ---

st.title("🌿 BioCore Intelligence")

# Barra lateral de Login con limpieza de datos
with st.sidebar:
    st.header("Acceso de Auditoría")
    with st.form("login_form"):
        email_input = st.text_input("Email Corporativo").strip().lower()
        pass_input = st.text_input("Contraseña", type="password").strip()
        boton_ingresar = st.form_submit_button("Ingresar")

# Aquí debes conectar tu Sheets. Ejemplo:
# conn = st.connection("gsheets", type=GSheetsConnection)
# df = conn.read()

if boton_ingresar:
    # --- VALIDACIÓN DE CREDENCIALES (Simulada con tu lógica de Excel) ---
    # En producción usarías: fila = df[df['Email'].str.strip().str.lower() == email_input]
    
    # Para la prueba, forzamos el acceso si los datos coinciden:
    if email_input == "consultorabiocore@gmail.com" and pass_input == "123":
        st.session_state.autenticado = True
        # Estos datos vendrán de tu fila de Excel corregida
        st.session_state.user_data = {
            "Proyecto": "Pascua Lama",
            "Tipo": "MINERIA",
            "Coordenadas": "[[-70.03, -29.31], [-70.01, -29.31], [-70.01, -29.33], [-70.03, -29.33]]",
            "Fecha_Inicio": "01/04/2026",
            "Meses_Pagados": 1
        }
        st.rerun()
    else:
        st.error("Credenciales no encontradas. Verifica espacios o mayúsculas en el Excel.")

# --- 5. PANEL DE CONTROL (Solo si está autenticado) ---
if st.session_state.get('autenticado'):
    u = st.session_state.user_data
    
    # Verificar Pago
    pago_ok, fecha_vence = verificar_estado_pago(u["Fecha_Inicio"], u["Meses_Pagados"])
    
    if not pago_ok:
        st.error(f"⚠️ SUSCRIPCIÓN VENCIDA (Expiró el {fecha_vence})")
        st.info("El acceso a nuevos reportes está bloqueado hasta regularizar el pago.")
    else:
        st.success(f"✅ Sesión Activa: {u['Proyecto']}")
        st.write(f"Suscripción válida hasta: **{fecha_vence}**")
        
        col1, col2 = st.columns([1, 1])
        
        with col1:
            st.subheader("📊 Análisis Satelital")
            if st.button("🚀 Iniciar Escaneo de Área"):
                with st.spinner("Conectando con satélites ESA/NASA..."):
                    # Inicializamos GEE solo al presionar el botón
                    if iniciar_gee():
                        # Simulación de resultados técnicos
                        res_tech = {"SAVI": 0.45, "TEMP": 21.8, "EXTRA": 0.12, "ETIQUETA": "Índice de Arcillas"}
                        
                        st.metric("Vigor Vegetal (SAVI)", res_tech["SAVI"])
                        st.metric("Temperatura Suelo", f"{res_tech['TEMP']} °C")
                        st.metric(res_tech["ETIQUETA"], res_tech["EXTRA"])
                        
                        # Botón de Descarga PDF
                        pdf_data = crear_reporte_pdf(u, res_tech)
                        st.download_button("📥 Descargar Reporte PDF", pdf_data, "Reporte_BioCore.pdf")
        
        with col2:
            st.subheader("🗺️ Área de Influencia")
            # Mapa base de Streamlit
            st.map()
            st.caption("Coordenadas registradas: " + u["Coordenadas"])

else:
    st.info("Por favor, ingresa tus credenciales en la barra lateral para comenzar.")
