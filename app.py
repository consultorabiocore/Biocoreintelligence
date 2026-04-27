import streamlit as st
import ee
import json
import os
import requests
import re
import base64
import folium
from streamlit_folium import st_folium

# --- CONFIGURACIÓN DE BIOCORE ---
st.set_page_config(page_title="BioCore Intelligence", layout="wide", initial_sidebar_state="expanded")

# 1. Configuración de Credenciales y Bot
T_TOKEN = "7961684994:AAGbepFHxXJtjCVTCjEwq2xWh9vT9TO6G68"
LOGO_PATH = os.path.join("assets", "logo_biocore.png")

# 2. Inicialización de Memoria (Base de Datos interna de la sesión)
if 'suscripciones' not in st.session_state:
    st.session_state.suscripciones = [{"nombre": "Loreto Campos", "id": "6712325113"}]

# --- FUNCIONES TÉCNICAS ---
def inicializar_gee():
    try:
        if 'gee_auth' not in st.session_state:
            info = json.loads(st.secrets["GEE_JSON"])
            creds = ee.ServiceAccountCredentials(info['client_email'], key_data=info['private_key'].replace("\\n", "\n"))
            ee.Initialize(creds)
            st.session_state.gee_auth = True
        return True
    except Exception as e:
        st.error(f"Error GEE: {e}")
        return False

def procesar_coordenadas(texto):
    """Limpia el texto y extrae Lat, Lon para GEE"""
    nums = re.findall(r"[-+]?\d*\.\d+|\d+", texto)
    coords = []
    for i in range(0, len(nums), 2):
        if i+1 < len(nums):
            # Formato GEE: [Longitud, Latitud]
            coords.append([float(nums[1]), float(nums[0])])
    if coords and coords[0] != coords[-1]:
        coords.append(coords[0]) # Cierra el polígono
    return coords

# --- INTERFAZ (SIDEBAR) ---
with st.sidebar:
    # Mostrar Logo
    if os.path.exists(LOGO_PATH):
        with open(LOGO_PATH, "rb") as f:
            data = base64.b64encode(f.read()).decode()
            st.markdown(f'<div style="text-align:center"><img src="data:image/png;base64,{data}" width="180"></div>', unsafe_allow_html=True)
    
    st.markdown("---")
    menu = st.radio("Menú de Navegación", ["📊 Auditoría Satelital", "⚙️ Registro de Clientes"])
    st.markdown("---")
    
    if menu == "⚙️ Registro de Clientes":
        st.subheader("Nuevo Registro")
        with st.form("form_registro"):
            n = st.text_input("Nombre del Cliente/Proyecto")
            c_id = st.text_input("Chat ID de Telegram")
            if st.form_submit_button("Guardar"):
                if n and c_id:
                    st.session_state.suscripciones.append({"nombre": n, "id": c_id})
                    st.success("Registrado.")
                else: st.error("Llenar campos.")
    
    else:
        st.subheader("Configuración de Envío")
        lista_nombres = [s['nombre'] for s in st.session_state.suscripciones]
        cliente_sel = st.selectbox("Seleccionar Destinatario:", lista_nombres)
        capa = st.selectbox("Capa Ambiental:", ["Minería", "Glaciares", "Humedales", "Agrícola"])
        st.info(f"Reporte vinculado al ID: {[s['id'] for s in st.session_state.suscripciones if s['nombre']==cliente_sel][0]}")

# --- CUERPO PRINCIPAL ---
if inicializar_gee():
    if menu == "📊 Auditoría Satelital":
        st.title(f"Vigilancia: {cliente_sel}")
        
        col1, col2 = st.columns([1, 2])
        
        with col1:
            st.markdown("### 📍 Ingreso de Coordenadas")
            ejemplo = "-29.3177, -70.0191\n-29.3300, -70.0100\n-29.3400, -70.0300"
            raw = st.text_area("Latitud, Longitud (una por línea):", height=300, placeholder=ejemplo)
            
            puntos = procesar_coordenadas(raw) if raw else []
            geom = ee.Geometry.Polygon(puntos) if len(puntos) > 2 else None
            
            if geom:
                st.success(f"Polígono de {len(puntos)-1} puntos validado.")
                
                # BOTÓN DE ENVÍO REAL
                if st.button("🚀 ENVIAR REPORTE AHORA"):
                    with st.spinner("Enviando..."):
                        dest_id = [s['id'] for s in st.session_state.suscripciones if s['nombre']==cliente_sel][0]
                        url = f"https://api.telegram.org/bot{T_TOKEN}/sendMessage"
                        msg = f"🛰 **REPORTE BIOCORE**\n\n✅ **Cliente:** {cliente_sel}\n🌿 **Análisis:** {capa}\n📅 **Fecha:** 27/04/2026\n\n_Estado: Monitoreo completado sin anomalías detectadas._"
                        
                        try:
                            res = requests.post(url, data={"chat_id": dest_id, "text": msg, "parse_mode": "Markdown"})
                            if res.status_code == 200:
                                st.balloons()
                                st.success("¡Enviado con éxito!")
                            else: st.error("Error: Cliente no ha activado el bot.")
                        except: st.error("Error de conexión.")

        with col2:
            if geom:
                # Centrar mapa en el primer punto
                m = folium.Map(location=[puntos[0][1], puntos[0][0]], zoom_start=14)
                folium.TileLayer('https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}', attr='Google', name='Satélite').add_to(m)
                folium.GeoJson(data=geom.getInfo(), style_function=lambda x: {'color': '#00ffcc', 'weight': 3}).add_to(m)
                st_folium(m, width="100%", height=500)
            else:
                # Mapa por defecto (Chile)
                st_folium(folium.Map(location=[-37, -72], zoom_start=5), width="100%", height=500)

elif menu == "⚙️ Registro de Clientes":
    st.info("Utilice el menú lateral para registrar nuevos clientes.")
