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

# --- 1. CONFIGURACIÓN INICIAL ---
st.set_page_config(page_title="BioCore Intelligence Admin", layout="wide")

# Estilo visual BioCore
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stButton>button { background-color: #183654; color: white; border-radius: 8px; font-weight: bold; height: 3em; }
    .section-header { color: #183654; font-weight: bold; font-size: 24px; border-bottom: 2px solid #183654; padding-bottom: 10px; }
    </style>
    """, unsafe_allow_html=True)

# Autenticación con Google Sheets
try:
    creds_dict = json.loads(st.secrets["GEE_JSON"])
    SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    CREDS = Credentials.from_service_account_info(creds_dict, scopes=SCOPE)
    G_CLIENT = gspread.authorize(CREDS)
except Exception as e:
    st.error(f"Error de credenciales: {e}")
    st.stop()

# Inicializar base de datos de sesión si no existe
if 'clientes_db' not in st.session_state:
    st.session_state.clientes_db = {}

# --- 2. FUNCIONES DE LÓGICA Y GRÁFICOS ---
def obtener_datos_completos(sheet_id, pestaña):
    try:
        sh = G_CLIENT.open_by_key(sheet_id)
        hoja = sh.worksheet(pestaña)
        df = pd.DataFrame(hoja.get_all_records())
        df.columns = [c.strip() for c in df.columns]
        df['Fecha'] = pd.to_datetime(df['Fecha'], dayfirst=True, errors='coerce')
        df = df.dropna(subset=['Fecha']).sort_values('Fecha')
        # Limpieza de índices
        for col in ["SAVI", "NDSI", "NDWI", "SWIR", "Deficit"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        return df
    except:
        return pd.DataFrame()

def generar_graficos_memoria(df):
    fig, axs = plt.subplots(4, 1, figsize=(8, 12))
    config = [
        ("NDSI", "CRIÓSFERA (NIEVE/HIELO)", "#00B0F0"),
        ("NDWI", "RECURSOS HÍDRICOS", "#0070C0"),
        ("SWIR", "ESTABILIDAD DE SUSTRATO", "#7030A0"),
        ("Deficit", "DEPÓSITO DE MATERIAL", "#C00000")
    ]
    for i, (col, titulo, color) in enumerate(config):
        if col in df.columns:
            axs[i].plot(df['Fecha'], df[col], color=color, lw=1.8, marker='o', markersize=4)
            axs[i].set_title(titulo, fontsize=10, fontweight='bold')
            axs[i].grid(True, alpha=0.3)
            axs[i].tick_params(labelsize=8)
    plt.tight_layout(pad=3.0)
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150)
    plt.close()
    return buf

# --- 3. REPORTE TÉCNICO PDF ---
class BioCorePDF(FPDF):
    def header(self):
        self.set_fill_color(24, 54, 84)
        self.rect(0, 0, 210, 35, 'F')
        self.set_text_color(255, 255, 255)
        self.set_font("Arial", 'B', 15)
        self.cell(0, 15, "AUDITORÍA DE CUMPLIMIENTO AMBIENTAL", 0, 1, 'C')
        self.set_font("Arial", 'I', 8)
        self.cell(0, 5, "Responsable Técnica: Loreto Campos Carrasco | BioCore Intelligence", 0, 1, 'C')

def crear_pdf_final(df, nombre_p):
    info = st.session_state.clientes_db[nombre_p]
    ultimo = df.iloc[-1]
    pdf = BioCorePDF()
    
    # Pág 1: Diagnóstico
    pdf.add_page()
    pdf.ln(25)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, f"PROYECTO: {nombre_p.upper()}", 0, 1)
    
    # Alerta Visual
    val_ndsi = ultimo.get('NDSI', 0)
    pdf.set_fill_color(200, 0, 0) if val_ndsi < 0.4 else pdf.set_fill_color(0, 100, 0)
    pdf.set_text_color(255, 255, 255)
    status = "ALERTA TÉCNICA: PÉRDIDA DE COBERTURA" if val_ndsi < 0.4 else "ESTATUS: CUMPLIMIENTO NORMAL"
    pdf.cell(0, 10, f" {status}", 0, 1, 'L', True)
    
    pdf.ln(5)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", '', 10)
    resumen = (f"Ubicación: {info.get('region', 'N/A')}\n"
               f"Última medición: {ultimo['Fecha'].strftime('%d/%m/%Y')}\n\n"
               f"ANÁLISIS TÉCNICO:\n"
               f"- Cobertura Nival (NDSI): {val_ndsi:.4f}\n"
               f"- Presencia hídrica (NDWI): {ultimo.get('NDWI', 0):.4f}\n"
               f"- Estabilidad Suelo (SWIR): {ultimo.get('SWIR', 0):.4f}\n\n"
               f"CONCLUSIÓN: Se requiere monitoreo continuo para asegurar la estabilidad del área.")
    pdf.multi_cell(0, 6, resumen)

    # Pág 2: Gráficos
    pdf.add_page()
    pdf.ln(20)
    img_buf = generar_graficos_memoria(df)
    with open("temp_plot.png", "wb") as f: f.write(img_buf.getbuffer())
    pdf.image("temp_plot.png", x=15, y=40, w=180)
    
    return pdf.output(dest='S').encode('latin-1')

# --- 4. INTERFAZ PRINCIPAL ---
st.sidebar.title("BioCore Intelligence")
menu = st.sidebar.radio("Navegación", ["Dashboard Auditoría", "Gestión de Proyectos"])

if menu == "Dashboard Auditoría":
    st.markdown('<p class="section-header">🛡️ Panel de Auditoría Satelital</p>', unsafe_allow_html=True)
    
    if not st.session_state.clientes_db:
        st.warning("⚠️ No hay proyectos registrados. Ve a 'Gestión de Proyectos'.")
    else:
        p_sel = st.selectbox("Seleccione Proyecto Activo:", list(st.session_state.clientes_db.keys()))
        info = st.session_state.clientes_db[p_sel]
        
        col_data, col_map = st.columns([1, 1.5])
        
        with col_data:
            st.info(f"**Región:** {info.get('region', 'N/A')}")
            if st.button("🔄 ANALIZAR Y GENERAR REPORTE"):
                with st.spinner("Descargando datos..."):
                    df_final = obtener_datos_completos(info['sheet_id'], info['pestaña'])
                    if not df_final.empty:
                        pdf_bytes = crear_pdf_final(df_final, p_sel)
                        b64 = base64.b64encode(pdf_bytes).decode()
                        st.markdown(f'<a href="data:application/pdf;base64,{b64}" download="BioCore_{p_sel}.pdf" style="text-decoration:none;"><div style="text-align:center; padding:15px; background-color:#183654; color:white; border-radius:8px; font-weight:bold;">📥 DESCARGAR INFORME TÉCNICO</div></a>', unsafe_allow_html=True)
                        st.success("Análisis completado con éxito.")
                    else:
                        st.error("No se encontraron datos en la hoja. Verifica el ID y la Pestaña.")

        with col_map:
            m = folium.Map(location=info['coords'][0], zoom_start=14)
            folium.Polygon(locations=info['coords'], color="#183654", fill=True, fill_opacity=0.4).add_to(m)
            folium_static(m)

else:
    st.markdown('<p class="section-header">📁 Registro de Clientes y Polígonos</p>', unsafe_allow_html=True)
    
    with st.form("registro_p"):
        nom = st.text_input("Nombre del Proyecto")
        sid = st.text_input("ID de Google Sheet")
        pes = st.text_input("Nombre de la Pestaña (ej: Hoja 1)")
        reg = st.text_input("Región / Ubicación")
        st.markdown("**Pegue Coordenadas del Polígono:** (lat, lon; lat, lon...)")
        raw_c = st.text_area("Bloque de coordenadas", help="Ejemplo: -29.31, -70.01; -29.31, -70.02...")
        
        if st.form_submit_button("Guardar Proyecto"):
            try:
                # Procesar pegado masivo
                limpio = raw_c.replace('\n', ';').strip()
                pares = [p.split(',') for p in limpio.split(';') if ',' in p]
                coords_ok = [[float(lat.strip()), float(lon.strip())] for lat, lon in pares]
                
                if len(coords_ok) >= 3:
                    st.session_state.clientes_db[nom] = {
                        "sheet_id": sid, "pestaña": pes, "region": reg, "coords": coords_ok
                    }
                    st.success(f"✅ Proyecto '{nom}' registrado.")
                    st.rerun()
                else:
                    st.error("Se necesitan al menos 3 puntos para el polígono.")
            except:
                st.error("Error de formato en las coordenadas.")

    st.subheader("Historial de Registros")
    if st.session_state.clientes_db:
        st.dataframe(pd.DataFrame.from_dict(st.session_state.clientes_db, orient='index'), use_container_width=True)
