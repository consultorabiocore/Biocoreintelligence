import streamlit as st
import ee
import json
import os
import pandas as pd
import matplotlib.pyplot as plt
import gspread
import folium
from google.oauth2.service_account import Credentials
from streamlit_folium import st_folium

# --- 1. CONFIGURACIÓN INICIAL ---
st.set_page_config(page_title="BioCore Intelligence", layout="wide", page_icon="🌿")

def inicializar_conexiones():
    try:
        if "GEE_JSON" not in st.secrets:
            st.error("Configura el secreto GEE_JSON en Streamlit Cloud.")
            st.stop()
        
        creds_dict = json.loads(st.secrets["GEE_JSON"])
        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive"
        ]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        gc = gspread.authorize(creds)
        return gc, creds_dict["client_email"]
    except Exception as e:
        st.error(f"Error crítico de conexión: {e}")
        st.stop()

gc, service_email = inicializar_conexiones()

# --- 2. GESTIÓN DE DATOS ---

def crear_excel_desde_app(nombre_proyecto):
    """Crea el Excel y añade cabeceras para que no esté vacío"""
    try:
        sh = gc.create(f"BioCore_DB_{nombre_proyecto}")
        ws = sh.get_worksheet(0)
        # Añadimos una fila inicial para que pandas no falle al leer
        ws.append_row(["Fecha", "NDSI", "NDWI", "SWIR", "Polvo", "Deficit"])
        return sh.id, sh.url
    except Exception as e:
        return None, str(e)

def obtener_dataframe(sheet_id):
    """Lee el Excel y limpia datos no numéricos para evitar errores de Matplotlib"""
    try:
        sh = gc.open_by_key(sheet_id).get_worksheet(0)
        lista_datos = sh.get_all_records()
        if not lista_datos:
            return pd.DataFrame()
            
        df = pd.DataFrame(lista_datos)
        # Limpieza crucial: Convertir a fecha y números
        df['Fecha'] = pd.to_datetime(df['Fecha'], errors='coerce')
        for col in ["NDSI", "NDWI", "SWIR", "Polvo", "Deficit"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        return df.dropna(subset=['Fecha']) # Elimina filas sin fecha válida
    except:
        return pd.DataFrame()

# --- 3. INTERFAZ ---

with st.sidebar:
    st.title("🌿 BioCore Admin")
    menu = st.radio("Menú:", ["➕ Crear Nuevo Proyecto", "📊 Ver Auditoría"])
    st.markdown("---")
    st.caption(f"Cuenta activa: {service_email}")

# --- MÓDULO A: CREAR EXCEL ---
if menu == "➕ Crear Nuevo Proyecto":
    st.header("Generar Nueva Base de Datos")
    st.write("Si no hay ningún Excel, créalo aquí primero.")
    
    with st.form("crear_forma"):
        nombre = st.text_input("Nombre del Cliente/Proyecto")
        enviar = st.form_submit_button("Crear Excel en Google Drive")
        
        if enviar and nombre:
            with st.spinner("Creando archivo..."):
                id_generado, url_generada = crear_excel_desde_app(nombre)
                if id_generado:
                    st.success(f"¡Excel creado para {nombre}!")
                    st.markdown(f"**ID:** `{id_generado}`")
                    st.link_button("📂 Abrir Hoja de Cálculo", url_generada)
                    st.info("Copia el ID arriba para visualizarlo en el panel de Auditoría.")
                else:
                    st.error(f"No se pudo crear: {url_generada}")

# --- MÓDULO B: AUDITORÍA ---
else:
    st.header("Panel de Visualización")
    sheet_id_input = st.text_input("Pega el ID del Excel del cliente aquí:")
    
    if sheet_id_input:
        if st.button("Sincronizar Datos"):
            df = obtener_dataframe(sheet_id_input)
            if not df.empty:
                st.session_state["datos_actuales"] = df
                st.success("Datos cargados correctamente.")
            else:
                st.warning("El Excel existe pero no tiene datos numéricos aún.")

        if "datos_actuales" in st.session_state:
            df_plot = st.session_state["datos_actuales"]
            
            # GRAFICAR (Blindado contra errores ValueError)
            if not df_plot.empty and len(df_plot) > 0:
                fig, ax = plt.subplots(figsize=(10, 4))
                for col in ["NDSI", "NDWI", "SWIR"]:
                    if col in df_plot.columns:
                        ax.plot(df_plot['Fecha'], df_plot[col], marker='o', label=col)
                
                ax.legend()
                ax.grid(True, alpha=0.3)
                plt.xticks(rotation=35)
                st.pyplot(fig)
                st.dataframe(df_plot)
            else:
                st.info("Esperando datos del monitor satelital...")
