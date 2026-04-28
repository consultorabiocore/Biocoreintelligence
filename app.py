import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from fpdf import FPDF
import json
import base64
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import io
import folium
from streamlit_folium import folium_static

# --- 1. CONFIGURACIÓN E IDENTIDAD CORPORATIVA ---
st.set_page_config(page_title="BioCore Audit System", layout="wide")

# Estilo para botones y métricas
st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    </style>
    """, unsafe_allow_html=True)

try:
    creds_dict = json.loads(st.secrets["GEE_JSON"])
    SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    CREDS = Credentials.from_service_account_info(creds_dict, scopes=SCOPE)
    G_CLIENT = gspread.authorize(CREDS)
except:
    st.error("Error crítico: Revisa las credenciales GEE_JSON en Streamlit Secrets.")
    st.stop()

# --- 2. BASE DE DATOS DE CLIENTES Y UMBRALES ---
UMBRAL_CRITICO = 0.40  # Límite para alerta de cobertura
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

# --- 3. PROCESAMIENTO TÉCNICO DE DATOS ---
def procesar_datos_completos(sheet_id, pestaña):
    try:
        hoja = G_CLIENT.open_by_key(sheet_id).worksheet(pestaña)
        df = pd.DataFrame(hoja.get_all_records())
        df['Fecha'] = pd.to_datetime(df['Fecha'], errors='coerce')
        df = df.dropna(subset=['Fecha']).sort_values('Fecha')
        
        indices = ["SAVI", "NDWI", "SWIR", "Arcillas", "Deficit", "VV", "VH"]
        presentes = []
        for col in indices:
            if col in df.columns:
                # Convertimos a número y limpiamos textos como "Muy Alto"
                df[col] = pd.to_numeric(df[col], errors='coerce').interpolate().fillna(0)
                presentes.append(col)
        return df, presentes
    except:
        return pd.DataFrame(), []

# --- 4. MOTOR DE GRÁFICOS (CASCADA PROFESIONAL) ---
def generar_graficos_cascada(df, columnas):
    n = len(columnas)
    fig, axs = plt.subplots(n, 1, figsize=(10, 3 * n))
    if n == 1: axs = [axs]
    
    colores = {"SAVI": "#143654", "NDWI": "#2E7D32", "SWIR": "#D4AC0D", "Deficit": "#C62828", "Arcillas": "#6E2C00"}
    
    for i, col in enumerate(columnas):
        axs[i].plot(df['Fecha'], df[col], color=colores.get(col, "#333333"), linewidth=1.5, marker='.', markersize=4)
        axs[i].set_title(f"MONITOREO TÉCNICO: {col}", fontsize=10, fontweight='bold', loc='left')
        axs[i].grid(True, linestyle=':', alpha=0.5)
        axs[i].tick_params(labelsize=8)
    
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150)
    return buf

# --- 5. REPORTE PDF (ESTILO FISCALIZACIÓN) ---
class BioCorePDF(FPDF):
    def header(self):
        self.set_fill_color(24, 54, 84) # Azul Marino Institucional
        self.rect(0, 0, 210, 35, 'F')
        self.set_text_color(255, 255, 255)
        self.set_font("Arial", 'B', 14)
        self.cell(0, 15, "AUDITORÍA DE CUMPLIMIENTO AMBIENTAL", 0, 1, 'C')
        self.set_font("Arial", 'I', 9)
        self.cell(0, 5, "Responsable Técnica: Loreto Campos Carrasco | BioCore Intelligence", 0, 1, 'C')

def crear_reporte_pdf(df, proyecto, columnas):
    info = CLIENTES_DB[proyecto]
    ultimo_val = df.iloc[-1].get('SAVI', 0)
    es_alerta = ultimo_val < UMBRAL_CRITICO
    
    pdf = BioCorePDF()
    pdf.add_page()
    pdf.ln(25)
    
    # ESTATUS (SEMÁFORO)
    status_txt = "ALERTA TÉCNICA: PÉRDIDA DE COBERTURA" if es_alerta else "ESTATUS: NORMAL / CUMPLIMIENTO"
    pdf.set_fill_color(200, 0, 0) if es_alerta else pdf.set_fill_color(0, 100, 0)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, f"  {status_txt}", 0, 1, 'L', True)
    
    # FICHA DEL PROYECTO
    pdf.ln(5)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(0, 8, f"PROYECTO: {proyecto.upper()}", 0, 1)
    pdf.set_font("Arial", size=9)
    pdf.cell(0, 6, f"Coordenadas: {info['lat']}, {info['lon']} | Región: {info['region']}", 0, 1)
    pdf.cell(0, 6, f"Sensores: {info['sensores']}", 0, 1)
    
    # HALLAZGOS NUMERADOS
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(0, 10, "DIAGNÓSTICO TÉCNICO:", 0, 1)
    pdf.set_font("Arial", size=9)
    
    hallazgo = (f"Se detecta un valor de {ultimo_val:.4f} en el índice de cobertura. "
                "Este registro indica una desviación crítica." if es_alerta else "Valores estables.")
    
    pdf.multi_cell(0, 7, f"1. HALLAZGO CRÍTICO: {hallazgo}", border=1)
    pdf.multi_cell(0, 7, "2. RIESGO TÉCNICO: Posible incumplimiento de RCA por alteración de masa criosférica.", border=1)
    pdf.multi_cell(0, 7, "3. ACCIÓN RECOMENDADA: Inspección de terreno y validación de material particulado.", border=1)

    # SEGUNDA PÁGINA: GRÁFICOS
    pdf.add_page()
    pdf.ln(20)
    buf_graf = generar_graficos_cascada(df, columnas)
    with open("audit_graf.png", "wb") as f:
        f.write(buf_graf.getbuffer())
    pdf.image("audit_graf.png", x=15, w=180)
    
    return pdf.output(dest='S').encode('latin-1')

# --- 6. INTERFAZ PRINCIPAL (DASHBOARD) ---
st.title("🛡️ BioCore Audit System")
st.sidebar.image("https://cdn-icons-png.flaticon.com/512/2092/2092144.png", width=100)
st.sidebar.header("Panel de Fiscalización")

proyecto_sel = st.sidebar.selectbox("Seleccione Proyecto Activo:", list(CLIENTES_DB.keys()))
info_p = CLIENTES_DB[proyecto_sel]

# Layout de Columnas
col_map, col_info = st.columns([2, 1])

with col_info:
    st.subheader("Ficha del Cliente")
    st.info(f"""
    **Proyecto:** {proyecto_sel}  
    **Contacto:** {info_p['contacto']}  
    **Ubicación:** {info_p['region']}  
    **Sensores:** {info_p['sensores']}
    """)
    
with col_map:
    m = folium.Map(location=[info_p['lat'], info_p['lon']], zoom_start=12, tiles="Stamen Terrain")
    folium.Marker([info_p['lat'], info_p['lon']], popup=proyecto_sel).add_to(m)
    folium_static(m)

if st.button("🚀 EJECUTAR AUDITORÍA COMPLETA"):
    with st.spinner("Sincronizando con Google Earth Engine & Sheets..."):
        df_final, cols_final = procesar_datos_completos(info_p['sheet_id'], info_p['pestaña'])
        
        if not df_final.empty:
            st.divider()
            # Métricas rápidas
            m1, m2, m3 = st.columns(3)
            ultimo = df_final.iloc[-1]
            m1.metric("Último SAVI/NDSI", f"{ultimo.get('SAVI', 0):.4f}")
            m2.metric("Déficit Acumulado", f"{ultimo.get('Deficit', 0):.0f}")
            m3.metric("Estatus", "ALERTA" if ultimo.get('SAVI', 0) < UMBRAL_CRITICO else "OK")

            # Mostrar Gráficos en Cascada
            st.image(generar_graficos_cascada(df_final, cols_final))
            
            # Botón de Descarga
            pdf_bytes = crear_reporte_pdf(df_final, proyecto_sel, cols_final)
            b64 = base64.b64encode(pdf_bytes).decode()
            href = f'<a href="data:application/pdf;base64,{b64}" download="Auditoria_BioCore_{proyecto_sel}.pdf" style="display:block; text-align:center; padding:20px; background-color:#183654; color:white; border-radius:10px; text-decoration:none; font-weight:bold; font-size:20px;">📄 DESCARGAR AUDITORÍA TÉCNICA (PDF)</a>'
            st.markdown(href, unsafe_allow_html=True)
        else:
            st.error("No se detectaron datos en el Excel. Verifica la pestaña ID_CARPETA_2.")
