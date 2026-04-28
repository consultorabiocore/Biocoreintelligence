import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from fpdf import FPDF
import json
import base64
import gspread
from google.oauth2.service_account import Credentials
import io
import folium
from streamlit_folium import folium_static
from datetime import datetime
import re

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="BioCore Intelligence Admin", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stButton>button { background-color: #183654; color: white; border-radius: 8px; font-weight: bold; height: 3.5em; }
    </style>
    """, unsafe_allow_html=True)

try:
    creds_dict = json.loads(st.secrets["GEE_JSON"])
    SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    CREDS = Credentials.from_service_account_info(creds_dict, scopes=SCOPE)
    G_CLIENT = gspread.authorize(CREDS)
except:
    st.error("Error en credenciales GEE_JSON.")
    st.stop()

if 'clientes_db' not in st.session_state:
    st.session_state.clientes_db = {}

# --- 2. LÓGICA DE DATOS ---
def obtener_datos_seguros(sheet_id, pestaña):
    try:
        # Limpieza del ID por si acaso
        s_id = sheet_id.strip()
        sh = G_CLIENT.open_by_key(s_id)
        
        # Verificar pestañas disponibles si hay error
        nombres_pestañas = [h.title for h in sh.worksheets()]
        if pestaña not in nombres_pestañas:
            st.error(f"Pestaña '{pestaña}' no encontrada. Disponibles: {nombres_pestañas}")
            return pd.DataFrame()

        hoja = sh.worksheet(pestaña)
        df = pd.DataFrame(hoja.get_all_records())
        df.columns = [c.strip() for c in df.columns]
        
        if df.empty: return pd.DataFrame()

        df['Fecha'] = pd.to_datetime(df['Fecha'], dayfirst=True, errors='coerce')
        df = df.dropna(subset=['Fecha']).sort_values('Fecha')
        
        for col in ["SAVI", "NDSI", "NDWI", "SWIR", "Deficit"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        return df
    except Exception as e:
        st.error(f"Error al acceder al Sheet: {e}")
        return pd.DataFrame()

# --- 3. INTERFAZ ---
st.sidebar.title("BioCore Intelligence")
menu = st.sidebar.radio("Menú", ["Auditoría", "Gestión de Clientes"])

if menu == "Auditoría":
    st.header("🛡️ Panel de Auditoría")
    if not st.session_state.clientes_db:
        st.info("Registra un proyecto con su ID real de Google Sheet primero.")
    else:
        p_sel = st.selectbox("Proyecto:", list(st.session_state.clientes_db.keys()))
        info = st.session_state.clientes_db[p_sel]
        
        col_c, col_m = st.columns([1, 1.5])
        with col_c:
            if st.button("🚀 GENERAR INFORME"):
                df_final = obtener_datos_seguros(info['sheet_id'], info['pestaña'])
                if not df_final.empty:
                    st.success("Datos cargados. Generando PDF...")
                    # Aquí iría tu función de PDF (crear_pdf_final)
                else:
                    st.warning("La hoja está vacía o el ID es incorrecto.")
        
        with col_m:
            m = folium.Map(location=info['coords'][0], zoom_start=14)
            folium.Polygon(locations=info['coords'], color="#183654", fill=True).add_to(m)
            folium_static(m)

else:
    st.header("📁 Gestión de Proyectos")
    with st.form("reg_pro"):
        nom = st.text_input("Nombre Proyecto")
        sid = st.text_input("ID real del Sheet (de la URL)")
        pes = st.text_input("Pestaña", value="Hoja 1")
        raw_c = st.text_area("Pegue coordenadas (Cualquier formato)")
        
        if st.form_submit_button("Guardar"):
            # Limpiador de coordenadas avanzado
            numeros = re.findall(r"[-+]?\d*\.\d+|[-+]?\d+", raw_c)
            coords = []
            for i in range(0, len(numeros), 2):
                if i+1 < len(numeros):
                    coords.append([float(numeros[i]), float(numeros[i+1])])
            
            if len(coords) >= 3:
                st.session_state.clientes_db[nom] = {
                    "sheet_id": sid.strip(), "pestaña": pes.strip(), "coords": coords
                }
                st.success(f"Proyecto {nom} guardado con {len(coords)} puntos.")
            else:
                st.error("Formato inválido o pocos puntos detectados.")
    
    st.write("Registros actuales:", st.session_state.clientes_db)
