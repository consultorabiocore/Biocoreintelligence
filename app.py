import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from fpdf import FPDF
import json, base64, io, re, requests
import gspread
from google.oauth2.service_account import Credentials
import folium
from streamlit_folium import folium_static

# --- 1. INICIALIZACIÓN Y PERSISTENCIA ---
if 'clientes_db' not in st.session_state:
    st.session_state.clientes_db = {
        "Laguna Señoraza (Laja)": {
            "tipo": "HUMEDAL", 
            "sheet_id": "1x6yAXNNlea3e43rijJu0aqcRpe4oP3BEnzgSgLuG1vU", 
            "pestaña": "ID_CARPETA_1", "umbral": 0.10,
            "coords": [[-37.275, -72.715], [-37.285, -72.715], [-37.285, -72.690], [-37.270, -72.690]]
        },
        "Pascua Lama (Cordillera)": {
            "tipo": "MINERIA", 
            "sheet_id": "1UTrDs939rPlVIR1OTIwbJ6rM3FazgjX43YnJdue-Dmc", 
            "pestaña": "ID_CARPETA_2", "umbral": 0.35,
            "coords": [[-29.316, -70.033], [-29.316, -70.016], [-29.333, -70.016], [-29.333, -70.033]]
        }
    }

st.set_page_config(page_title="BioCore Intelligence", layout="wide")

# --- 2. FUNCIONES DE COMUNICACIÓN (TELEGRAM) ---
def enviar_a_telegram(mensaje):
    try:
        token = st.secrets["TELEGRAM_TOKEN"]
        chat_id = st.secrets["TELEGRAM_CHAT_ID"]
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": chat_id, "text": mensaje, "parse_mode": "Markdown"}
        requests.post(url, json=payload)
    except Exception as e:
        st.error(f"Error enviando a Telegram: {e}")

# --- 3. PROCESAMIENTO DE DATOS ---
def obtener_config(tipo):
    if tipo == "MINERIA":
        return {"indices": ["NDSI", "CLAY", "SWIR"], "colores": ["#00BFFF", "#D2691E", "#708090"], "main": "NDSI"}
    return {"indices": ["NDWI", "SAVI", "SWIR"], "colores": ["#1E90FF", "#32CD32", "#8B4513"], "main": "NDWI"}

# --- 4. INTERFAZ DE NAVEGACIÓN ---
menu = st.sidebar.radio("MENÚ BIOCORE", ["🛡️ Auditoría SEIA", "⚙️ Gestión"])

if menu == "🛡️ Auditoría SEIA":
    st.title("🛡️ Panel de Vigilancia Ambiental")
    
    if st.session_state.clientes_db:
        opcion = st.selectbox("Seleccione Proyecto:", list(st.session_state.clientes_db.keys()))
        info = st.session_state.clientes_db[opcion]
        conf = obtener_config(info['tipo'])
        
        col1, col2 = st.columns([1, 1.2])
        
        with col1:
            if st.button("🚀 EJECUTAR AUDITORÍA Y NOTIFICAR"):
                # Simulación de carga (aquí conectas tu función cargar_datos_excel)
                val_simulado = 0.42 if info['tipo'] == "MINERIA" else 0.15
                estado = "🟢 BAJO CONTROL" if val_simulado >= info['umbral'] else "🔴 ALERTA TÉCNICA"
                
                # 1. Notificación Telegram
                reporte_msg = (
                    f"🛰 **BIOCORE: REPORTE DE VIGILANCIA**\n"
                    f"**Proyecto:** {opcion}\n"
                    f"**Ecosistema:** {info['tipo']}\n"
                    f"**Valor {conf['main']}:** `{val_simulado:.3f}`\n"
                    f"──────────────────\n"
                    f"✅ **ESTADO GLOBAL:** {estado}\n"
                    f"📝 Diagnóstico generado desde panel administrativo."
                )
                enviar_a_telegram(reporte_msg)
                st.success("Notificación enviada a Telegram.")
                
                # 2. Visualización
                st.line_chart(pd.DataFrame({conf['main']: [0.4, 0.45, val_simulado]}))
                
        with col2:
            st.subheader("📍 Ubicación del Polígono")
            m = folium.Map(location=info['coords'][0], zoom_start=13)
            folium.Polygon(locations=info['coords'], color="#1a3a5a", fill=True).add_to(m)
            folium_static(m)

else:
    # (Sección de Gestión para añadir nuevos proyectos)
    st.title("⚙️ Registro de Faenas")
    with st.form("nuevo_proy"):
        nom = st.text_input("Nombre")
        tipo = st.selectbox("Ecosistema", ["MINERIA", "HUMEDAL"])
        if st.form_submit_button("Guardar"):
            st.session_state.clientes_db[nom] = {"tipo": tipo, "coords": [[-29.3, -70.0]]} # Simplificado
            st.success("Guardado correctamente.")
