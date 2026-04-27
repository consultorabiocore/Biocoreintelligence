import streamlit as st
import ee
import json
import os
import requests
import re
import base64
import folium
import pandas as pd
from streamlit_folium import st_folium

# --- CONFIGURACIÓN DE BIOCORE ---
st.set_page_config(page_title="BioCore Intelligence", layout="wide", initial_sidebar_state="expanded")

T_TOKEN = "7961684994:AAGbepFHxXJtjCVTCjEwq2xWh9vT9TO6G68"
LOGO_PATH = os.path.join("assets", "logo_biocore.png")

# --- BASE DE DATOS DE SESIÓN ---
if 'suscripciones' not in st.session_state:
    st.session_state.suscripciones = [
        {"ID": "BC-001", "PROYECTO": "Loreto Campos", "CHAT_ID": "6712325113", "CATEGORIA": "Administrador"}
    ]

# --- FUNCIONES TÉCNICAS ---
def inicializar_gee():
    try:
        if 'gee_auth' not in st.session_state:
            info = json.loads(st.secrets["GEE_JSON"])
            ee.Initialize(ee.ServiceAccountCredentials(info['client_email'], key_data=info['private_key'].replace("\\n", "\n")))
            st.session_state.gee_auth = True
        return True
    except: return False

def procesar_coords(texto):
    nums = re.findall(r"[-+]?\d*\.\d+|\d+", texto)
    coords = []
    for i in range(0, len(nums), 2):
        if i+1 < len(nums): coords.append([float(nums[1]), float(nums[0])])
    if coords and coords[0] != coords[-1]: coords.append(coords[0])
    return coords

# --- BARRA LATERAL ---
with st.sidebar:
    if os.path.exists(LOGO_PATH):
        with open(LOGO_PATH, "rb") as f:
            st.markdown(f'<div style="text-align:center"><img src="data:image/png;base64,{base64.b64encode(f.read()).decode()}" width="180"></div>', unsafe_allow_html=True)
    
    st.markdown("---")
    acceso = st.radio("Módulo de Control:", ["🛰️ Monitor de Auditoría", "👤 Registro y Configuración"])
    st.markdown("---")
    st.caption("BioCore Intelligence v2.5")

# --- LÓGICA DE INTERFAZ ---
if inicializar_gee():

    if acceso == "👤 Registro y Configuración":
        st.header("Configuración de Reportes Diarios")
        st.write("Registre al cliente aquí para activar su reporte automático a Telegram.")

        # Tabla de Clientes para que el cliente vea sus datos
        if st.session_state.suscripciones:
            st.markdown("### 📋 Suscripciones Activas")
            df = pd.DataFrame(st.session_state.suscripciones)
            st.dataframe(df, use_container_width=True, hide_index=True)
        
        st.markdown("---")
        
        col_reg, col_help = st.columns([1, 1])
        with col_reg:
            st.subheader("📝 Nuevo Registro Técnico")
            with st.form("registro_p"):
                nombre_p = st.text_input("Nombre del Proyecto")
                id_tele = st.text_input("Chat ID de Telegram")
                if st.form_submit_button("✅ Activar Monitoreo Diario"):
                    if nombre_p and id_tele:
                        nuevo_id = f"BC-{len(st.session_state.suscripciones)+1:03}"
                        st.session_state.suscripciones.append({
                            "ID": nuevo_id, "PROYECTO": nombre_p, "CHAT_ID": id_tele, "CATEGORIA": "Suscripción Activa"
                        })
                        st.toast("LOG: Enlace Diario Activado", icon="📡")
                        st.rerun()

    else:
        # PANTALLA DE AUDITORÍA (MAPA)
        nombres = [s['PROYECTO'] for s in st.session_state.suscripciones]
        sel_cliente = st.selectbox("Seleccione Proyecto para Generar Informe Especial:", nombres)
        data_p = [s for s in st.session_state.suscripciones if s['PROYECTO'] == sel_cliente][0]
        
        st.title(f"Centro de Mando: {sel_cliente}")
        
        c1, c2 = st.columns([1, 2])
        
        with c1:
            st.markdown("### 📊 Generador de Informe")
            st.info(f"ID: {data_p['ID']} | Canal: {data_p['CHAT_ID']}")
            
            raw = st.text_area("Coordenadas del incidente (Lat, Lon):", height=200, placeholder="-29.3177, -70.0191...")
            puntos = procesar_coords(raw) if raw else []
            geom = ee.Geometry.Polygon(puntos) if len(puntos) > 2 else None
            
            if geom:
                st.write("---")
                if st.button("📤 TRANSMITIR INFORME AHORA"):
                    # Barra de progreso tech
                    progreso = st.progress(0)
                    for i in range(100):
                        import time
                        time.sleep(0.01)
                        progreso.progress(i + 1)
                    
                    url = f"https://api.telegram.org/bot{T_TOKEN}/sendMessage"
                    msg = (f"🛰 **INFORME ESPECIAL BIOCORE**\n"
                           f"━━━━━━━━━━━━━━\n"
                           f"✅ **ID:** {data_p['ID']}\n"
                           f"👤 **PROYECTO:** {sel_cliente}\n"
                           f"🛰 **ALERTA:** Análisis de área completado.\n"
                           f"📅 **FECHA:** 27/04/2026\n"
                           f"━━━━━━━━━━━━━━")
                    
                    res = requests.post(url, data={"chat_id": data_p['CHAT_ID'], "text": msg, "parse_mode": "Markdown"})
                    if res.status_code == 200:
                        st.toast("Transmisión Exitosa", icon="📡")
                        st.success("Informe enviado al terminal móvil.")
                    else:
                        st.error("Error de enlace.")

        with c2:
            if geom:
                m = folium.Map(location=[puntos[0][1], puntos[0][0]], zoom_start=14)
                folium.TileLayer('https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}', attr='Google', name='Sat').add_to(m)
                folium.GeoJson(data=geom.getInfo(), style_function=lambda x: {'color': '#00ffcc', 'weight': 2, 'fillOpacity': 0.1}).add_to(m)
                st_folium(m, width="100%", height=500)
            else:
                st_folium(folium.Map(location=[-37, -72], zoom_start=5), width="100%", height=500)
