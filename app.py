import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from fpdf import FPDF
import json, base64, io, re, requests
import gspread
from google.oauth2.service_account import Credentials
import folium
from streamlit_folium import folium_static

# --- 1. INICIALIZACIÓN CRÍTICA (Evita el borrado al cambiar de pestaña) ---
if 'clientes_db' not in st.session_state:
    st.session_state.clientes_db = {
        "Laguna Señoraza (Laja)": {
            "tipo": "HUMEDAL", 
            "sheet_id": "1x6yAXNNlea3e43rijJu0aqcRpe4oP3BEnzgSgLuG1vU", 
            "pestaña": "ID_CARPETA_1", 
            "umbral": 0.10,
            "coords": [[-37.275, -72.715], [-37.285, -72.715], [-37.285, -72.690], [-37.270, -72.690]]
        },
        "Pascua Lama (Cordillera)": {
            "tipo": "MINERIA", 
            "sheet_id": "1UTrDs939rPlVIR1OTIwbJ6rM3FazgjX43YnJdue-Dmc", 
            "pestaña": "ID_CARPETA_2", 
            "umbral": 0.35,
            "coords": [[-29.316, -70.033], [-29.316, -70.016], [-29.333, -70.016], [-29.333, -70.033]]
        }
    }

# --- 2. CONFIGURACIÓN VISUAL ---
st.set_page_config(page_title="BioCore Intelligence", layout="wide")

def obtener_config(tipo):
    if tipo == "MINERIA":
        return {"indices": ["NDSI", "CLAY", "SWIR"], "colores": ["#00BFFF", "#D2691E", "#708090"], "main": "NDSI"}
    return {"indices": ["NDWI", "SAVI", "SWIR"], "colores": ["#1E90FF", "#32CD32", "#8B4513"], "main": "NDWI"}

# --- 3. NAVEGACIÓN ---
menu = st.sidebar.radio("MENÚ BIOCORE", ["🛡️ Auditoría SEIA", "⚙️ Gestión de Proyectos"])

# --- SECCIÓN AUDITORÍA ---
if menu == "🛡️ Auditoría SEIA":
    st.title("🛡️ Panel de Vigilancia Ambiental")
    
    # Usar los datos guardados en session_state
    if st.session_state.clientes_db:
        opcion = st.selectbox("Seleccione Proyecto:", list(st.session_state.clientes_db.keys()))
        info = st.session_state.clientes_db[opcion]
        conf = obtener_config(info['tipo'])
        
        col1, col2 = st.columns([1, 1.2])
        
        with col1:
            st.metric(f"Proyecto Activo", opcion, delta=info['tipo'])
            if st.button("🚀 EJECUTAR ANÁLISIS"):
                # Aquí iría tu función de cargar_datos_excel
                st.success(f"Analizando {info['tipo']}...")
                # Gráfico histórico simulado con los colores de tu lógica
                st.line_chart(pd.DataFrame({conf['main']: [0.4, 0.42, 0.38, 0.36]}))
        
        with col2:
            st.subheader("📍 Ubicación Geográfica")
            m = folium.Map(location=info['coords'][0], zoom_start=13)
            folium.Polygon(locations=info['coords'], color="#1a3a5a", fill=True).add_to(m)
            folium_static(m)

# --- SECCIÓN GESTIÓN ---
else:
    st.title("⚙️ Registro Técnico de Faenas")
    
    with st.form("nuevo_registro", clear_on_submit=True):
        nombre = st.text_input("Nombre del Proyecto")
        tipo = st.selectbox("Ecosistema", ["MINERIA", "HUMEDAL"])
        sheet = st.text_input("ID del Sheet")
        pesta = st.text_input("Pestaña", value="Hoja 1")
        coord_raw = st.text_area("Coordenadas (Lat, Lon)")
        
        if st.form_submit_button("💾 Guardar y Sincronizar"):
            # Procesar coordenadas
            nums = re.findall(r"[-+]?\d*\.\d+|[-+]?\d+", coord_raw)
            coords = [[float(nums[i]), float(nums[i+1])] for i in range(0, len(nums), 2) if i+1 < len(nums)]
            
            if nombre and coords:
                # GUARDADO DIRECTO EN SESSION STATE
                st.session_state.clientes_db[nombre] = {
                    "tipo": tipo, "sheet_id": sheet, "pestaña": pesta, 
                    "umbral": 0.35 if tipo=="MINERIA" else 0.10,
                    "coords": coords
                }
                st.success(f"✅ Proyecto {nombre} guardado. Ya puedes verlo en la pestaña de Auditoría.")
            else:
                st.error("Faltan datos obligatorios.")

    # Mostrar lo que hay en memoria actualmente
    with st.expander("📂 Ver Proyectos en Vigilancia"):
        st.write(st.session_state.clientes_db)
