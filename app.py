import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import gspread
from google.oauth2.service_account import Credentials
from fpdf import FPDF
import json
import base64
from datetime import datetime

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="BioCore Intelligence", layout="wide")

try:
    creds_dict = json.loads(st.secrets["GEE_JSON"])
    SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    CREDS = Credentials.from_service_account_info(creds_dict, scopes=SCOPE)
    G_CLIENT = gspread.authorize(CREDS)
except:
    st.error("Error en credenciales.")
    st.stop()

CLIENTES_DB = {
    "Pascua Lama (Cordillera)": {
        "sheet_id": "1UTrDs939rPlVIR1OTIwbJ6rM3FazgjX43YnJdue-Dmc",
        "pestaña": "ID_CARPETA_2",
        "coords": [-29.32, -70.02]
    }
}

# --- 2. FUNCIÓN DE LIMPIEZA AUTOMÁTICA ---
def obtener_y_limpiar_datos(sheet_id, pestaña):
    try:
        hoja = G_CLIENT.open_by_key(sheet_id).worksheet(pestaña)
        df = pd.DataFrame(hoja.get_all_records())
        
        if df.empty: return df

        # A. Unificar Fechas
        df['Fecha'] = pd.to_datetime(df['Fecha'], errors='coerce')
        df = df.dropna(subset=['Fecha'])

        # B. Limpieza de "Basura": Quitar filas donde todo sea 0 (excepto fecha)
        # Esto elimina esas filas que te ensucian el Sheet
        cols_indices = [c for c in df.columns if c != 'Fecha']
        df[cols_indices] = df[cols_indices].apply(pd.to_numeric, errors='coerce')
        df = df[(df[cols_indices] != 0).any(axis=1)]

        # C. Quitar Duplicados: Si hay varias filas para el mismo día, deja la última
        df = df.sort_values('Fecha').drop_duplicates(subset=['Fecha'], keep='last')
        
        return df
    except Exception as e:
        st.error(f"Error al limpiar: {e}")
        return pd.DataFrame()

# --- 3. FUNCIÓN DEL INFORME ---
def generar_pdf(df, proyecto):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(190, 10, f"BioCore Intelligence - Informe Tecnico", ln=True, align='C')
    pdf.set_font("Arial", size=12)
    pdf.cell(190, 10, f"Proyecto: {proyecto}", ln=True, align='C')
    pdf.ln(10)

    # Solo las columnas que existen en tu Excel (SAVI, NDWI, Arcillas...)
    columnas = [c for c in df.columns if c != 'Fecha']
    
    # Tabla
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(35, 10, "Fecha", 1)
    for c in columnas[:4]: # Limitamos a 4 columnas para que quepa en la hoja
        pdf.cell(35, 10, c, 1)
    pdf.ln()

    pdf.set_font("Arial", size=10)
    for _, row in df.tail(20).iterrows():
        pdf.cell(35, 10, row['Fecha'].strftime('%d/%m/%Y'), 1)
        for c in columnas[:4]:
            val = row[c]
            txt = f"{val:.3f}" if pd.notnull(val) else "N/A"
            pdf.cell(35, 10, txt, 1)
        pdf.ln()
    
    return pdf.output(dest='S').encode('latin-1')

# --- 4. INTERFAZ ---
with st.sidebar:
    st.title("🌿 BioCore Admin")
    opcion = st.radio("Menú", ["📊 Auditoría", "➕ Registrar"])
    if opcion == "📊 Auditoría":
        sel = st.selectbox("Proyecto:", list(CLIENTES_DB.keys()))

if opcion == "📊 Auditoría":
    conf = CLIENTES_DB[sel]
    st.header(f"Control: {sel}")

    if st.button("🔄 Sincronizar y Limpiar Datos"):
        with st.spinner("Procesando y eliminando duplicados..."):
            df_limpio = obtener_y_limpiar_datos(conf["sheet_id"], conf["pestaña"])
            if not df_limpio.empty:
                st.session_state[f"clean_{sel}"] = df_limpio
                st.success(f"¡Sincronizado! Se procesaron {len(df_limpio)} registros únicos.")
            else:
                st.error("No hay datos válidos.")

    if f"clean_{sel}" in st.session_state:
        data = st.session_state[f"clean_{sel}"]
        st.dataframe(data.tail(15), use_container_width=True)

        if st.button("📄 Descargar Informe PDF"):
            pdf_bytes = generar_pdf(data, sel)
            b64 = base64.b64encode(pdf_bytes).decode()
            href = f'<a href="data:application/pdf;base64,{b64}" download="Informe_{sel}.pdf" style="text-decoration:none; background-color:#4CAF50; color:white; padding:10px 20px; border-radius:5px;">📥 CLICK AQUÍ PARA BAJAR PDF</a>'
            st.markdown(href, unsafe_allow_html=True)

    st.markdown("---")
    m = folium.Map(location=conf["coords"], zoom_start=14)
    folium.TileLayer('https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}', attr='Google', name='Sat').add_to(m)
    st_folium(m, width="100%", height=400)

else:
    st.header("Registro de Datos de Cliente")
    with st.form("reg"):
        nombre = st.text_input("Nombre Proyecto")
        sheet = st.text_input("ID Sheet")
        if st.form_submit_button("Guardar"):
            st.info("Datos guardados. Actualiza el diccionario CLIENTES_DB con esta info.")
