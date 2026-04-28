import streamlit as st
import ee
import json
import pandas as pd
import folium
from streamlit_folium import st_folium
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# --- 1. CONFIGURACIÓN E INICIALIZACIÓN ---
st.set_page_config(page_title="BioCore Intelligence", layout="wide")

try:
    creds_dict = json.loads(st.secrets["GEE_JSON"])
    SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    CREDS = Credentials.from_service_account_info(creds_dict, scopes=SCOPE)
    G_CLIENT = gspread.authorize(CREDS)
except Exception as e:
    st.error("❌ Error en Secrets: Configura GEE_JSON en el panel de Streamlit.")
    st.stop()

# --- 2. BASE DE DATOS DE PROYECTOS (Tu estructura fija) ---
CLIENTES_DB = {
    "Pascua Lama (Cordillera)": {
        "sheet_id": "1UTrDs939rPlVIR1OTIwbJ6rM3FazgjX43YnJdue-Dmc",
        "pestaña": "ID_CARPETA_2",
        "coords": [-29.32, -70.02]
    }
    # Aquí vas agregando tus otros proyectos reales
}

# --- 3. FUNCIONES CORE ---

def obtener_datos(sheet_id, pestaña):
    """Extrae datos de Google Sheets para auditoría y reportes"""
    try:
        hoja = G_CLIENT.open_by_key(sheet_id).worksheet(pestaña)
        records = hoja.get_all_records()
        df = pd.DataFrame(records)
        if not df.empty:
            df['Fecha'] = pd.to_datetime(df['Fecha'], errors='coerce')
            # Blindaje contra errores de formato
            for col in ["NDSI", "NDWI", "SWIR", "Polvo", "Deficit"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            return df.sort_values('Fecha').dropna(subset=['Fecha'])
        return pd.DataFrame()
    except:
        return pd.DataFrame()

# --- 4. INTERFAZ (SIDEBAR ORIGINAL) ---

with st.sidebar:
    st.title("🌿 BioCore Admin")
    opcion = st.radio("Ir a:", ["📊 Panel de Auditoría", "➕ Registrar Proyecto"])
    st.markdown("---")
    
    if opcion == "📊 Panel de Auditoría":
        proyecto_sel = st.selectbox("Proyecto Activo:", list(CLIENTES_DB.keys()))
        dias_ver = st.slider("Días de historial:", 5, 60, 15)
    
    st.markdown("---")
    st.caption("BioCore Intelligence © 2026")

# --- 5. MÓDULOS ---

if opcion == "➕ Registrar Proyecto":
    st.header("Registro de Nuevo Cliente")
    st.write("Al crear un proyecto, se generará una base de datos en Google Drive automáticamente.")
    
    with st.form("form_nuevo"):
        nuevo_nom = st.text_input("Nombre del Proyecto")
        # Selector de tipo de proyecto si lo necesitas en el futuro
        tipo_proy = st.selectbox("Tipo de Proyecto", ["Minería", "Forestal", "Agrícola", "Otro"])
        submit = st.form_submit_button("Crear Base de Datos")
        
        if submit and nuevo_nom:
            st.info("⚠️ Debido a límites de cuota de Google Cloud, cree el Excel en su Drive y compártalo con la cuenta de servicio.")

elif opcion == "📊 Panel de Auditoría":
    info = CLIENTES_DB[proyecto_sel]
    st.header(f"Vigilancia Satelital: {proyecto_sel}")
    
    if st.button("🔄 Sincronizar Datos"):
        with st.spinner("Conectando con la base de datos..."):
            df = obtener_datos(info["sheet_id"], info["pestaña"])
            if not df.empty:
                st.session_state[f"df_{proyecto_sel}"] = df
            else:
                st.error("No se encontraron datos en el Excel.")

    if f"df_{proyecto_sel}" in st.session_state:
        df = st.session_state[f"df_{proyecto_sel}"]
        
        col1, col2 = st.columns([1, 2])
        
        with col1:
            st.subheader("Estado Actual")
            ultimos = df.tail(1)
            if not ultimos.empty:
                for col in ["NDSI", "NDWI", "SWIR"]:
                    if col in ultimos.columns:
                        val = ultimos[col].values[0]
                        st.metric(label=col, value=f"{val:.3f}" if pd.notnull(val) else "N/A")
            
            st.markdown("---")
            if st.button("📄 Generar Informe para Cliente"):
                st.toast("Generando informe técnico con gráficos de tendencias...")

        with col2:
            st.subheader("Registros Recientes")
            st.dataframe(df.tail(dias_ver), use_container_width=True)

    # Mapa siempre al final
    st.markdown("---")
    m = folium.Map(location=info["coords"], zoom_start=14)
    folium.TileLayer('https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}', attr='Google', name='Sat').add_to(m)
    folium.Marker(info["coords"], popup=proyecto_sel).add_to(m)
    st_folium(m, width="100%", height=400, key=f"map_{proyecto_sel}")
