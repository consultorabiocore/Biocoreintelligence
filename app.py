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

# --- 1. CONFIGURACIÓN E IDENTIDAD ---
st.set_page_config(page_title="BioCore Audit System", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; border-left: 5px solid #183654; }
    </style>
    """, unsafe_allow_html=True)

try:
    creds_dict = json.loads(st.secrets["GEE_JSON"])
    SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    CREDS = Credentials.from_service_account_info(creds_dict, scopes=SCOPE)
    G_CLIENT = gspread.authorize(CREDS)
except Exception as e:
    st.error(f"Error de credenciales: {e}")
    st.stop()

# --- 2. BASE DE DATOS DE PROYECTOS ---
UMBRAL_CRITICO = 0.40  
CLIENTES_DB = {
    "Pascua Lama (Cordillera)": {
        "sheet_id": "1UTrDs939rPlVIR1OTIwbJ6rM3FazgjX43YnJdue-Dmc",
        "pestaña": "ID_CARPETA_2",
        "lat": -29.3200, "lon": -70.0200,
        "contacto": "Gerencia de Medio Ambiente",
        "region": "Atacama / San Juan",
        "sensores": "Sentinel-1 (SAR), Sentinel-2 (Óptico), Landsat 8/9"
    }
}

# --- 3. PROCESAMIENTO ROBUSTO DE DATOS ---
def procesar_datos_bio_inteligente(sheet_id, pestaña):
    try:
        hoja = G_CLIENT.open_by_key(sheet_id).worksheet(pestaña)
        df = pd.DataFrame(hoja.get_all_records())
        
        # Limpieza de Fechas
        df['Fecha'] = pd.to_datetime(df['Fecha'], errors='coerce')
        df = df.dropna(subset=['Fecha']).sort_values('Fecha')
        
        # Columnas objetivo
        indices = ["SAVI", "NDSI", "NDWI", "SWIR", "Deficit"]
        presentes = []
        
        for col in indices:
            if col in df.columns:
                # SOLUCIÓN AL ERROR: Convertir a número y tratar errores como NaN
                df[col] = pd.to_numeric(df[col], errors='coerce')
                # Llenar vacíos o textos (NaN) con interpolación lineal o cero si no hay datos
                if df[col].isnull().any():
                    df[col] = df[col].interpolate().fillna(0)
                presentes.append(col)
        
        return df, presentes
    except Exception as e:
        st.error(f"Error al leer la Pestaña: {e}")
        return pd.DataFrame(), []

# --- 4. MOTOR DE GRÁFICOS ---
def generar_graficos_cascada(df, columnas):
    n = len(columnas)
    fig, axs = plt.subplots(n, 1, figsize=(10, 3 * n))
    if n == 1: axs = [axs]
    
    colores = {"SAVI": "#143654", "NDSI": "#0077b6", "NDWI": "#2E7D32", "SWIR": "#D4AC0D", "Deficit": "#C62828"}
    
    for i, col in enumerate(columnas):
        axs[i].plot(df['Fecha'], df[col], color=colores.get(col, "#333333"), linewidth=1.5, marker='.')
        axs[i].set_title(f"MONITOREO TÉCNICO: {col}", fontsize=10, fontweight='bold', loc='left')
        axs[i].grid(True, linestyle=':', alpha=0.5)
        axs[i].tick_params(labelsize=8)
    
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150)
    return buf

# --- 5. REPORTE PDF ---
class BioCorePDF(FPDF):
    def header(self):
        self.set_fill_color(24, 54, 84) 
        self.rect(0, 0, 210, 35, 'F')
        self.set_text_color(255, 255, 255)
        self.set_font("Arial", 'B', 14)
        self.cell(0, 15, "AUDITORÍA DE CUMPLIMIENTO AMBIENTAL", 0, 1, 'C')
        self.set_font("Arial", 'I', 9)
        self.cell(0, 5, "Responsable Técnica: Loreto Campos Carrasco | BioCore Intelligence", 0, 1, 'C')

def crear_pdf(df, proyecto, columnas):
    info = CLIENTES_DB[proyecto]
    ultimo_val = df.iloc[-1].get('NDSI', df.iloc[-1].get('SAVI', 0))
    es_alerta = ultimo_val < UMBRAL_CRITICO
    
    pdf = BioCorePDF()
    pdf.add_page()
    pdf.ln(25)
    
    # ESTATUS
    status_txt = "ALERTA TÉCNICA: PÉRDIDA DE COBERTURA" if es_alerta else "NORMAL / CUMPLIMIENTO"
    pdf.set_fill_color(200, 0, 0) if es_alerta else pdf.set_fill_color(0, 100, 0)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, f"  ESTATUS: {status_txt}", 0, 1, 'L', True)
    
    # FICHA
    pdf.ln(5)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(0, 8, f"PROYECTO: {proyecto.upper()}", 0, 1)
    pdf.set_font("Arial", size=9)
    pdf.cell(0, 6, f"Ubicación: {info['region']} | Coordenadas: {info['lat']}, {info['lon']}", 0, 1)

    # HALLAZGOS
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(0, 10, "DIAGNÓSTICO TÉCNICO DE CRIÓSFERA:", 0, 1)
    pdf.set_font("Arial", size=9)
    msg = f"Valor actual {ultimo_val:.4f} bajo umbral de seguridad." if es_alerta else "Estabilidad detectada."
    pdf.multi_cell(0, 7, f"1. HALLAZGO: {msg}", border=1)
    pdf.multi_cell(0, 7, "2. RIESGO: Posible degradación severa de masa criosférica.", border=1)
    pdf.multi_cell(0, 7, "3. RECOMENDACIÓN: Inspección inmediata de terreno.", border=1)

    # GRÁFICOS
    pdf.add_page()
    pdf.ln(20)
    buf_graf = generar_graficos_cascada(df, columnas)
    with open("temp_report.png", "wb") as f:
        f.write(buf_graf.getbuffer())
    pdf.image("temp_report.png", x=15, w=180)
    
    return pdf.output(dest='S').encode('latin-1')

# --- 6. INTERFAZ ---
st.title("🛡️ BioCore Intelligence Audit")
proyecto_sel = st.sidebar.selectbox("Proyecto Activo:", list(CLIENTES_DB.keys()))
info_p = CLIENTES_DB[proyecto_sel]

col_m, col_i = st.columns([2, 1])

with col_i:
    st.subheader("Ficha Técnica")
    st.info(f"**Cliente:** {info_p['contacto']}\n\n**Región:** {info_p['region']}\n\n**Sensores:** {info_p['sensores']}")

with col_m:
    m = folium.Map(location=[info_p['lat'], info_p['lon']], zoom_start=12, 
                   tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
                   attr='Esri World Imagery')
    folium.Marker([info_p['lat'], info_p['lon']], popup=proyecto_sel).add_to(m)
    folium_static(m)

if st.button("🚀 SINCRONIZAR Y GENERAR REPORTE"):
    with st.spinner("Accediendo a la base de datos..."):
        df_final, cols_final = procesar_datos_bio_inteligente(info_p['sheet_id'], info_p['pestaña'])
        
        if not df_final.empty:
            st.success("Datos sincronizados correctamente.")
            # Métricas
            st.divider()
            m1, m2, m3 = st.columns(3)
            val = df_final.iloc[-1].get('SAVI', 0)
            m1.metric("Último SAVI", f"{val:.4f}")
            m2.metric("Déficit Detectado", f"{df_final.iloc[-1].get('Deficit', 0):.2f}")
            m3.metric("Estatus", "ALERTA" if val < UMBRAL_CRITICO else "OK")

            # Gráficos
            st.image(generar_graficos_cascada(df_final, cols_final))
            
            # PDF
            pdf_b = crear_pdf(df_final, proyecto_sel, cols_final)
            b64 = base64.b64encode(pdf_b).decode()
            href = f'<a href="data:application/pdf;base64,{b64}" download="Auditoria_BioCore_{proyecto_sel}.pdf" style="display:block; text-align:center; padding:15px; background-color:#183654; color:white; border-radius:10px; text-decoration:none; font-weight:bold;">📄 DESCARGAR REPORTE DE AUDITORÍA</a>'
            st.markdown(href, unsafe_allow_html=True)
        else:
            st.warning(f"La pestaña '{info_p['pestaña']}' parece estar vacía o no existe.")
