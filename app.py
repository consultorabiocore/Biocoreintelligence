import streamlit as st
import ee
import folium
from streamlit_folium import folium_static
import json
import pandas as pd
import requests
from datetime import datetime
from supabase import create_client, Client

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="BioCore Intelligence V5", layout="wide")

# Intento de conexión a Supabase con validación
try:
    url: str = st.secrets["connections"]["supabase"]["url"]
    key: str = st.secrets["connections"]["supabase"]["key"]
    supabase: Client = create_client(url, key)
except Exception as e:
    st.error(f"❌ Error de conexión a Supabase: {e}")
    st.stop()

# --- 2. CARGA DE DATOS ---
# Forzamos la lectura de la tabla de usuarios
try:
    response = supabase.table("usuarios").select("*").execute()
    proyectos = response.data
except Exception as e:
    st.error(f"❌ No se pudo leer la tabla 'usuarios': {e}")
    proyectos = []

# --- 3. INTERFAZ ---
st.title("🛰️ BioCore Intelligence V5")

t1, t2, t3 = st.tabs(["🚀 VIGILANCIA", "📊 EXCEL/HISTORIAL", "⚙️ CONFIG"])

with t1:
    if not proyectos:
        st.warning("⚠️ La base de datos está vacía o no se detectan proyectos.")
        if st.button("Simular Proyecto (Pascua Lama)"):
            # Esto es solo para que veas algo si la base de datos falla
            proyectos = [{
                "Proyecto": "Pascua Lama (Test)",
                "Tipo": "GLACIAR",
                "telegram_id": "TU_ID_AQUÍ",
                "Coordenadas": '{"type":"Polygon","coordinates":[[[-70.0, -29.3],[-70.01, -29.3],[-70.01, -29.31],[-70.0, -29.31],[-70.0, -29.3]]]}'
            }]
            st.rerun()
    else:
        for p in proyectos:
            with st.expander(f"📍 {p['Proyecto']}", expanded=True):
                col_map, col_info = st.columns([3, 1])
                with col_map:
                    # Aquí va la función de dibujar_mapa que ya tienes
                    st.info("Mapa cargando...") 
                with col_info:
                    st.write(f"**Perfil:** {p.get('Tipo')}")
                    if st.button("Disparar Auditoría", key=f"btn_{p['Proyecto']}"):
                        st.write("Procesando...")

with t2:
    st.subheader("Historial de Reportes")
    try:
        hist_res = supabase.table("historial_reportes").select("*").execute()
        if hist_res.data:
            df_hist = pd.DataFrame(hist_res.data)
            st.dataframe(df_hist)
            st.download_button("Descargar Excel", df_hist.to_csv(), "BioCore_Report.csv")
        else:
            st.info("No hay registros en el historial todavía.")
    except Exception as e:
        st.error(f"Error al cargar historial: {e}")

with t3:
    st.subheader("Parámetros del Sistema")
    st.json(st.session_state.get('PERFILES', {}))
