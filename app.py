import streamlit as st
import ee
import json
import requests
import re
import os
import base64
import pandas as pd
import matplotlib.pyplot as plt
from fpdf import FPDF
from streamlit_folium import st_folium
import folium
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# --- 1. CONFIGURACIÓN E INICIALIZACIÓN ---
st.set_page_config(page_title="BioCore Intelligence", layout="wide")

# Credenciales desde Secrets
try:
    creds_dict = json.loads(st.secrets["GEE_JSON"])
    # Añadimos 'drive' explícitamente para evitar el error 403 al crear archivos
    SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    CREDS = Credentials.from_service_account_info(creds_dict, scopes=SCOPE)
    G_CLIENT = gspread.authorize(CREDS)
except Exception as e:
    st.error("❌ Error en Secrets: Configura GEE_JSON en el panel de Streamlit.")
    st.stop()

# --- 2. BASE DE DATOS DE PROYECTOS ---
CLIENTES_DB = {
    "Pascua Lama (Cordillera)": {
        "sheet_id": "1UTrDs939rPlVIR1OTIwbJ6rM3FazgjX43YnJdue-Dmc",
        "pestaña": "ID_CARPETA_2",
        "coords": [-29.32, -70.02]
    },
    "Laguna Señoraza (Laja)": {
        "sheet_id": "1x6yAXNNlea3e43rijJu0aqcRpe4oP3BEnzgSgLuG1vU",
        "pestaña": "ID_CARPETA_1",
        "coords": [-37.2713, -72.7095]
    }
}

# --- 3. FUNCIONES CORE ---

def crear_excel_automatico(nombre):
    """Crea un nuevo Google Sheet y devuelve su ID"""
    try:
        nueva_hoja = G_CLIENT.create(f"BioCore_DB_{nombre}")
        hoja_activa = nueva_hoja.get_worksheet(0)
        hoja_activa.append_row(["Fecha", "NDSI", "NDWI", "SWIR", "Polvo", "Deficit"])
        return nueva_hoja.id
    except Exception as e:
        # Si falla por cuota, devolvemos el error detallado
        return f"Error de Google: {str(e)}"

def obtener_datos(sheet_id, pestaña):
    """Extrae datos de Google Sheets y los convierte a DataFrame limpio"""
    try:
        hoja = G_CLIENT.open_by_key(sheet_id).worksheet(pestaña)
        records = hoja.get_all_records()
        df = pd.DataFrame(records)
        if not df.empty:
            df['Fecha'] = pd.to_datetime(df['Fecha'], errors='coerce')
            # LIMPIEZA: Aseguramos que los índices sean números para evitar el ValueError en Matplotlib
            for col in ["NDSI", "NDWI", "SWIR"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            return df.sort_values('Fecha').dropna(subset=['Fecha'])
        return pd.DataFrame()
    except:
        return pd.DataFrame()

# --- 4. INTERFAZ (SIDEBAR) ---

with st.sidebar:
    st.title("🌿 BioCore Admin")
    opcion = st.radio("Ir a:", ["📊 Panel de Auditoría", "➕ Registrar Proyecto"])
    st.markdown("---")
    
    if opcion == "📊 Panel de Auditoría":
        proyecto_sel = st.selectbox("Proyecto Activo:", list(CLIENTES_DB.keys()))
        dias_ver = st.slider("Días de historial:", 5, 60, 15)
    
    st.markdown("---")
    st.caption("BioCore Intelligence © 2026")

# --- 5. MÓDULOS DE LA APP ---

if opcion == "➕ Registrar Proyecto":
    st.header("Registro de Nuevo Cliente")
    st.write("Al crear un proyecto, se generará una base de datos en Google Drive automáticamente.")
    
    with st.form("form_nuevo"):
        nuevo_nom = st.text_input("Nombre del Proyecto (ej: Mina El Teniente)")
        submit = st.form_submit_button("Crear Base de Datos")
        
        if submit and nuevo_nom:
            with st.spinner("Generando archivo en la nube..."):
                nuevo_id = crear_excel_automatico(nuevo_nom)
                if "Error" in str(nuevo_id):
                    st.error(f"❌ {nuevo_id}")
                    st.info("Nota: Si es un error de 'Quota', intenta crear el Excel manualmente y compartirlo con la cuenta de servicio.")
                else:
                    st.success(f"✅ ¡Éxito! Base de datos creada.")
                    st.code(f"ID del Sheet: {nuevo_id}", language="text")

elif opcion == "📊 Panel de Auditoría":
    info = CLIENTES_DB[proyecto_sel]
    st.header(f"Vigilancia Satelital: {proyecto_sel}")
    
    if st.button("🔄 Sincronizar Datos"):
        with st.spinner("Leyendo Google Sheets..."):
            df = obtener_datos(info["sheet_id"], info["pestaña"])
            if not df.empty:
                st.session_state[f"df_{proyecto_sel}"] = df
            else:
                st.error("No se encontraron datos válidos (revise si el Excel tiene números).")

    if f"df_{proyecto_sel}" in st.session_state:
        df = st.session_state[f"df_{proyecto_sel}"]
        
        col1, col2 = st.columns([1, 2])
        
        with col1:
            st.subheader("Estado Actual")
            ultimos = df.tail(1)
            if not ultimos.empty:
                for col in ["NDSI", "NDWI", "SWIR"]:
                    if col in ultimos.columns:
                        st.metric(label=col, value=f"{ultimos[col].values[0]:.3f}")
            
            st.markdown("---")
            if st.button("📄 Generar Informe para Cliente"):
                st.toast("Preparando PDF técnico...")

        with col2:
            st.subheader("Análisis de Tendencias")
            if not df.empty:
                fig, ax = plt.subplots(figsize=(10, 5))
                # Graficamos solo si son datos numéricos
                for col in ["NDSI", "NDWI", "SWIR"]:
                    if col in df.columns:
                        ax.plot(df["Fecha"].tail(dias_ver), df[col].tail(dias_ver), marker='o', label=col)
                ax.legend()
                ax.grid(True, alpha=0.3)
                plt.xticks(rotation=30)
                st.pyplot(fig)

    st.markdown("---")
    m = folium.Map(location=info["coords"], zoom_start=14)
    folium.TileLayer('https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}', attr='Google', name='Sat').add_to(m)
    folium.Marker(info["coords"], popup=proyecto_sel).add_to(m)
    st_folium(m, width="100%", height=400, key=f"map_{proyecto_sel}")
