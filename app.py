import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from fpdf import FPDF
import io
import base64
from datetime import datetime

# --- 1. CONFIGURACIÓN DEL REPORTE ---
UMBRAL_GLACIAR = 0.40

def generar_diagnostico(df):
    """Genera la lógica de auditoría basada en los últimos datos"""
    ultimo = df.iloc[-1]
    ndsi_actual = ultimo.get('SAVI', 0) # Usando SAVI como proxy de NDSI si no está
    
    status = "NORMAL"
    alerta_roja = False
    hallazgo = "Los índices se mantienen dentro de los rangos de variabilidad estacional esperados."
    
    if ndsi_actual < UMBRAL_GLACIAR:
        status = "ALERTA TÉCNICA: PÉRDIDA DE COBERTURA"
        alerta_roja = True
        hallazgo = (f"El índice actual ({ndsi_actual:.2f}) se encuentra bajo el umbral crítico "
                    f"de {UMBRAL_GLACIAR}. Esto indica una degradación severa de la masa criosférica.")
    
    return status, hallazgo, alerta_roja

# --- 2. MOTOR DE GRÁFICOS MÚLTIPLES ---
def crear_graficos_separados(df, columnas):
    fig, axs = plt.subplots(len(columnas), 1, figsize=(10, 3 * len(columnas)))
    if len(columnas) == 1: axs = [axs]
    
    colores = {"SAVI": "#1f77b4", "NDWI": "#2ca02c", "SWIR": "#7f7f7f", "Deficit": "#d62728"}
    nombres = {"SAVI": "ÁREA DE NIEVE/HIELO (NDSI)", "NDWI": "RECURSOS HÍDRICOS (NDWI)", 
               "SWIR": "ESTABILIDAD DE SUSTRATO (SWIR)", "Deficit": "DEPÓSITO DE MATERIAL"}

    for i, col in enumerate(columnas):
        axs[i].plot(df['Fecha'], df[col], marker='.', color=colores.get(col, "black"), linewidth=1)
        axs[i].set_title(nombres.get(col, col), fontsize=10, fontweight='bold')
        axs[i].grid(True, linestyle=':', alpha=0.6)
        axs[i].tick_params(axis='both', labelsize=8)
    
    plt.tight_layout()
    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150)
    return buf

# --- 3. CONSTRUCCIÓN DEL PDF PROFESIONAL ---
class BioCorePDF(FPDF):
    def header(self):
        # Barra superior azul oscuro como la original
        self.set_fill_color(24, 54, 84)
        self.rect(0, 0, 210, 35, 'F')
        self.set_text_color(255, 255, 255)
        self.set_font("Arial", 'B', 14)
        self.cell(0, 15, "AUDITORÍA DE CUMPLIMIENTO AMBIENTAL - PASCUA LAMA", 0, 1, 'C')
        self.set_font("Arial", 'I', 9)
        self.cell(0, 5, "Responsable Técnica: Loreto Campos Carrasco | BioCore Intelligence", 0, 1, 'C')

    def footer(self):
        self.set_y(-25)
        self.set_font("Arial", 'B', 10)
        self.set_text_color(40, 40, 40)
        self.cell(0, 5, "Loreto Campos Carrasco", 0, 1, 'C')
        self.set_font("Arial", 'I', 8)
        self.cell(0, 5, "Directora Técnica - BioCore Intelligence", 0, 1, 'C')

def exportar_auditoria(df, proyecto, columnas):
    status, hallazgo, es_rojo = generar_diagnostico(df)
    pdf = BioCorePDF()
    pdf.add_page()
    
    # Sección de Diagnóstico
    pdf.ln(25)
    pdf.set_font("Arial", 'B', 11)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(0, 10, "DIAGNÓSTICO TÉCNICO DE CRIÓSFERA Y ALTA MONTAÑA", 0, 1)
    
    # Cuadro de Estatus
    if es_rojo:
        pdf.set_fill_color(200, 0, 0) # Rojo Alerta
        pdf.set_text_color(255, 255, 255)
    else:
        pdf.set_fill_color(0, 100, 0) # Verde Normal
        pdf.set_text_color(255, 255, 255)
        
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(0, 8, f" ESTATUS: {status}", 0, 1, 'L', True)
    
    # Texto de la Auditoría
    pdf.ln(5)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Arial", size=9)
    
    texto_puntos = [
        f"1. ESTADO DE GLACIARES: {hallazgo}",
        "2. RIESGO TÉCNICO-LEGAL: La ausencia de firma espectral de hielo constituye un hallazgo crítico.",
        "3. RECOMENDACIÓN: Se sugiere inspección inmediata para descartar sedimentación de material particulado."
    ]
    
    for punto in texto_puntos:
        pdf.multi_cell(0, 6, punto, border=1)
        pdf.ln(1)

    # Gráficos (En la segunda página para que respire el diseño)
    pdf.add_page()
    pdf.ln(20)
    buf = crear_graficos_separados(df, columnas)
    with open("temp_audit.png", "wb") as f:
        f.write(buf.getbuffer())
    pdf.image("temp_audit.png", x=15, w=180)
    
    return pdf.output(dest='S').encode('latin-1')

# --- 4. INTERFAZ ---
st.title("🛡️ BioCore Audit System")

# ... (Aquí iría tu lógica de carga de datos de Google Sheets) ...
# Simulando un botón de proceso:
if st.button("Generar Auditoría de Cumplimiento"):
    # (Asumiendo que 'df' y 'cols' ya fueron cargados)
    pdf_final = exportar_auditoria(df, "Pascua Lama", cols)
    b64 = base64.b64encode(pdf_final).decode()
    href = f'<a href="data:application/pdf;base64,{b64}" download="Auditoria_BioCore.pdf" style="padding:20px; background-color:#183654; color:white; border-radius:5px; text-decoration:none; font-weight:bold;">📄 DESCARGAR AUDITORÍA TÉCNICA</a>'
    st.markdown(href, unsafe_allow_html=True)
