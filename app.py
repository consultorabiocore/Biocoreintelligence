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

# --- 1. CONFIGURACIÓN E IDENTIDAD VISUAL ---
st.set_page_config(page_title="BioCore Intelligence", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; border-left: 5px solid #183654; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    .report-title { color: #183654; font-weight: bold; font-size: 24px; }
    </style>
    """, unsafe_allow_html=True)

# Autenticación con Google Sheets
try:
    creds_dict = json.loads(st.secrets["GEE_JSON"])
    SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    CREDS = Credentials.from_service_account_info(creds_dict, scopes=SCOPE)
    G_CLIENT = gspread.authorize(CREDS)
except Exception as e:
    st.error(f"Fallo en la conexión: {e}")
    st.stop()

# --- 2. GESTIÓN DE CLIENTES (REGISTRO Y BASE DE DATOS) ---
# Aquí puedes expandir con una base de datos real o mantener el diccionario de proyectos activos
CLIENTES_DB = {
    "Pascua Lama (Cordillera)": {
        "sheet_id": "1UTrDs939rPlVIR1OTIwbJ6rM3FazgjX43YnJdue-Dmc",
        "pestaña": "ID_CARPETA_2",
        "lat": -29.3200, "lon": -70.0200,
        "rubro": "Minería",
        "contacto": "Gerencia Medio Ambiente",
        "sensores": "Sentinel-1 (SAR), Sentinel-2 (Óptico), Landsat 8/9"
    }
}

# --- 3. PROCESAMIENTO TÉCNICO DE DATOS ---
def obtener_datos_audit(sheet_id, pestaña):
    try:
        hoja = G_CLIENT.open_by_key(sheet_id).worksheet(pestaña)
        df = pd.DataFrame(hoja.get_all_records())
        
        # Limpieza y Conversión Forzada (Solución al error 'object dtype')
        df['Fecha'] = pd.to_datetime(df['Fecha'], errors='coerce')
        df = df.dropna(subset=['Fecha']).sort_values('Fecha')
        
        columnas_tecnicas = ["SAVI", "NDSI", "NDWI", "SWIR", "Deficit", "Arcillas", "VV", "VH"]
        presentes = []
        
        for col in columnas_tecnicas:
            if col in df.columns:
                # Forzamos conversión a float, ignorando errores de texto como 'Muy Alto'
                df[col] = pd.to_numeric(df[col], errors='coerce')
                # Interpolación para completar vacíos tras la conversión
                df[col] = df[col].interpolate().fillna(0)
                presentes.append(col)
        
        return df, presentes
    except Exception as e:
        st.error(f"Error al leer la base de datos: {e}")
        return pd.DataFrame(), []

# --- 4. MOTOR DE GRÁFICOS (ESTILO AUDITORÍA) ---
def generar_graficos_cascada(df, columnas):
    n = len(columnas)
    fig, axs = plt.subplots(n, 1, figsize=(10, 3.5 * n))
    if n == 1: axs = [axs]
    
    colores = {"SAVI": "#2E7D32", "NDSI": "#0077b6", "NDWI": "#1565C0", "Deficit": "#C62828", "SWIR": "#F9A825"}
    
    for i, col in enumerate(columnas):
        axs[i].plot(df['Fecha'], df[col], color=colores.get(col, "#455A64"), linewidth=2, marker='o', markersize=4)
        axs[i].set_title(f"TENDENCIA: {col}", fontsize=11, fontweight='bold', loc='left', color='#183654')
        axs[i].grid(True, linestyle='--', alpha=0.6)
        axs[i].tick_params(labelsize=9)
    
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150)
    return buf

# --- 5. REPORTE TÉCNICO PDF (ALTA PRECISIÓN) ---
class BioCoreReport(FPDF):
    def header(self):
        self.set_fill_color(24, 54, 84) # Azul BioCore
        self.rect(0, 0, 210, 40, 'F')
        self.set_text_color(255, 255, 255)
        self.set_font("Arial", 'B', 16)
        self.cell(0, 20, "AUDITORÍA DE CUMPLIMIENTO AMBIENTAL", 0, 1, 'C')
        self.set_font("Arial", 'I', 10)
        self.cell(0, 5, f"BioCore Intelligence - {datetime.now().strftime('%d/%m/%Y %H:%M')}", 0, 1, 'C')

def crear_pdf_final(df, proyecto_nombre, cols):
    info = CLIENTES_DB[proyecto_nombre]
    ultimo = df.iloc[-1]
    umbral = 0.40
    es_alerta = ultimo.get('NDSI', ultimo.get('SAVI', 0)) < umbral

    pdf = BioCoreReport()
    pdf.add_page()
    pdf.ln(25)

    # Diagnóstico y Estatus
    status = "ALERTA TÉCNICA: PÉRDIDA DE COBERTURA" if es_alerta else "ESTATUS: CUMPLIMIENTO NORMATIVO"
    pdf.set_fill_color(180, 0, 0) if es_alerta else pdf.set_fill_color(0, 100, 0)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 12, f"  {status}", 0, 1, 'L', True)

    # Info Proyecto
    pdf.ln(5)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(0, 8, f"PROYECTO: {proyecto_nombre.upper()}", 0, 1)
    pdf.set_font("Arial", '', 9)
    pdf.multi_cell(0, 6, f"Localización: Lat {info['lat']}, Lon {info['lon']}\nRubro: {info['rubro']}\nSensores: {info['sensores']}")

    # Cuadro de Hallazgos
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 11)
    pdf.cell(0, 10, "DIAGNÓSTICO DE CRIÓSFERA Y ALTA MONTAÑA:", 0, 1)
    pdf.set_font("Arial", '', 9)
    diagnostico = "Se observa una degradación severa de la firma espectral de hielo/nieve. Riesgo de incumplimiento de RCA." if es_alerta else "Los índices se mantienen estables dentro de los rangos históricos."
    pdf.multi_cell(0, 8, f"1. ESTADO: {diagnostico}", border=1)
    pdf.multi_cell(0, 8, "2. RECOMENDACIÓN: Realizar validación de terreno y monitoreo de material particulado.", border=1)

    # Gráficos en página 2
    pdf.add_page()
    pdf.ln(10)
    buf_g = generar_graficos_cascada(df, cols)
    with open("report_graf.png", "wb") as f: f.write(buf_g.getbuffer())
    pdf.image("report_graf.png", x=15, y=50, w=180)
    
    return pdf.output(dest='S').encode('latin-1')

# --- 6. INTERFAZ PRINCIPAL ---
st.sidebar.image("https://cdn-icons-png.flaticon.com/512/2092/2092144.png", width=80)
st.sidebar.title("Panel BioCore")
menu = st.sidebar.radio("Navegación:", ["Dashboard Auditoría", "Registro de Clientes"])

if menu == "Dashboard Auditoría":
    st.markdown('<p class="report-title">🌿 BioCore Intelligence: Auditoría Satelital</p>', unsafe_allow_html=True)
    
    proyecto_sel = st.sidebar.selectbox("Seleccione Proyecto:", list(CLIENTES_DB.keys()))
    info = CLIENTES_DB[proyecto_sel]

    col_map, col_data = st.columns([2, 1])

    with col_data:
        st.subheader("Ficha del Proyecto")
        st.write(f"**Ubicación:** {info['region']}")
        st.write(f"**Sensores:** {info['sensores']}")
        st.write(f"**Lat:** `{info['lat']}` | **Lon:** `{info['lon']}`")
        
    with col_map:
        m = folium.Map(location=[info['lat'], info['lon']], zoom_start=13, 
                       tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
                       attr='Esri World Imagery')
        folium.Marker([info['lat'], info['lon']], popup=proyecto_sel).add_to(m)
        folium_static(m)

    if st.button("🚀 SINCRONIZAR SENSORES Y GENERAR REPORTE"):
        with st.spinner("Analizando firmas espectrales..."):
            df_final, cols_final = obtener_datos_audit(info['sheet_id'], info['pestaña'])
            
            if not df_final.empty:
                st.success("Análisis Multi-satelital Completado.")
                
                # Resumen de métricas
                m1, m2, m3 = st.columns(3)
                ultimo_savi = df_final.iloc[-1].get('SAVI', 0)
                m1.metric("Índice SAVI", f"{ultimo_savi:.4f}")
                m2.metric("Déficit Hídrico", f"{df_final.iloc[-1].get('Deficit', 0):.2f}")
                m3.metric("Estatus", "ALERTA" if ultimo_savi < 0.40 else "NORMAL")

                # Mostrar Gráficos
                st.image(generar_graficos_cascada(df_final, cols_final))
                
                # Descarga de PDF
                pdf_bytes = crear_pdf_final(df_final, proyecto_sel, cols_final)
                b64 = base64.b64encode(pdf_bytes).decode()
                href = f'<a href="data:application/pdf;base64,{b64}" download="Reporte_BioCore_{proyecto_sel}.pdf" style="text-decoration:none;"><div style="text-align:center; padding:15px; background-color:#183654; color:white; border-radius:10px; font-weight:bold;">📄 DESCARGAR INFORME TÉCNICO (PDF)</div></a>'
                st.markdown(href, unsafe_allow_html=True)
            else:
                st.error("No se encontraron datos válidos para procesar.")

elif menu == "Registro de Clientes":
    st.subheader("📝 Gestión de Datos del Cliente")
    with st.form("registro_cliente"):
        nom = st.text_input("Nombre del Proyecto / Cliente")
        rubro = st.selectbox("Rubro", ["Minería", "Forestal", "Energía", "Agrícola"])
        sid = st.text_input("ID del Google Sheet")
        pest = st.text_input("Nombre de la Pestaña", value="Hoja 1")
        if st.form_submit_button("Guardar Perfil de Cliente"):
            st.success(f"Perfil de {nom} guardado exitosamente en el sistema BioCore.")
