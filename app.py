import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import gspread
from google.oauth2.service_account import Credentials
from fpdf import FPDF
import json
import base64

# --- 1. CONFIGURACIÓN E INICIALIZACIÓN ---
st.set_page_config(page_title="BioCore Intelligence", layout="wide")

try:
    creds_dict = json.loads(st.secrets["GEE_JSON"])
    SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    CREDS = Credentials.from_service_account_info(creds_dict, scopes=SCOPE)
    G_CLIENT = gspread.authorize(CREDS)
except:
    st.error("Configura las credenciales en Secrets.")
    st.stop()

# --- 2. BASE DE DATOS DE PROYECTOS ---
# Aquí es donde el cliente guarda sus datos: Nombre, ID y Coordenadas
CLIENTES_DB = {
    "Pascua Lama (Cordillera)": {
        "sheet_id": "1UTrDs939rPlVIR1OTIwbJ6rM3FazgjX43YnJdue-Dmc",
        "pestaña": "ID_CARPETA_2",
        "coords": [-29.32, -70.02],
        "tipo": "Minería"
    }
}

# --- 3. FUNCIONES DE APOYO ---

def generar_pdf(df, nombre_proyecto):
    """Crea un informe técnico en PDF con los índices"""
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(190, 10, f"Informe Técnico: {nombre_proyecto}", ln=True, align='C')
    pdf.ln(10)
    
    pdf.set_font("Arial", size=12)
    pdf.multi_cell(0, 10, f"Resumen de monitoreo ambiental generado el {pd.Timestamp.now().strftime('%d/%m/%Y')}.")
    pdf.ln(5)
    
    # Tabla de datos en el PDF
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(40, 10, "Fecha", 1)
    pdf.cell(30, 10, "NDSI", 1)
    pdf.cell(30, 10, "NDWI", 1)
    pdf.cell(30, 10, "SWIR", 1)
    pdf.ln()
    
    pdf.set_font("Arial", size=10)
    for i, row in df.tail(10).iterrows():
        pdf.cell(40, 10, str(row['Fecha'].date()), 1)
        pdf.cell(30, 10, str(row['NDSI']), 1)
        pdf.cell(30, 10, str(row['NDWI']), 1)
        pdf.cell(30, 10, str(row['SWIR']), 1)
        pdf.ln()
    
    return pdf.output(dest='S').encode('latin-1')

# --- 4. INTERFAZ (SIDEBAR) ---
with st.sidebar:
    st.title("🌿 BioCore Admin")
    opcion = st.radio("Ir a:", ["📊 Panel de Auditoría", "➕ Registrar Proyecto"])
    
    if opcion == "📊 Panel de Auditoría":
        proyecto_sel = st.selectbox("Proyecto Activo:", list(CLIENTES_DB.keys()))
        dias_ver = st.slider("Registros a mostrar:", 5, 50, 15)

# --- 5. MÓDULOS ---

if opcion == "➕ Registrar Proyecto":
    st.header("Registro de Nuevo Cliente")
    with st.form("registro_cliente"):
        nom = st.text_input("Nombre del Proyecto")
        s_id = st.text_input("ID del Google Sheet")
        tipo = st.selectbox("Tipo de Proyecto", ["Minería", "Forestal", "Agrícola"])
        lat = st.number_input("Latitud", value=-29.0)
        lon = st.number_input("Longitud", value=-70.0)
        
        if st.form_submit_button("Guardar Datos de Cliente"):
            st.success(f"Proyecto '{nom}' registrado localmente.")
            # Esto genera el código para que el cliente lo pegue en su base de datos
            nuevo_entry = {nom: {"sheet_id": s_id, "coords": [lat, lon], "tipo": tipo}}
            st.code(f"Añadir a CLIENTES_DB:\n{nuevo_entry}")

elif opcion == "📊 Panel de Auditoría":
    info = CLIENTES_DB[proyecto_sel]
    st.header(f"Gestión de Proyecto: {proyecto_sel}")
    
    if st.button("🔄 Sincronizar Base de Datos"):
        try:
            hoja = G_CLIENT.open_by_key(info["sheet_id"]).worksheet(info.get("pestaña", "Hoja 1"))
            df = pd.DataFrame(hoja.get_all_records())
            df['Fecha'] = pd.to_datetime(df['Fecha'])
            st.session_state[f"data_{proyecto_sel}"] = df
        except:
            st.error("No se pudo acceder a los datos. Verifique el ID y permisos del Sheet.")

    if f"data_{proyecto_sel}" in st.session_state:
        df = st.session_state[f"data_{proyecto_sel}"]
        
        # Dashboard sin índices (Solo tabla de gestión y botones)
        st.subheader("Registros en Nube")
        st.dataframe(df.tail(dias_ver), use_container_width=True)
        
        st.markdown("---")
        # Generación del informe
        if st.button("📄 Generar Informe Técnico para Cliente"):
            pdf_data = generar_pdf(df, proyecto_sel)
            b64_pdf = base64.b64encode(pdf_data).decode('utf-8')
            href = f'<a href="data:application/octet-stream;base64,{b64_pdf}" download="Informe_{proyecto_sel}.pdf">📥 Descargar Informe PDF</a>'
            st.markdown(href, unsafe_allow_html=True)
            st.success("Informe generado con éxito (incluye índices y tendencias).")

    # Mapa de ubicación
    st.markdown("---")
    m = folium.Map(location=info["coords"], zoom_start=14)
    folium.TileLayer('https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}', attr='Google', name='Sat').add_to(m)
    st_folium(m, width="100%", height=400)
