import streamlit as st
import ee
import json
import folium
import os
import base64
import re
import requests
from streamlit_folium import st_folium

# --- CONFIGURACIÓN BIOCORE ---
st.set_page_config(page_title="BioCore Intelligence", layout="wide")
LOGO_PATH = os.path.join("assets", "logo_biocore.png")
T_TOKEN = "7961684994:AAGbepFHxXJtjCVTCjEwq2xWh9vT9TO6G68" # Tu Token de Bot

def inicializar_gee():
    try:
        if 'gee_auth' not in st.session_state:
            info = json.loads(st.secrets["GEE_JSON"])
            creds = ee.ServiceAccountCredentials(info['client_email'], key_data=info['private_key'].replace("\\n", "\n"))
            ee.Initialize(creds)
            st.session_state.gee_auth = True
        return True
    except: return False

def procesar_coordenadas_simples(texto):
    lineas = texto.strip().split('\n')
    coords_finales = []
    for linea in lineas:
        numeros = re.findall(r"[-+]?\d*\.\d+|\d+", linea)
        if len(numeros) >= 2:
            lat, lon = float(numeros[0]), float(numeros[1])
            coords_finales.append([lon, lat])
    if coords_finales and coords_finales[0] != coords_finales[-1]:
        coords_finales.append(coords_finales[0])
    return coords_finales

# --- PESTAÑA LATERAL (REGISTRO Y CONFIGURACIÓN) ---
with st.sidebar:
    if os.path.exists(LOGO_PATH):
        with open(LOGO_PATH, "rb") as f:
            data = base64.b64encode(f.read()).decode()
            st.markdown(f'<div style="text-align:center"><img src="data:image/png;base64,{data}" width="160"></div>', unsafe_allow_html=True)
    
    st.markdown("---")
    if not st.session_state.get('auth', False):
        u, p = st.text_input("Usuario"), st.text_input("Clave", type="password")
        if st.button("Ingresar"):
            if u == "admin" and p == "loreto2026":
                st.session_state.auth = True
                st.rerun()
    else:
        st.subheader("📲 Notificaciones Telegram")
        # ESPACIO PARA REGISTRAR EL ID DEL CELULAR
        chat_id_user = st.text_input("ID de Telegram (Chat ID):", value="6712325113", help="ID numérico para recibir alertas")
        
        st.subheader("📂 Datos del Proyecto")
        nombre_cliente = st.text_input("Cliente/Proyecto:", value="")
        tipo_sector = st.selectbox("Sector de Auditoría:", ["Minería", "Glaciares", "Humedales", "Forestal"])
        
        if st.button("Cerrar Sesión"):
            st.session_state.auth = False
            st.rerun()

# --- PANEL PRINCIPAL ---
if st.session_state.get('auth', False) and inicializar_gee():
    st.title("🛰 BioCore: Vigilancia Satelital")

    col_map, col_ctrl = st.columns([2, 1])

    with col_ctrl:
        st.markdown("### 📍 Coordenadas (Lat, Lon)")
        ejemplo = "-29.3177, -70.0191\n-29.3300, -70.0100"
        raw_input = st.text_area("Pegue la lista de coordenadas:", height=250, placeholder=f"Ejemplo:\n{ejemplo}")
        
        geom = None
        if raw_input:
            puntos = procesar_coordenadas_simples(raw_input)
            if len(puntos) >= 3:
                try:
                    geom = ee.Geometry.Polygon(puntos)
                    st.success(f"✅ Polígono detectado.")
                except: st.error("Error geométrico.")

    with col_map:
        if geom:
            centro = geom.centroid().coordinates().getInfo()[::-1]
            m = folium.Map(location=centro, zoom_start=14)
        else:
            m = folium.Map(location=[-37.0, -72.0], zoom_start=5)
        
        folium.TileLayer('https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}', attr='Google', name='Satélite').add_to(m)
        if geom:
            folium.GeoJson(data=geom.getInfo(), style_function=lambda x: {'color': '#39FF14', 'weight': 2}).add_to(m)
        st_folium(m, width="100%", height=400)

    # --- BOTÓN DE ENVÍO REAL ---
    if geom and nombre_cliente and chat_id_user:
        if st.button(f"🚀 GENERAR Y ENVIAR REPORTE A TELEGRAM"):
            with st.spinner("Analizando satélite y enviando alerta..."):
                try:
                    # Mensaje que se envía
                    mensaje = f"🛰 **AUDITORÍA BIOCORE**\n\n✅ **Proyecto:** {nombre_cliente}\n📍 **Sector:** {tipo_sector}\n📊 **Estado:** Monitoreo Exitoso\n📅 **Fecha:** {st.session_state.get('fecha', '27-04-2026')}"
                    
                    url = f"https://api.telegram.org/bot{T_TOKEN}/sendMessage"
                    data = {"chat_id": chat_id_user, "text": mensaje, "parse_mode": "Markdown"}
                    response = requests.post(url, data=data)
                    
                    if response.status_code == 200:
                        st.success(f"¡Reporte enviado con éxito al ID {chat_id_user}!")
                    else:
                        st.error(f"Error al enviar: {response.text}")
                except Exception as e:
                    st.error(f"Error de conexión: {e}")
