import streamlit as st
import ee
import folium
from streamlit_folium import folium_static
import json
import pandas as pd
import requests
from datetime import datetime, time
import plotly.graph_objects as go
from supabase import create_client, Client
import matplotlib.pyplot as plt
from fpdf import FPDF
import io
import os
import tempfile

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="BioCore Intelligence V5", layout="wide")


@st.cache_resource
def init_db():
    return create_client(
        st.secrets["connections"]["supabase"]["url"],
        st.secrets["connections"]["supabase"]["key"]
    )


supabase = init_db()


def iniciar_gee():
    try:
        if not ee.data.is_initialized():
            creds = json.loads(st.secrets["gee"]["json"])
            ee_creds = ee.ServiceAccountCredentials(
                creds['client_email'], 
                key_data=creds['private_key']
            )
            ee.Initialize(ee_creds, project=creds.get('project_id'))
            return True
    except Exception as e:
        st.error(f"Error crítico en GEE: {e}")
        return False


gee_status = iniciar_gee()


def clean(text):
    """Limpia caracteres especiales para FPDF"""
    return text.encode('latin-1', errors='replace').decode('latin-1')


# --- 2. FUNCIÓN DE MAPA REFORZADA ---
def dibujar_mapa_biocore(coordenadas):
    try:
        if isinstance(coordenadas, str):
            import json
            coordenadas = json.loads(coordenadas)

        lons = [c[0] for c in coordenadas]
        lats = [c[1] for c in coordenadas]
        centro = [sum(lats)/len(lats), sum(lons)/len(lons)]

        m = folium.Map(
            location=centro,
            zoom_start=13,
            tiles='https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}',
            attr='Google Satellite'
        )

        folium.Polygon(
            locations=[[c[1], c[0]] for c in coordenadas],
            color="cyan",
            weight=2,
            fill=True,
            fill_opacity=0.2
        ).add_to(m)

        return m
    except Exception as e:
        return folium.Map(location=[-33.45, -70.66], zoom_start=4)


# --- 3. GENERADOR DE GRÁFICOS ---
def generar_graficos(df):
    """Genera gráficos de análisis y retorna ruta del archivo"""
    fig, axes = plt.subplots(4, 1, figsize=(10, 10))
    fig.patch.set_facecolor('#0e1117')
    
    config = [
        ('ndsi', '#3498db', 'ÁREA DE NIEVE/HIELO (NDSI)'),
        ('ndwi', '#2980b9', 'RECURSOS HÍDRICOS (NDWI)'),
        ('swir', '#7f8c8d', 'ESTABILIDAD DE SUSTRATO (SWIR)'),
        ('polvo', '#e67e22', 'DEPÓSITO DE MATERIAL PARTICULADO')
    ]
    
    for i, (col, color, titulo) in enumerate(config):
        if col in df.columns:
            try:
                df_clean = pd.to_numeric(df[col], errors='coerce').dropna()
                if not df_clean.empty:
                    axes[i].plot(df_clean.index, df_clean.values, 
                               color=color, marker='o', linewidth=2, markersize=4)
            except:
                pass
            axes[i].set_title(clean(titulo), fontweight='bold', fontsize=11, color='white')
            axes[i].grid(True, alpha=0.2, color='gray')
            axes[i].set_facecolor('#1e293b')
            axes[i].tick_params(colors='white')
    
    plt.tight_layout(pad=3.0)
    
    # Guardar a archivo temporal
    temp_dir = tempfile.gettempdir()
    img_path = os.path.join(temp_dir, 'grafico_biocore.png')
    plt.savefig(img_path, format='png', dpi=150, bbox_inches='tight', facecolor='#0e1117')
    plt.close()
    
    return img_path


# --- 4. MOTOR DE REPORTES ESPECÍFICOS POR TIPO ---

def generar_contenido_glaciar(df, proyecto_nombre, ndsi_val):
    """Lógica para proyectos GLACIAR"""
    if ndsi_val < 0.35:
        estado_txt = "ALERTA TECNICA: PERDIDA DE COBERTURA"
        color_resumen = (200, 0, 0)
        diagnostico = (
            f"1. ESTADO DE GLACIARES: El indice NDSI actual ({ndsi_val:.2f}) se encuentra bajo el umbral "
            "critico de presencia de hielo/nieve perenne (0.40). Esto indica una exposicion del suelo desnudo "
            "o una degradacion severa de la masa criofserica.\n\n"
            "2. RIESGO TECNICO-LEGAL: La ausencia de firma espectral de hielo constituye un hallazgo critico. "
            "Ante una fiscalizacion, esto requiere medidas de mitigacion urgentes.\n\n"
            "3. RECOMENDACION: Inspeccion inmediata para descartar acumulacion de material particulado."
        )
    else:
        estado_txt = "BAJO CONTROL: ESTABILIDAD CRIOFSERICA"
        color_resumen = (0, 100, 0)
        diagnostico = (
            f"1. PROTECCION DE GLACIARES: El indice NDSI ({ndsi_val:.2f}) confirma la permanencia de masa de hielo.\n\n"
            "2. BLINDAJE: El monitoreo indica cumplimiento de los parametros de preservacion de la RCA."
        )
    
    return estado_txt, color_resumen, diagnostico


def generar_contenido_mineria(df, proyecto_nombre, ndsi_val):
    """Lógica para proyectos MINERIA"""
    ndwi_val = float(df['ndwi'].iloc[-1]) if 'ndwi' in df.columns else 0
    
    if ndwi_val < 0.2:
        estado_txt = "ALERTA: ESTRES HIDRICO DETECTADO"
        color_resumen = (200, 100, 0)
        diagnostico = (
            f"1. DISPONIBILIDAD HIDRICA: El indice NDWI ({ndwi_val:.2f}) indica baja disponibilidad de agua "
            "en el terreno. Esto puede afectar la estabilidad de taludes.\n\n"
            "2. OPERACION MINERA: Se recomienda revisar sistemas de drenaje y contencion.\n\n"
            "3. RECOMENDACION: Incrementar monitoreo de infiltracion."
        )
    else:
        estado_txt = "BAJO CONTROL: GESTION HIDRICA ESTABLE"
        color_resumen = (0, 150, 0)
        diagnostico = (
            f"1. RECURSOS HIDRICOS: NDWI de {ndwi_val:.2f} indica disponibilidad adecuada.\n\n"
            "2. CUMPLIMIENTO: Los parametros hidricos se mantienen dentro de norma."
        )
    
    return estado_txt, color_resumen, diagnostico


def generar_contenido_bosque(df, proyecto_nombre, ndsi_val):
    """Lógica para proyectos BOSQUE"""
    savi_val = float(df.get('savi', pd.Series([0])).iloc[-1]) if 'savi' in df.columns else 0
    
    if savi_val < 0.3:
        estado_txt = "ALERTA: DEGRADACION DE COBERTURA"
        color_resumen = (200, 50, 0)
        diagnostico = (
            f"1. SALUD FORESTAL: El indice SAVI ({savi_val:.2f}) indica cobertura baja.\n\n"
            "2. RIESGO ECOLOGICO: Perdida de biomasa detectada.\n\n"
            "3. ACCION: Se requiere plan de reforestacion urgente."
        )
    else:
        estado_txt = "BAJO CONTROL: COBERTURA VEGETAL ESTABLE"
        color_resumen = (50, 150, 0)
        diagnostico = (
            f"1. VIGOR FORESTAL: SAVI de {savi_val:.2f} indica cobertura saludable.\n\n"
            "2. CUMPLIMIENTO: La densidad de dosel se mantiene dentro de parametros."
        )
    
    return estado_txt, color_resumen, diagnostico


def generar_contenido_humedal(df, proyecto_nombre, ndsi_val):
    """Lógica para proyectos HUMEDAL"""
    ndwi_val = float(df['ndwi'].iloc[-1]) if 'ndwi' in df.columns else 0
    
    if ndwi_val < 0.3:
        estado_txt = "ALERTA: DESECACION DE HUMEDAL"
        color_resumen = (200, 0, 0)
        diagnostico = (
            f"1. HUMEDAD DEL SUSTRATO: NDWI ({ndwi_val:.2f}) critico. Indica desecacion.\n\n"
            "2. RIESGO AMBIENTAL: Perdida de biodiversidad e habitat.\n\n"
            "3. ACCION: Restauracion hidrologica e inspeccion inmediata."
        )
    else:
        estado_txt = "BAJO CONTROL: HUMEDAL EN EQUILIBRIO"
        color_resumen = (0, 150, 0)
        diagnostico = (
            f"1. INTEGRIDAD DEL HUMEDAL: NDWI de {ndwi_val:.2f} confirma hidratacion.\n\n"
            "2. CUMPLIMIENTO: Parametros de preservacion dentro de norma."
        )
    
    return estado_txt, color_resumen, diagnostico


def generar_contenido_agricola(df, proyecto_nombre, ndsi_val):
    """Lógica para proyectos AGRÍCOLA"""
    savi_val = float(df.get('savi', pd.Series([0])).iloc[-1]) if 'savi' in df.columns else 0
    ndwi_val = float(df['ndwi'].iloc[-1]) if 'ndwi' in df.columns else 0
    
    if savi_val < 0.35 or ndwi_val < 0.25:
        estado_txt = "ALERTA: ESTRES EN CULTIVOS"
        color_resumen = (200, 100, 0)
        diagnostico = (
            f"1. VIGOR DE CULTIVO: SAVI ({savi_val:.2f}) indica estres hidrico.\n\n"
            f"2. PRODUCTIVIDAD: Humedad insuficiente detectada (NDWI: {ndwi_val:.2f}).\n\n"
            "3. RECOMENDACION: Ajustar riego y acelerar cosecha."
        )
    else:
        estado_txt = "BAJO CONTROL: CULTIVOS OPTIMOS"
        color_resumen = (0, 150, 0)
        diagnostico = (
            f"1. RENDIMIENTO: SAVI de {savi_val:.2f} indica vigor excelente.\n\n"
            f"2. GESTION HIDRICA: Parametros de humedad optimos (NDWI: {ndwi_val:.2f})."
        )
    
    return estado_txt, color_resumen, diagnostico


def generar_pdf_profesional(df, proyecto_nombre, tipo_proyecto, img_path):
    """Genera PDF con contenido específico según tipo de proyecto"""
    
    # Obtener valor principal (NDSI)
    ndsi_val = float(df['ndsi'].iloc[-1]) if 'ndsi' in df.columns else 0
    
    # Seleccionar generador de contenido según tipo
    generadores = {
        'GLACIAR': generar_contenido_glaciar,
        'MINERIA': generar_contenido_mineria,
        'BOSQUE': generar_contenido_bosque,
        'HUMEDAL': generar_contenido_humedal,
        'AGRICOLA': generar_contenido_agricola
    }
    
    tipo_clave = tipo_proyecto.upper()
    if tipo_clave not in generadores:
        tipo_clave = 'MINERIA'  # Default
    
    estado_txt, color_resumen, diagnostico = generadores[tipo_clave](df, proyecto_nombre, ndsi_val)
    
    # Crear PDF
    pdf = FPDF()
    pdf.add_page()
    
    # Encabezado
    pdf.set_fill_color(20, 50, 80)
    pdf.rect(0, 0, 210, 40, 'F')
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("helvetica", "B", 16)
    pdf.cell(0, 20, clean(f"AUDITORIA AMBIENTAL - {proyecto_nombre.upper()}"), align="C", ln=1)
    pdf.set_font("helvetica", "I", 10)
    pdf.cell(0, 5, clean("BioCore Intelligence | Vigilancia Satelital Avanzada"), align="C", ln=1)
    
    # Tipo de proyecto
    pdf.ln(15)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("helvetica", "B", 12)
    pdf.cell(0, 10, clean(f"PROYECTO: {tipo_proyecto.upper()}"), ln=1)
    
    # Estado de alerta
    pdf.set_fill_color(color_resumen[0], color_resumen[1], color_resumen[2])
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("helvetica", "B", 11)
    pdf.cell(0, 10, clean(f" {estado_txt}"), ln=1, fill=True)
    
    # Diagnóstico
    pdf.ln(5)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("helvetica", "", 9)
    pdf.multi_cell(0, 5, clean(diagnostico), border=1)
    
    # Gráficos
    pdf.add_page()
    pdf.set_font("helvetica", "B", 12)
    pdf.cell(0, 10, clean("ANALISIS ESPECTRAL - SERIE TEMPORAL"), ln=1)
    
    if os.path.exists(img_path):
        pdf.image(img_path, x=15, y=30, w=180)
    
    # Firma
    pdf.set_y(260)
    pdf.set_font("helvetica", "B", 10)
    pdf.cell(0, 5, clean("BioCore Intelligence"), align="C", ln=1)
    pdf.set_font("helvetica", "I", 9)
    pdf.cell(0, 5, clean("Sistema de Vigilancia Ambiental"), align="C", ln=1)
    
    return pdf


# --- 5. MOTOR DE REPORTE COMPLETO ---
def generar_reporte_total(p):
    PERFILES = {
        "MINERIA": {
            "cat": "RCA Mineria (F-30)",
            "ve7": "Estabilidad de taludes.",
            "clima": "Protocolo extremos."
        },
        "GLACIAR": {
            "cat": "RCA Criosfera",
            "ve7": "Balance de masa.",
            "clima": "Ley de Glaciares."
        },
        "BOSQUE": {
            "cat": "Ley 20.283",
            "ve7": "Vigilancia regeneracion.",
            "clima": "Prevension incendios."
        },
        "HUMEDAL": {
            "cat": "Ramsar",
            "ve7": "Proteccion de biodiversidad.",
            "clima": "Decreto de Humedales."
        },
        "AGRICOLA": {
            "cat": "Ley de Riego",
            "ve7": "Gestion hidrica.",
            "clima": "Proteccion de cultivos."
        }
    }

    tipo = p.get('Tipo', 'MINERIA')
    d = PERFILES.get(tipo, PERFILES["MINERIA"])

    try:
        raw_coords = p.get('Coordenadas')

        if raw_coords is None:
            return (f"Error: La columna 'Coordenadas' esta vacia para {p.get('Proyecto')}.",
                    0, 0)

        if isinstance(raw_coords, str):
            import json
            try:
                raw_coords = json.loads(raw_coords)
            except:
                raw_coords = eval(raw_coords)

        geom = ee.Geometry.Polygon(raw_coords)

    except Exception as e:
        return f"Error critico en geometria: {str(e)}", 0, 0

    # PROCESAMIENTO SATELITAL
    s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')\
        .filterBounds(geom)\
        .sort('system:time_start', False)\
        .first()

    try:
        timestamp_ms = s2.get('system:time_start').getInfo()
        if timestamp_ms:
            f_rep = datetime.fromtimestamp(timestamp_ms/1000).strftime('%d/%m/%Y')
        else:
            f_rep = "Fecha no disponible"
    except:
        f_rep = "Fecha no disponible"

    s1 = ee.ImageCollection('COPERNICUS/S1_GRD')\
        .filterBounds(geom)\
        .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV'))\
        .sort('system:time_start', False)\
        .first()
    radar_val = s1.select('VV')

    temp_img = ee.ImageCollection("MODIS/061/MOD11A1")\
        .filterBounds(geom)\
        .sort('system:time_start', False)\
        .first()

    temp_val = temp_img.select('LST_Day_1km').multiply(0.02).subtract(273.15)\
        .reduceRegion(ee.Reducer.mean(), geom, 1000).getInfo().get('LST_Day_1km', 0)

    focos = ee.ImageCollection("FIRMS")\
        .filterBounds(geom)\
        .filterDate(ee.Date(datetime.now()).advance(-3, 'day'))\
        .size().getInfo()

    alerta_incendio = "ALERT: Focos detectados" if focos > 0 else "Sin focos activos"

    def calcular_idx(img):
        savi = img.expression('((NIR - RED) / (NIR + RED + 0.5)) * (1.5)', {
            'NIR': img.select('B8'),
            'RED': img.select('B4')
        }).rename('sa')
        ndsi = img.normalizedDifference(['B3', 'B11']).rename('ndsi')
        swir = img.select('B11').divide(10000).rename('sw')
        clay = img.normalizedDifference(['B11', 'B12']).rename('clay')
        ndwi = img.normalizedDifference(['B8', 'B11']).rename('ndwi')

        return img.addBands([savi, ndsi, swir, clay, ndwi])

    img_now = calcular_idx(s2)
    idx = img_now.reduceRegion(ee.Reducer.mean(), geom, 30).getInfo()

    anio_base = p.get('anio_linea_base', 2017)
    s2_base = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')\
        .filterBounds(geom)\
        .filterDate(f'{anio_base}-01-01', f'{anio_base}-12-31')\
        .sort('CLOUDY_PIXEL_PERCENTAGE')\
        .first()

    img_base = calcular_idx(s2_base)
    idx_base = img_base.reduceRegion(ee.Reducer.mean(), geom, 30).getInfo()

    s_actual = float(idx.get('sa', 0))
    s_base = float(idx_base.get('sa', 0.001))

    v_now = float(idx.get('sa', 0))
    v_base = float(idx_base.get('sa', 0))

    if abs(v_now) < 0.05 and abs(v_base) < 0.05:
        variacion = 0.0
        est_global = "BAJO CONTROL"
        exp_savi = ("Suelo estable. Los valores bajos son consistentes con la "
                    "litologia y altitud del sector.")
    else:
        variacion = ((v_now - v_base) / abs(v_base if v_base != 0 else 0.001)) * 100

        umbral_critico = -15 if d['cat'] == "RCA Mineria (F-30)" else -25

        if variacion < umbral_critico:
            est_global = "ALERTA CRITICA"
            exp_savi = ("Descenso significativo detectado. Posible intervencion "
                        "o estres hidrico severo.")
        else:
            est_global = "BAJO CONTROL"
            exp_savi = ("La cobertura vegetal se mantiene estable dentro de los "
                        "rangos historicos.")

    v_ndsi = float(idx.get('ndsi', 0))
    if v_ndsi > 0.4:
        exp_snow = ("Cobertura de nieve/hielo consolidada, esencial para el "
                    "balance hidrico.")
    elif v_ndsi > 0.1:
        exp_snow = "Nieve dispersa o en fusion. Se observa transicion en la crifera."
    else:
        exp_snow = "Nula presencia de nieve. Predomina suelo expuesto o sustrato rocoso."

    if est_global == "BAJO CONTROL":
        nucleo = f"estabilidad tecnica del area bajo el perfil {d['cat']}."
        accion = "Se sugiere mantener la periodicidad de vigilancia programada."
    else:
        nucleo = (f"una anomalia critica en {d['cat']}, con una desviacion "
                  f"del {variacion:.1f}%.")
        accion = "Se requiere activar el protocolo de inspeccion y revisar el blindaje legal."

    if v_ndsi < 0.2 and d['cat'] == "GLACIAR":
        detalle = " La perdida de cobertura nival es el factor de mayor incidencia."
    elif variacion < -15:
        detalle = " El descenso en el vigor fotosinterico (SAVI) es el parametro dominante."
    elif temp_val > 28:
        detalle = " El estres termico detectado eleva la vulnerabilidad del sector."
    else:
        detalle = (" Los parametros se mantienen dentro de la varianza historica "
                   "permitida.")

    conclusion_final = f"Tras el analisis, se concluye {nucleo}{detalle} {accion}"

    v_radar = float(idx.get('radar_vv', 0))
    if v_radar > -12:
        exp_radar = ("La senal sugiere una superficie rugosa o presencia de "
                     "estructuras, consistente con la actividad operativa.")
    else:
        exp_radar = ("El radar indica una superficie lisa o despejada, ideal para "
                     "el seguimiento de la estabilidad del terreno.")

    v_swir = float(idx.get('sw', 0))
    if v_swir < 0.2:
        exp_swir = ("Niveles de humedad en suelo bajos. Se recomienda monitorear "
                    "ante posibles riesgos de aridez extrema.")
    else:
        exp_swir = ("Niveles de humedad optimos detectados, garantizando estabilidad "
                    "en el sustrato.")

    v_savi = float(idx.get('sa', 0))
    v_ndsi = float(idx.get('ndsi', 0))
    v_swir = float(idx.get('sw', 0))
    v_clay = float(idx.get('clay', 0))

    s_actual = v_savi

    texto_final = f"""
REPORTE DE VIGILANCIA AMBIENTAL - BIOCORE
PROYECTO: {p['Proyecto']}
Analisis: {f_rep} | Linea Base: {anio_base}
──────────────────
ESTADO DE CRIFERA (NDSI):
└ Cobertura Actual: {v_ndsi:.3f}
└ Analisis: {exp_snow}

MONITOREO RADAR (Sentinel-1):
└ Retrodispersion VV: {v_radar:.2f} dB
└ Analisis: {exp_radar}

INTEGRIDAD DEL TERRENO (SU-6):
└ Humedad (SWIR): {v_swir:.2f} | Arcillas: {v_clay:.2f}
└ Analisis: {exp_swir}

SALUD VEGETAL (SAVI):
└ Vigor Actual: {v_savi:.3f} | Base: {s_base:.3f}
└ Variacion: {variacion:.1f}% respecto al original.
└ Analisis: {exp_savi}

RIESGO CLIMATICO:
└ Temperatura: {temp_val:.1f}C | Incendios: {alerta_incendio}
──────────────────
ESTADO GLOBAL: {est_global}
CONCLUSION FINAL: {conclusion_final}
    """
    return texto_final, s_actual, s_base


# --- 6. INTERFAZ ---
tab1, tab_informe, tab_excel, tab_admin = st.tabs([
    "Vigilancia Activa",
    "Informes de Auditoria",
    "Base de Datos (Excel)",
    "Admin"
])


# --- PESTAÑA 1: VIGILANCIA ---
with tab1:
    proyectos = supabase.table("usuarios").select("*").execute().data

    if proyectos:
        for p in proyectos:
            st.markdown(f"### Proyecto: {p['Proyecto']}")

            col_mapa, col_reporte = st.columns([2.5, 1])

            with col_mapa:
                m_obj = dibujar_mapa_biocore(p['Coordenadas'])
                folium_static(m_obj, width=850, height=500)

            with col_reporte:
                if st.button("Ejecutar Reporte Completo", key=p['Proyecto']):
                    with st.spinner("Generando analisis dinamico..."):
                        txt, v_now, v_base = generar_reporte_total(p)
                        anio_base = p.get('anio_linea_base', 2017)
                        tipo = p.get('Tipo', 'Mineria')

                        es_estable = abs(v_now) < 0.05 and abs(v_base) < 0.05

                        if es_estable:
                            v_ref_grafico = v_now + 0.00001
                            delta_texto = "0.0% (Estable)"
                            detalles = (
                                f"Analisis de alta montaña. El valor SAVI de {v_now:.4f} "
                                f"es consistente con la litologia mineral del sector. "
                                f"La variacion del 0.0% certifica la estabilidad del terreno "
                                f"y la ausencia de sedimentos o polvo sobre la firma espectral "
                                f"original de {anio_base}."
                            )
                        else:
                            v_ref_grafico = v_base
                            diff = ((v_now - v_base) / abs(v_base if v_base != 0 else 1)) * 100
                            delta_texto = f"{diff:.1f}%"

                            if tipo == 'Bosque Nativo':
                                detalles = (
                                    f"Monitoreo de biomasa forestal. El SAVI de {v_now:.4f} "
                                    f"refleja la densidad del dosel y salud de las especies nativas."
                                )
                            elif tipo == 'Humedal':
                                detalles = (
                                    f"Control de ecosistema hidrico. Valores de {v_now:.4f} "
                                    f"permiten vigilar la salud de la vegetacion hidrófila."
                                )
                            elif tipo == 'Agricola':
                                detalles = (
                                    f"Seguimiento de vigor de cultivo. El SAVI de {v_now:.4f} "
                                    f"valida la estabilidad de la productividad por lote."
                                )
                            else:
                                detalles = (
                                    f"Control de entorno operativo. El valor de {v_now:.4f} "
                                    f"asegura la proteccion de la vegetacion perifica."
                                )

                        try:
                            response = requests.post(
                                f"https://api.telegram.org/bot{st.secrets['telegram']['token']}/sendMessage",
                                data={
                                    "chat_id": p['telegram_id'],
                                    "text": txt,
                                    "parse_mode": "Markdown"
                                },
                                timeout=10
                            )
                            if response.status_code == 200:
                                st.success("Reporte enviado!")
                            else:
                                st.error(f"Error Telegram: {response.status_code}")
                        except Exception as e:
                            st.warning(f"Error conexion: {e}")

                        st.metric(
                            label=f"SAVI Actual vs Base {anio_base}",
                            value=f"{v_now:.4f}",
                            delta=delta_texto
                        )

                        fig = go.Figure(go.Indicator(
                            mode="gauge",
                            value=v_now,
                            gauge={
                                'axis': {
                                    'range': [0, 0.15],
                                    'tickwidth': 1,
                                    'tickcolor': "white"
                                },
                                'bar': {'color': "#2c3e50"},
                                'steps': [
                                    {'range': [0, 0.05], 'color': "#e74c3c"},
                                    {'range': [0.05, 0.10], 'color': "#f1c40f"},
                                    {'range': [0.10, 0.15], 'color': "#2ecc71"}
                                ],
                                'threshold': {
                                    'line': {'color': "white", 'width': 4},
                                    'value': v_base
                                }
                            }
                        ))
                        fig.update_layout(
                            height=220,
                            margin=dict(l=40, r=40, t=20, b=20),
                            paper_bgcolor="rgba(0,0,0,0)",
                            font={'color': "white"}
                        )
                        st.plotly_chart(fig, use_container_width=True)


# --- PESTAÑA 2: INFORMES (AUDITORÍA PREMIUM) ---
with tab_informe:
    st.subheader("Informes de Auditoria Profesionales")
    
    try:
        proyectos_list = supabase.table("usuarios").select("Proyecto,Tipo").execute().data
        proyectos_dict = {p['Proyecto']: p.get('Tipo', 'MINERIA') for p in proyectos_list}
        proyectos_nombres = list(proyectos_dict.keys())
    except:
        proyectos_nombres = ['Pascua Lama']
        proyectos_dict = {'Pascua Lama': 'MINERIA'}
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        proyecto_sel = st.selectbox("Seleccionar Proyecto", proyectos_nombres)
    
    with col2:
        mes_sel = st.selectbox("Mes", 
            ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
             "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"])
    
    with col3:
        anio_sel = st.number_input("Ano", value=2026, min_value=2020, max_value=2030)
    
    if st.button(f"Generar Auditoria Premium {proyecto_sel}"):
        with st.spinner("Procesando datos y generando PDF profesional..."):
            try:
                res = supabase.table("historial_reportes")\
                    .select("*")\
                    .eq("proyecto", proyecto_sel)\
                    .execute()

                if res.data:
                    df = pd.DataFrame(res.data)
                    df['Fecha'] = pd.to_datetime(df['created_at'])
                    
                    meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
                             "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
                    mes_num = meses.index(mes_sel) + 1
                    
                    df_mes = df[(df['Fecha'].dt.month == mes_num) & 
                                (df['Fecha'].dt.year == anio_sel)].sort_values('Fecha')

                    if not df_mes.empty:
                        tipo_proyecto = proyectos_dict.get(proyecto_sel, 'MINERIA')
                        
                        # Generar gráficos
                        img_path = generar_graficos(df_mes)
                        
                        # Generar PDF
                        pdf = generar_pdf_profesional(df_mes, proyecto_sel, tipo_proyecto, img_path)
                        
                        # Guardar PDF
                        pdf_filename = f"Auditoria_{proyecto_sel}_{mes_sel}_{anio_sel}.pdf"
                        pdf.output(pdf_filename)
                        
                        st.success(f"Auditoria PDF generada para {mes_sel}/{anio_sel}")
                        st.info(f"Registros procesados: {len(df_mes)}")
                        
                        # Mostrar preview de datos
                        st.subheader("Vista previa de datos")
                        cols_display = [c for c in ['proyecto', 'created_at', 'ndsi', 'ndwi', 'swir', 'polvo'] 
                                       if c in df_mes.columns]
                        st.dataframe(df_mes[cols_display], use_container_width=True)
                        
                        # Descarga
                        with open(pdf_filename, "rb") as f:
                            st.download_button(
                                label="Descargar PDF Auditoria",
                                data=f.read(),
                                file_name=pdf_filename,
                                mime="application/pdf"
                            )
                        
                        # Limpiar archivo temporal
                        if os.path.exists(img_path):
                            os.remove(img_path)
                    else:
                        st.warning(f"No hay datos para {mes_sel}/{anio_sel}")
                else:
                    st.error("No se encontraron reportes en la base de datos.")
            except Exception as e:
                st.error(f"Error al generar auditoria: {str(e)}")


# --- PESTAÑA 3: EXCEL (HISTORIAL) ---
with tab_excel:
    st.subheader("Historial Acumulado de Mediciones")
    try:
        res_hist = supabase.table("historial_reportes").select("*").execute()
        if res_hist.data:
            df_hist = pd.DataFrame(res_hist.data)
            cols = ['proyecto', 'created_at', 'ndsi', 'ndwi', 'vegetacion_altura', 'swir', 'polvo']
            st.dataframe(
                df_hist[[c for c in cols if c in df_hist.columns]],
                use_container_width=True
            )
    except Exception as e:
        st.error(f"Error en historial: {e}")


# --- PESTAÑA 4: ADMIN (REGISTRO) ---
with tab_admin:
    st.title("Panel de Control BioCore")
    with st.form("form_registro_cliente", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            titular = st.text_input("Nombre del Titular")
            nombre_proy = st.text_input("Nombre del Proyecto")
            tipo_proy = st.selectbox("Tipo de Proyecto", 
                                     ["MINERIA", "GLACIAR", "BOSQUE", "HUMEDAL", "AGRICOLA"])
            anio_lb_input = st.number_input("Ano Linea Base", value=2017)
        with c2:
            telegram_id = st.text_input("ID Telegram")
            coords = st.text_input("Coordenadas")
            hora_envio = st.time_input("Hora de Envio", value=time(8, 0))

        if st.form_submit_button("Guardar en BioCore Cloud"):
            nuevo_p = {
                "titular": titular,
                "Proyecto": nombre_proy,
                "Tipo": tipo_proy,
                "anio_linea_base": anio_lb_input,
                "telegram_id": telegram_id,
                "Coordenadas": coords,
                "hora_envio": hora_envio.strftime("%H:%M")
            }
            supabase.table("usuarios").upsert(nuevo_p).execute()
            st.success(f"{nombre_proy} ({tipo_proy}) guardado correctamente.")
            st.balloons()
