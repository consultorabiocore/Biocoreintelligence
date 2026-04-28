import streamlit as st
import ee
import json
import os
import base64
import pandas as pd
import matplotlib.pyplot as plt
import gspread
import folium
from google.oauth2.service_account import Credentials
from streamlit_folium import st_folium

# --- 1. CONFIGURACIÓN E INICIALIZACIÓN ---
st.set_page_config(page_title="BioCore Intelligence", layout="wide", page_icon="🌿")

def inicializar_conexiones():
    try:
        # Carga de credenciales desde Secrets de Streamlit
        creds_dict = json.loads(st.secrets["GEE_JSON"])
        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive",
            "https://www.googleapis.com/auth/earthengine"
        ]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        
        # Inicializar Google Sheets
        gc = gspread.authorize(creds)
        
        # Inicializar Earth Engine
        ee.Initialize(creds)
        
        return gc, creds_dict["client_email"]
    except Exception as e:
        st.error(f"❌ Error de conexión: {e}")
        st.stop()

gc, service_account_email = inicializar_conexiones()

# --- 2. BASE DE DATOS DE PROYECTOS (ESTÁTICA) ---
# Aquí puedes ir agregando los IDs que la App te genere
CLIENTES_DB = {
    "Pascua Lama (Cordillera)": {
        "id": "1UTrDs939rPlVIR1OTIwbJ6rM3FazgjX43YnJdue-Dmc",
        "hoja": "ID_CARPETA_2",
        "coords": [-29.32, -70.02]
    },
    "Laguna Señoraza (Laja)": {
        "id": "1x6yAXNNlea3e43rijJu0aqcRpe4oP3BEnzgSgLuG1vU",
        "hoja": "ID_CARPETA_1",
        "coords": [-37.27, -72.70]
    }
}

# --- 3. FUNCIONES DE GESTIÓN ---

def crear_base_datos_cliente(nombre):
    """Crea un Google Sheet, lo configura y devuelve ID y Link"""
    try:
        sh = gc.create(f"BioCore_DB_{nombre}")
        worksheet = sh.get_worksheet(0)
        # Encabezados técnicos que usan tus scripts de monitoreo
        worksheet.append_row(["Fecha", "NDSI", "NDWI", "SWIR", "Polvo", "Deficit"])
        return sh.id, sh.url
    except Exception as e:
        return None, str(e)

def cargar_datos(sheet_id, pestaña):
    """Extrae datos de la nube"""
    try:
        sh = gc.open_by_key(sheet_id).worksheet(pestaña)
        df = pd.DataFrame(sh.get_all_records())
        if not df.empty:
            df['Fecha'] = pd.to_datetime(df['Fecha'], errors='coerce')
            return df.sort_values('Fecha')
        return df
    except:
        return pd.DataFrame()

# --- 4. INTERFAZ DE USUARIO ---

with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2950/2950137.png", width=80) # Icono genérico
    st.title("BioCore Intelligence")
    menu = st.radio("Navegación:", ["📊 Auditoría Satelital", "➕ Nuevo Proyecto"])
    st.markdown("---")
    st.caption(f"Conectado como: {service_account_email}")

# --- MÓDULO: NUEVO PROYECTO ---
if menu == "➕ Nuevo Proyecto":
    st.header("Registrar Nuevo Cliente")
    st.info("Esta sección crea una base de datos en Google Drive para el nuevo polígono de estudio.")
    
    with st.form("registro_cliente"):
        nombre_p = st.text_input("Nombre del Proyecto (ej: Los Bronces)")
        crear = st.form_submit_button("Generar Infraestructura Cloud")
        
        if crear and nombre_p:
            with st.spinner("Creando archivos en Google Drive..."):
                nuevo_id, nueva_url = crear_base_datos_cliente(nombre_p)
                if nuevo_id:
                    st.success(f"✅ ¡Proyecto '{nombre_p}' listo!")
                    st.markdown(f"**ID del Sheet:** `{nuevo_id}`")
                    st.link_button("📂 Abrir Base de Datos", nueva_url)
                    st.warning("RECUERDA: Agregue este ID a su script de monitoreo automático.")
                else:
                    st.error(f"Error: {nueva_url}")

# --- MÓDULO: AUDITORÍA ---
else:
    st.header("Panel de Vigilancia Ambiental")
    proyecto = st.selectbox("Seleccione Proyecto:", list(CLIENTES_DB.keys()))
    
    conf = CLIENTES_DB[proyecto]
    
    if st.button("🔄 Sincronizar Datos en Tiempo Real"):
        with st.spinner("Consultando base de datos..."):
            df_cl = cargar_datos(conf["id"], conf["hoja"])
            if not df_cl.empty:
                st.session_state[f"df_{proyecto}"] = df_cl
                st.success("Sincronización completa.")
            else:
                st.warning("No hay datos registrados aún para este proyecto.")

    # Mostrar visualizaciones si hay datos cargados
    if f"df_{proyecto}" in st.session_state:
        df = st.session_state[f"df_{proyecto}"]
        
        tab1, tab2 = st.tabs(["📉 Tendencias", "📋 Tabla de Datos"])
        
        with tab1:
            fig, ax = plt.subplots(figsize=(10, 4))
            indices = [c for c in ["NDSI", "NDWI", "SWIR"] if c in df.columns]
            for idx in indices:
                ax.plot(df['Fecha'], df[idx], marker='o', label=idx)
            ax.set_title(f"Evolución de Índices - {proyecto}")
            ax.legend()
            plt.xticks(rotation=45)
            st.pyplot(fig)
            
        with tab2:
            st.dataframe(df.tail(20), use_container_width=True)

    # Mapa de ubicación
    st.markdown("---")
    st.subheader("Localización del Área de Estudio")
    mapa = folium.Map(location=conf["coords"], zoom_start=13)
    folium.TileLayer('https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}', attr='Google', name='Sat').add_to(mapa)
    folium.Marker(conf["coords"], popup=proyecto).add_to(mapa)
    st_folium(mapa, width="100%", height=400, key=f"map_{proyecto}")
