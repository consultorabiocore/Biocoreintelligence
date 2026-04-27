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

# --- FUNCIONES CORE ---
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

# --- SIDEBAR TECNOLÓGICA ---
with st.sidebar:
    if os.path.exists(LOGO_PATH):
        with open(LOGO_PATH, "rb") as f:
            data = base64.b64encode(f.read()).decode()
            st.markdown(f'<div style="text-align:center"><img src="data:image/png;base64,{data}" width="180"></div>', unsafe_allow_html=True)
    
    st.markdown("---")
    # Perfil de acceso
    acceso = st.radio("Módulo de Acceso:", ["🛰️ Monitor de Auditoría", "👤 Portal de Clientes"])
    st.markdown("---")
    st.caption("BioCore Intelligence v2.1")

# --- LÓGICA DE INTERFAZ ---
if inicializar_gee():

    # --- PANTALLA: PORTAL DE CLIENTES (VER Y EDITAR DATOS) ---
    if acceso == "👤 Portal de Clientes":
        st.header("Centro de Gestión de Cuentas")
        st.write("Aquí tanto tú como el cliente pueden verificar los datos de enlace.")

        # Vista de Tabla Profesional
        if st.session_state.suscripciones:
            df = pd.DataFrame(st.session_state.suscripciones)
            st.markdown("### 📋 Directorio de Proyectos Activos")
            st.dataframe(df, use_container_width=True, hide_index=True) # Dataframe interactivo
        
        st.markdown("---")
        
        # Registro/Edición
        col_reg, col_info = st.columns([1.5, 1])
        
        with col_reg:
            st.subheader("📝 Registro de Nuevas Credenciales")
            with st.form("form_registro"):
                nombre_p = st.text_input("Nombre del Proyecto / Cliente")
                id_tele = st.text_input("ID Técnico de Telegram")
                cat = st.selectbox("Tipo de Auditoría", ["Minería", "Humedales", "Glaciares", "Agrícola"])
                
                if st.form_submit_button("Vincular al Sistema"):
                    if nombre_p and id_tele:
                        nuevo_id = f"BC-0{len(st.session_state.suscripciones)+1}"
                        st.session_state.suscripciones.append({
                            "ID": nuevo_id, "PROYECTO": nombre_p, "CHAT_ID": id_tele, "CATEGORIA": cat
                        })
                        st.toast(f"LOG: Proyecto {nombre_p} inicializado.", icon="✅")
                        st.rerun()
        
        with col_info:
            st.info("""
            **Guía para el Cliente:**
            1. Busque el bot en Telegram.
            2. Presione /start.
            3. Ingrese su ID en este panel.
            4. El sistema verificará el enlace automáticamente.
            """)

    # --- PANTALLA: MONITOR DE AUDITORÍA (LO QUE EL CLIENTE VE) ---
    else:
        if not st.session_state.suscripciones:
            st.warning("No hay bases de datos cargadas.")
        else:
            nombres = [s['PROYECTO'] for s in st.session_state.suscripciones]
            sel_cliente = st.selectbox("Seleccione Proyecto para Visualización:", nombres)
            data_p = [s for s in st.session_state.suscripciones if s['PROYECTO'] == sel_cliente][0]
            
            st.title(f"Monitor de Vigilancia: {sel_cliente}")
            
            # Layout Tech
            c1, c2 = st.columns([1, 2])
            
            with c1:
                st.markdown("### 📊 Parámetros de Telemetría")
                st.write(f"**ID Proyecto:** `{data_p['ID']}`")
                st.write(f"**Enlace:** `Telegram Encrypted ({data_p['CHAT_ID']})`")
                
                raw = st.text_area("Coordenadas de Análisis (Lat, Lon):", height=200, placeholder="-29.3177, -70.0191...")
                puntos = procesar_coords(raw) if raw else []
                geom = ee.Geometry.Polygon(puntos) if len(puntos) > 2 else None
                
                if geom:
                    if st.button("🛰️ DISPARAR TRANSMISIÓN"):
                        url = f"https://api.telegram.org/bot{T_TOKEN}/sendMessage"
                        msg = (f"🛰 **BIOCORE INTELLIGENCE**\n"
                               f"━━━━━━━━━━━━━━\n"
                               f"✅ **ID:** {data_p['ID']}\n"
                               f"👤 **CLIENTE:** {sel_cliente}\n"
                               f"📅 **STATUS:** Monitoreo Exitoso\n"
                               f"━━━━━━━━━━━━━━")
                        try:
                            res = requests.post(url, data={"chat_id": data_p['CHAT_ID'], "text": msg, "parse_mode": "Markdown"})
                            if res.status_code == 200:
                                st.toast("Transmisión Completada", icon="📡")
                            else: st.error("Fallo de enlace.")
                        except: st.error("Error de red.")

            with c2:
                if geom:
                    m = folium.Map(location=[puntos[0][1], puntos[0][0]], zoom_start=14)
                    folium.TileLayer('https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}', attr='Google', name='Sat').add_to(m)
                    folium.GeoJson(data=geom.getInfo(), style_function=lambda x: {'color': '#00ffcc', 'weight': 2, 'fillOpacity': 0.1}).add_to(m)
                    st_folium(m, width="100%", height=500)
                else:
                    st_folium(folium.Map(location=[-37, -72], zoom_start=5), width="100%", height=500)
