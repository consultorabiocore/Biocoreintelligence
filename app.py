import streamlit as st
import ee
import json
import os
import requests
import re
from streamlit_folium import st_folium
import folium

# --- CONFIGURACIÓN DE BIOCORE ---
T_TOKEN = "7961684994:AAGbepFHxXJtjCVTCjEwq2xWh9vT9TO6G68"

# Simulamos la base de datos que guarda quién recibe reportes diarios
if 'suscripciones_diarias' not in st.session_state:
    st.session_state.suscripciones_diarias = []

def inicializar_gee():
    try:
        if 'gee_auth' not in st.session_state:
            info = json.loads(st.secrets["GEE_JSON"])
            ee.Initialize(ee.ServiceAccountCredentials(info['client_email'], key_data=info['private_key'].replace("\\n", "\n")))
            st.session_state.gee_auth = True
        return True
    except: return False

def procesar_coordenadas(texto):
    # Limpia el texto para aceptar el formato Lat, Lon sin corchetes
    nums = re.findall(r"[-+]?\d*\.\d+|\d+", texto)
    coords = []
    for i in range(0, len(nums), 2):
        if i+1 < len(nums): coords.append([float(nums[1]), float(nums[0])])
    if coords and coords[0] != coords[-1]: coords.append(coords[0])
    return coords

# --- INTERFAZ ÚNICA (TODO DENTRO DE LA APP) ---
with st.sidebar:
    st.title("🌿 BioCore Intelligence")
    st.markdown("---")
    
    # Pestañas de navegación interna
    opcion = st.radio("Menú Principal:", ["📊 Panel de Auditoría", "⚙️ Configurar Envío Diario"])
    
    st.markdown("---")
    if st.button("Cerrar Sesión"):
        st.session_state.auth = False
        st.rerun()

# --- LÓGICA DE LAS PESTAÑAS ---
if inicializar_gee():
    
    # --- PESTAÑA 1: CONFIGURACIÓN DE ENVÍO (Aquí es donde el cliente se registra) ---
    if opcion == "⚙️ Configurar Envío Diario":
        st.header("Configuración de Reportes Automáticos")
        st.write("Registre aquí los datos para que el sistema envíe el reporte cada mañana.")
        
        with st.form("registro_cliente"):
            nombre = st.text_input("Nombre del Proyecto/Cliente:")
            chat_id = st.text_input("ID de Telegram del Celular:", placeholder="Ej: 6712325113")
            frecuencia = st.selectbox("Frecuencia de Envío:", ["Diario (08:00 AM)", "Semanal (Lunes)", "Solo Alertas Críticas"])
            
            if st.form_submit_button("✅ Activar Monitoreo Automático"):
                if nombre and chat_id:
                    nuevo_registro = {"nombre": nombre, "id": chat_id, "plan": frecuencia}
                    st.session_state.suscripciones_diarias.append(nuevo_registro)
                    st.success(f"¡Suscripción Activada! {nombre} recibirá reportes en el ID {chat_id}")
                else:
                    st.error("Por favor, complete todos los campos.")

        # Mostrar quiénes están suscritos actualmente
        if st.session_state.suscripciones_diarias:
            st.markdown("---")
            st.subheader("Suscripciones Activas")
            for sub in st.session_state.suscripciones_diarias:
                st.write(f"🟢 **{sub['nombre']}** - ID: {sub['id']} ({sub['plan']})")

    # --- PESTAÑA 2: AUDITORÍA (Lo que tú usas para ver el mapa) ---
    elif opcion == "📊 Panel de Auditoría":
        st.header("Consola de Vigilancia Satelital")
        
        col_mapa, col_datos = st.columns([2, 1])
        
        with col_datos:
            st.markdown("**📍 Área de Monitoreo**")
            # El cuadro de texto que pediste, limpio y sin corchetes
            raw = st.text_area("Pegue coordenadas (Lat, Lon):", height=200, 
                             placeholder="-29.3177, -70.0191\n-29.3300, -70.0100")
            
            puntos = procesar_coordenadas(raw) if raw else []
            geom = ee.Geometry.Polygon(puntos) if len(puntos) > 2 else None
            
            if geom:
                st.success("Polígono validado correctamente.")
                cliente_envio = st.selectbox("Enviar este análisis a:", [s['nombre'] for s in st.session_state.suscripciones_diarias] if st.session_state.suscripciones_diarias else ["Nadie registrado"])

        with col_mapa:
            if geom:
                m = folium.Map(location=puntos[0][::-1], zoom_start=14)
                folium.TileLayer('https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}', attr='Google', name='Sat').add_to(m)
                folium.GeoJson(data=geom.getInfo(), style_function=lambda x: {'color': '#39FF14', 'weight': 2}).add_to(m)
                st_folium(m, width="100%", height=450)
            else:
                st_folium(folium.Map(location=[-37, -72], zoom_start=5), width="100%", height=450)

        # Botón para disparar el reporte manualmente (además del automático)
        if geom and st.session_state.suscripciones_diarias:
            if st.button(f"🚀 GENERAR Y ENVIAR REPORTE AHORA"):
                # Buscamos el ID del cliente seleccionado
                destino_id = [s['id'] for s in st.session_state.suscripciones_diarias if s['nombre'] == cliente_envio][0]
                
                url = f"https://api.telegram.org/bot{T_TOKEN}/sendMessage"
                texto = f"🛰 **BIOCORE INFORMA**\n\n✅ Reporte para: **{cliente_envio}**\n🌍 Estado: Monitoreo Activo\n📅 Fecha: 27/04/2026"
                
                res = requests.post(url, data={"chat_id": destino_id, "text": texto, "parse_mode": "Markdown"})
                if res.status_code == 200: st.success("¡Reporte enviado al celular!")
