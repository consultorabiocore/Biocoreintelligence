import streamlit as st
import ee
import json
import pandas as pd
import matplotlib.pyplot as plt
import gspread
import folium
from google.oauth2.service_account import Credentials
from streamlit_folium import st_folium
from datetime import datetime

# --- 1. CONFIGURACIÓN ESTÉTICA Y CONEXIÓN ---
st.set_page_config(page_title="BioCore Intelligence", layout="wide", page_icon="🌿")

# Inyectar un poco de CSS para que se vea premium
st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    </style>
    """, unsafe_allow_html=True)

def inicializar_todo():
    try:
        creds_dict = json.loads(st.secrets["GEE_JSON"])
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        gc = gspread.authorize(creds)
        return gc, creds_dict["client_email"]
    except Exception as e:
        st.error(f"Error de inicialización: {e}")
        st.stop()

gc, email_app = inicializar_todo()

# --- 2. BASE DE DATOS DE PROYECTOS (Tu estructura original) ---
CLIENTES_DB = {
    "Laguna Señoraza (Laja)": {
        "id": "1x6yAXNNlea3e43rijJu0aqcRpe4oP3BEnzgSgLuG1vU",
        "pestaña": "ID_CARPETA_1", # El nombre que me diste
        "coords": [-37.2713, -72.7095]
    },
    "Pascua Lama (Cordillera)": {
        "id": "1UTrDs939rPlVIR1OTIwbJ6rM3FazgjX43YnJdue-Dmc",
        "pestaña": "Hoja 1",
        "coords": [-29.32, -70.02]
    }
}

# --- 3. BARRA LATERAL PROFESIONAL ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/892/892903.png", width=100)
    st.title("BioCore Intelligence")
    st.subheader("Consultoría Ambiental")
    menu = st.radio("Navegación", ["📊 Dashboard de Auditoría", "➕ Gestión de Clientes"])
    st.markdown("---")
    st.info(f"**App ID:** {email_app}")

# --- MÓDULO 1: AUDITORÍA (EL DASHBOARD COMPLETO) ---
if menu == "📊 Dashboard de Auditoría":
    col_t1, col_t2 = st.columns([3, 1])
    with col_t1:
        proyecto = st.selectbox("Seleccione el Área de Estudio", list(CLIENTES_DB.keys()))
    with col_t2:
        st.write("") # Espaciador
        sync = st.button("🔄 Sincronizar Satélite")

    conf = CLIENTES_DB[proyecto]

    if sync:
        with st.spinner("Conectando con la base de datos en la nube..."):
            try:
                sh = gc.open_by_key(conf["id"]).worksheet(conf["pestaña"])
                df = pd.DataFrame(sh.get_all_records())
                if not df.empty:
                    # Limpieza de datos profesional
                    df['Fecha'] = pd.to_datetime(df['Fecha'], errors='coerce')
                    for c in ["NDSI", "NDWI", "SWIR", "Polvo", "Deficit"]:
                        if c in df.columns:
                            df[c] = pd.to_numeric(df[c], errors='coerce')
                    st.session_state[f"data_{proyecto}"] = df.dropna(subset=['Fecha'])
                else:
                    st.warning("El archivo está conectado pero no tiene registros.")
            except Exception as e:
                st.error(f"Error de acceso: {e}")

    if f"data_{proyecto}" in st.session_state:
        df_view = st.session_state[f"data_{proyecto}"]
        
        # FILA 1: MÉTRICAS CLAVE
        m1, m2, m3, m4 = st.columns(4)
        ultimo = df_view.iloc[-1]
        m1.metric("Última Fecha", ultimo['Fecha'].strftime('%d/%m/%Y'))
        m2.metric("NDWI (Agua)", f"{ultimo.get('NDWI', 0):.3f}")
        m3.metric("NDSI (Nieve)", f"{ultimo.get('NDSI', 0):.3f}")
        m4.metric("SWIR (Humedad)", f"{ultimo.get('SWIR', 0):.3f}")

        # FILA 2: GRÁFICOS Y MAPA
        tab_graf, tab_map, tab_data = st.tabs(["📉 Tendencias Temporales", "🌍 Ubicación Espacial", "📑 Datos Crudos"])
        
        with tab_graf:
            fig, ax = plt.subplots(figsize=(12, 5))
            for idx in ["NDSI", "NDWI", "SWIR"]:
                if idx in df_view.columns:
                    ax.plot(df_view['Fecha'], df_view[idx], marker='o', label=idx, linewidth=2)
            ax.set_title(f"Evolución Biofísica - {proyecto}", fontsize=14)
            ax.grid(True, alpha=0.3)
            ax.legend()
            st.pyplot(fig)

        with tab_map:
            m = folium.Map(location=conf["coords"], zoom_start=14)
            folium.TileLayer('https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}', attr='Google', name='Google Satellite').add_to(m)
            folium.Marker(conf["coords"], popup=proyecto).add_to(m)
            st_folium(m, width="100%", height=500)

        with tab_data:
            st.dataframe(df_view.sort_values('Fecha', ascending=False), use_container_width=True)

# --- MÓDULO 2: GESTIÓN (PARA CLIENTES NUEVOS) ---
else:
    st.header("⚙️ Configuración de Clientes")
    st.write("Registra aquí los IDs de los nuevos Excels que crees.")
    
    with st.form("nuevo_cliente"):
        n = st.text_input("Nombre del Proyecto")
        i = st.text_input("ID del Google Sheet")
        la = st.number_input("Latitud", value=-37.0)
        lo = st.number_input("Longitud", value=-72.0)
        p = st.text_input("Nombre de la Pestaña", value="Hoja 1")
        
        if st.form_submit_button("Vincular Proyecto"):
            st.success(f"Proyecto {n} listo. Agrégalo a la lista 'CLIENTES_DB' en el código.")
            st.code(f"'{n}': {{'id': '{i}', 'pestaña': '{p}', 'coords': [{la}, {lo}]}}")
