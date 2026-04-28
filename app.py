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

# --- 1. CONFIGURACIÓN Y ESTILO ---
st.set_page_config(page_title="BioCore Admin System", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    [data-testid="stMetricValue"] { color: #183654 !important; font-size: 28px; font-weight: bold; }
    .stMetric { 
        background-color: #ffffff; 
        padding: 15px; 
        border-radius: 10px; 
        border-left: 5px solid #183654;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.05);
    }
    .sidebar-text { font-size: 14px; color: #455A64; }
    </style>
    """, unsafe_allow_html=True)

# Conexión Segura
try:
    creds_dict = json.loads(st.secrets["GEE_JSON"])
    SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    CREDS = Credentials.from_service_account_info(creds_dict, scopes=SCOPE)
    G_CLIENT = gspread.authorize(CREDS)
except Exception as e:
    st.error("Error de conexión con Google. Revisa GEE_JSON.")
    st.stop()

# Simulación de Base de Datos (Persistente durante la sesión)
if 'clientes_db' not in st.session_state:
    st.session_state.clientes_db = {
        "Pascua Lama (Cordillera)": {
            "sheet_id": "1UTrDs939rPlVIR1OTIwbJ6rM3FazgjX43YnJdue-Dmc",
            "pestaña": "ID_CARPETA_2",
            "lat": -29.3200, "lon": -70.0200,
            "region": "Atacama / San Juan",
            "sensores": "S1/S2/L8",
            "fecha_registro": "2026-04-20"
        }
    }

# --- 2. BARRA LATERAL (SIDEBAR) ---
st.sidebar.image("https://cdn-icons-png.flaticon.com/512/2092/2092144.png", width=70)
st.sidebar.title("BioCore Intelligence")
menu = st.sidebar.radio("MENÚ PRINCIPAL", ["📊 Dashboard Auditoría", "📁 Gestión de Clientes"])

st.sidebar.divider()
st.sidebar.markdown("**ESTADO DEL SISTEMA**")
st.sidebar.success("📡 Sensores Activos")
st.sidebar.write(f"Proyectos Registrados: {len(st.session_state.clientes_db)}")

# --- 3. FUNCIONES TÉCNICAS ---
def procesar_datos(sheet_id, pestaña):
    try:
        hoja = G_CLIENT.open_by_key(sheet_id).worksheet(pestaña)
        df = pd.DataFrame(hoja.get_all_records())
        df['Fecha'] = pd.to_datetime(df['Fecha'], errors='coerce')
        df = df.dropna(subset=['Fecha']).sort_values('Fecha')
        for col in ["SAVI", "NDSI", "NDWI", "Deficit"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').interpolate().fillna(0)
        return df
    except: return pd.DataFrame()

def graficar_pdf(df):
    fig, axs = plt.subplots(3, 1, figsize=(8, 9))
    cols = ["NDSI", "NDWI", "Deficit"]
    for i, col in enumerate(cols):
        if col in df.columns:
            axs[i].plot(df['Fecha'], df[col], color="#183654", lw=1.5)
            axs[i].set_title(f"HISTÓRICO: {col}", fontsize=10, fontweight='bold')
            axs[i].grid(True, alpha=0.2)
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150)
    return buf

# --- 4. VISTAS ---
if menu == "📊 Dashboard Auditoría":
    st.subheader("🛡️ Panel de Control Satelital")
    p_sel = st.selectbox("Seleccione Proyecto para Auditar:", list(st.session_state.clientes_db.keys()))
    info = st.session_state.clientes_db[p_sel]

    col1, col2 = st.columns([1, 1.5])
    with col1:
        st.info(f"**Ubicación:** {info['region']}\n\n**Sensores:** {info['sensores']}")
        if st.button("🚀 EJECUTAR AUDITORÍA"):
            df = procesar_datos(info['sheet_id'], info['pestaña'])
            if not df.empty:
                st.divider()
                st.metric("Último SAVI (Veg)", f"{df.iloc[-1]['SAVI']:.4f}")
                st.metric("Déficit Acumulado", f"{df.iloc[-1]['Deficit']:.2f}")
                
                # Botón de Descarga
                pdf = FPDF()
                pdf.add_page()
                pdf.set_font("Arial", 'B', 16)
                pdf.cell(0, 10, f"INFORME TÉCNICO: {p_sel}", 0, 1, 'C')
                g_buf = graficar_pdf(df)
                with open("temp.png", "wb") as f: f.write(g_buf.getbuffer())
                pdf.image("temp.png", x=15, y=40, w=180)
                
                pdf_bytes = pdf.output(dest='S').encode('latin-1')
                b64 = base64.b64encode(pdf_bytes).decode()
                st.markdown(f'<a href="data:application/pdf;base64,{b64}" download="Audit_{p_sel}.pdf" style="text-decoration:none;"><div style="text-align:center; padding:10px; background-color:#183654; color:white; border-radius:5px; font-weight:bold;">📄 DESCARGAR PDF</div></a>', unsafe_allow_html=True)

    with col2:
        m = folium.Map(location=[info['lat'], info['lon']], zoom_start=13)
        folium.Marker([info['lat'], info['lon']], popup=p_sel).add_to(m)
        folium_static(m)

elif menu == "📁 Gestión de Clientes":
    st.subheader("📁 Registro Histórico y Nuevos Proyectos")
    
    # Tabla Histórica
    st.markdown("### Proyectos en Base de Datos")
    df_hist = pd.DataFrame.from_dict(st.session_state.clientes_db, orient='index')
    st.dataframe(df_hist, use_container_width=True)
    
    # Formulario de Registro
    with st.expander("➕ Registrar Nuevo Cliente"):
        with st.form("reg_form"):
            n = st.text_input("Nombre del Proyecto")
            sid = st.text_input("Google Sheet ID")
            pes = st.text_input("Pestaña", value="Hoja 1")
            lat = st.number_input("Latitud", format="%.4f")
            lon = st.number_input("Longitud", format="%.4f")
            reg = st.text_input("Región")
            if st.form_submit_button("Guardar en Registro"):
                st.session_state.clientes_db[n] = {
                    "sheet_id": sid, "pestaña": pes, "lat": lat, "lon": lon, 
                    "region": reg, "sensores": "S2/L8", "fecha_registro": datetime.now().strftime('%Y-%m-%d')
                }
                st.rerun()
