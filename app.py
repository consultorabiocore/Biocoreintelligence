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
import os
import tempfile
import hashlib

# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="BioCore Intelligence V7", layout="wide")

# CSS personalizado para sidebar
st.markdown("""
<style>
    [data-testid="stSidebar"] {
        background-color: #0e1117;
    }
    .sidebar-title {
        color: white;
        font-size: 18px;
        font-weight: bold;
        margin-bottom: 10px;
    }
</style>
""", unsafe_allow_html=True)


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


# === SISTEMA DE AUTENTICACIÓN ===
def hash_password(password):
    """Genera hash SHA256 de contraseña"""
    return hashlib.sha256(password.encode()).hexdigest()


def verificar_credenciales_usuario(proyecto, password):
    """Verifica credenciales del cliente"""
    try:
        res = supabase.table("usuarios").select("*").eq("Proyecto", proyecto).execute()
        if res.data:
            cliente = res.data[0]
            password_guardada = cliente.get('password_cliente', '')
            if password_guardada and hash_password(password) == password_guardada:
                return True, cliente
        return False, None
    except:
        return False, None


def es_admin(contraseña_admin):
    """Verifica si es el admin (contraseña maestra)"""
    contraseña_admin_hash = st.secrets.get("admin_password_hash", 
                                           hash_password("biocore2024admin"))
    return hash_password(contraseña_admin) == contraseña_admin_hash


# === PROTOCOLO DE VALIDACIÓN DE LÍNEA BASE ESPECTRAL ===

class ProtocoloValidacionBaseline:
    """
    Sistema de validación que distingue:
    - Cambios reales (áreas con recursos)
    - Ruido de sensor (áreas mineral/áridas)
    """
    
    RANGO_INERCIA = {
        'savi_suelo_desnudo': 0.10,
        'ndwi_seco_historico': 0.0,
        'ndsi_fuera_nieves': 0.20,
    }
    
    DELTA_ABSOLUTA_MINIMA = 0.05
    TOLERANCIA_RELATIVA_MINERAL = 0.20
    
    @staticmethod
    def clasificar_terreno_base(savi_base, ndwi_base, ndsi_base):
        if ndsi_base >= 0.35:
            return 'CRIOSFERA', "Zona con nieve/hielo permanente"
        elif savi_base >= 0.30:
            return 'VEGETADO', "Zona con cobertura vegetal significativa"
        elif ndwi_base >= 0.20:
            return 'HIDRICO', "Zona con presencia de agua"
        else:
            return 'MINERAL_ARIDO', "Suelo desnudo, mineral o árido (sin recursos espectrales)"
    
    @staticmethod
    def validar_cambio(v_now, v_base, tipo_indice, tipo_terreno):
        delta_abs = abs(v_now - v_base)
        delta_rel = 0 if v_base == 0 else ((v_now - v_base) / abs(v_base)) * 100
        
        if delta_abs < ProtocoloValidacionBaseline.DELTA_ABSOLUTA_MINIMA:
            return {
                'es_alerta': False,
                'razon': 'Diferencia absoluta < 0.05 (Ruido de sensor)',
                'delta_abs': delta_abs,
                'delta_rel': delta_rel,
                'clasificacion': 'ESTABILIDAD_ESTRUCTURAL'
            }
        
        if tipo_terreno == 'MINERAL_ARIDO':
            if abs(delta_rel) <= ProtocoloValidacionBaseline.TOLERANCIA_RELATIVA_MINERAL * 100:
                return {
                    'es_alerta': False,
                    'razon': f'Variación normal en suelo mineral ({delta_rel:.1f}%)',
                    'delta_abs': delta_abs,
                    'delta_rel': delta_rel,
                    'clasificacion': 'ESTABILIDAD_MINERAL'
                }
        
        if tipo_indice == 'savi' and v_base < ProtocoloValidacionBaseline.RANGO_INERCIA['savi_suelo_desnudo']:
            return {
                'es_alerta': False,
                'razon': 'Línea base indica suelo desnudo (sin biomasa)',
                'delta_abs': delta_abs,
                'delta_rel': delta_rel,
                'clasificacion': 'ESTABILIDAD_MINERAL'
            }
        
        if tipo_indice == 'ndwi' and v_base <= ProtocoloValidacionBaseline.RANGO_INERCIA['ndwi_seco_historico']:
            if v_now > v_base:
                return {
                    'es_alerta': True,
                    'razon': 'ANOMALÍA: Presencia de agua en zona históricamente seca',
                    'delta_abs': delta_abs,
                    'delta_rel': delta_rel,
                    'clasificacion': 'ANOMALIA_HUMEDAD'
                }
            else:
                return {
                    'es_alerta': False,
                    'razon': 'Zona históricamente seca, variación dentro de norma',
                    'delta_abs': delta_abs,
                    'delta_rel': delta_rel,
                    'clasificacion': 'ESTABILIDAD_HISTORICA'
                }
        
        if tipo_indice == 'ndsi' and v_base < ProtocoloValidacionBaseline.RANGO_INERCIA['ndsi_fuera_nieves']:
            return {
                'es_alerta': False,
                'razon': 'Zona fuera de cota de nieve permanente',
                'delta_abs': delta_abs,
                'delta_rel': delta_rel,
                'clasificacion': 'NORMAL_ESTACIONAL'
            }
        
        if tipo_terreno in ['VEGETADO', 'HIDRICO', 'CRIOSFERA']:
            if delta_rel < -15:
                return {
                    'es_alerta': True,
                    'razon': f'Degradación detectada ({delta_rel:.1f}%)',
                    'delta_abs': delta_abs,
                    'delta_rel': delta_rel,
                    'clasificacion': 'DEGRADACION_REAL'
                }
        
        return {
            'es_alerta': False,
            'razon': 'Variación dentro de tolerancia histórica',
            'delta_abs': delta_abs,
            'delta_rel': delta_rel,
            'clasificacion': 'BAJO_CONTROL'
        }


# === ÍNDICES ESPECTRALES ===
CORRECCIONES_INDICE = {
    'savi_offset': 0.15,
    'ndwi_min_valido': 0.15,
    'swir_offset': 0.10,
    'ndsi_min_hielo': 0.35,
}


def normalizar_indice(valor, tipo_indice):
    """Aplica correcciones para evitar falsos positivos"""
    try:
        valor = float(valor)
        
        if tipo_indice == 'savi':
            valor_corr = valor - CORRECCIONES_INDICE['savi_offset']
            return max(0, valor_corr)
        elif tipo_indice == 'ndwi':
            if valor < CORRECCIONES_INDICE['ndwi_min_valido']:
                return 0.0
            return valor
        elif tipo_indice == 'swir':
            valor_corr = valor - CORRECCIONES_INDICE['swir_offset']
            return max(0, valor_corr)
        elif tipo_indice == 'ndsi':
            if valor < CORRECCIONES_INDICE['ndsi_min_hielo']:
                return 0.0
            return valor
        else:
            return valor
    except:
        return 0.0


# --- 2. FUNCIÓN DE MAPA ---
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
    """Genera gráficos de análisis"""
    try:
        fig, axes = plt.subplots(4, 1, figsize=(10, 10))
        fig.patch.set_facecolor('#0e1117')
        
        config = [
            ('ndsi', '#3498db', 'ÁREA DE NIEVE/HIELO (NDSI)'),
            ('ndwi', '#2980b9', 'RECURSOS HÍDRICOS (NDWI)'),
            ('swir', '#7f8c8d', 'ESTABILIDAD DE SUSTRATO (SWIR)'),
            ('polvo', '#e67e22', 'DEPÓSITO DE MATERIAL PARTICULADO')
        ]
        
        for i, (col, color, titulo) in enumerate(config):
            try:
                if col in df.columns:
                    if col in ['savi', 'ndwi', 'swir', 'ndsi']:
                        df_clean = df[col].apply(lambda x: normalizar_indice(x, col))
                    else:
                        df_clean = pd.to_numeric(df[col], errors='coerce')
                    
                    df_clean = df_clean.dropna()
                    
                    if not df_clean.empty and df_clean.sum() > 0:
                        axes[i].plot(df_clean.index, df_clean.values, 
                                   color=color, marker='o', linewidth=2, markersize=4)
                    else:
                        axes[i].text(0.5, 0.5, 'SIN DATOS', ha='center', va='center', color='red')
            except:
                pass
            
            axes[i].set_title(clean(titulo), fontweight='bold', fontsize=11, color='white')
            axes[i].grid(True, alpha=0.2, color='gray')
            axes[i].set_facecolor('#1e293b')
            axes[i].tick_params(colors='white')
        
        plt.tight_layout(pad=3.0)
        
        temp_dir = tempfile.gettempdir()
        img_path = os.path.join(temp_dir, 'grafico_biocore.png')
        plt.savefig(img_path, format='png', dpi=150, bbox_inches='tight', facecolor='#0e1117')
        plt.close()
        
        return img_path, True
    except Exception as e:
        return None, False


# --- 4. EVALUACIÓN CON PROTOCOLO BASELINE ---

def evaluar_proyecto_con_protocolo(tipo_proyecto, 
                                   ndsi_now, ndwi_now, savi_now, swir_now,
                                   ndsi_base, ndwi_base, savi_base, swir_base):
    """Evaluación inteligente usando Protocolo de Validación de Línea Base"""
    
    # Normalizar valores
    ndsi_corr = normalizar_indice(ndsi_now, 'ndsi')
    ndwi_corr = normalizar_indice(ndwi_now, 'ndwi')
    savi_corr = normalizar_indice(savi_now, 'savi')
    swir_corr = normalizar_indice(swir_now, 'swir')
    
    ndsi_base_corr = normalizar_indice(ndsi_base, 'ndsi')
    ndwi_base_corr = normalizar_indice(ndwi_base, 'ndwi')
    savi_base_corr = normalizar_indice(savi_base, 'savi')
    swir_base_corr = normalizar_indice(swir_base, 'swir')
    
    # Clasificar terreno
    tipo_terreno, desc_terreno = ProtocoloValidacionBaseline.clasificar_terreno_base(
        savi_base_corr, ndwi_base_corr, ndsi_base_corr
    )
    
    # Validar cada índice
    validacion_savi = ProtocoloValidacionBaseline.validar_cambio(
        savi_corr, savi_base_corr, 'savi', tipo_terreno
    )
    
    validacion_ndwi = ProtocoloValidacionBaseline.validar_cambio(
        ndwi_corr, ndwi_base_corr, 'ndwi', tipo_terreno
    )
    
    validacion_ndsi = ProtocoloValidacionBaseline.validar_cambio(
        ndsi_corr, ndsi_base_corr, 'ndsi', tipo_terreno
    )
    
    validacion_swir = ProtocoloValidacionBaseline.validar_cambio(
        swir_corr, swir_base_corr, 'swir', tipo_terreno
    )
    
    # Determinar estado global
    alertas = [validacion_savi, validacion_ndwi, validacion_ndsi, validacion_swir]
    hay_alertas_criticas = any(a['es_alerta'] for a in alertas)
    
    tipo_clave = tipo_proyecto.upper()
    
    # === CONSTRUCCIÓN DE ESTADO FINAL ===
    
    if tipo_terreno == 'MINERAL_ARIDO':
        if not hay_alertas_criticas:
            estado = "BAJO CONTROL: OPERACIÓN NORMAL - SUELO MINERAL"
            color = (0, 150, 0)
            diagnostico = f"""
Línea Base Confirmada: {desc_terreno}
Clasificación del Terreno: {tipo_terreno}

VALIDACIÓN DE ÍNDICES:
• SAVI: {validacion_savi['clasificacion']} ({savi_corr:.4f})
• NDWI: {validacion_ndwi['clasificacion']} ({ndwi_corr:.4f})
• SWIR: {validacion_swir['clasificacion']} ({swir_corr:.4f})
• NDSI: {validacion_ndsi['clasificacion']} ({ndsi_corr:.4f})

Interpretación: Las variaciones detectadas se encuentran dentro del 
rango esperado para suelo mineral/árido. Estabilidad estructural verificada.
            """
            nivel = "NORMAL"
        else:
            estado = "⚠️ ANOMALÍA EN ZONA MINERAL"
            color = (200, 100, 0)
            diagnostico = f"""
Tipo de Terreno: {tipo_terreno}
ANOMALÍA DETECTADA - Fuera de patrón esperado

{'; '.join([f"{a['razon']}" for a in alertas if a['es_alerta']])}
            """
            nivel = "MODERADO"
    
    elif tipo_terreno == 'VEGETADO':
        if validacion_savi['es_alerta']:
            estado = "🔴 ALERTA: DEGRADACIÓN DE COBERTURA VEGETAL"
            color = (200, 50, 0)
            diagnostico = f"""
Tipo de Terreno: {tipo_terreno}
SAVI Base: {savi_base_corr:.4f} -> Actual: {savi_corr:.4f}
Cambio: {validacion_savi['delta_rel']:.1f}% ({validacion_savi['razon']})

Recomendación: Evaluación ecológica inmediata.
            """
            nivel = "CRÍTICO"
        else:
            estado = "BAJO CONTROL: COBERTURA VEGETAL ESTABLE"
            color = (50, 150, 0)
            diagnostico = f"Cobertura vegetal dentro de parámetros normales."
            nivel = "NORMAL"
    
    elif tipo_terreno == 'CRIOSFERA':
        if validacion_ndsi['es_alerta']:
            estado = "🔴 ALERTA CRÍTICA: PÉRDIDA DE COBERTURA NIVAL"
            color = (200, 0, 0)
            diagnostico = f"""
NDSI Base: {ndsi_base_corr:.4f} -> Actual: {ndsi_corr:.4f}
{validacion_ndsi['razon']}

ACCIÓN REQUERIDA: Inspección inmediata.
            """
            nivel = "CRÍTICO"
        else:
            estado = "BAJO CONTROL: CRIOSFERA ESTABLE"
            color = (0, 100, 0)
            diagnostico = f"Cobertura de nieve/hielo dentro de norma histórica."
            nivel = "NORMAL"
    
    elif tipo_terreno == 'HIDRICO':
        if validacion_ndwi['es_alerta']:
            estado = "⚠️ ALERTA: ANOMALÍA HÍDRICA"
            color = (200, 100, 0)
            diagnostico = f"{validacion_ndwi['razon']}"
            nivel = "MODERADO"
        else:
            estado = "BAJO CONTROL: RECURSOS HÍDRICOS ESTABLES"
            color = (0, 150, 0)
            diagnostico = "Humedad dentro de parámetros esperados."
            nivel = "NORMAL"
    
    else:
        estado = "BAJO CONTROL"
        color = (0, 150, 0)
        diagnostico = "Sistema en operación normal."
        nivel = "NORMAL"
    
    return {
        'estado': estado,
        'color': color,
        'diagnostico': diagnostico,
        'nivel': nivel,
        'tipo_terreno': tipo_terreno,
        'savi_actual': savi_corr,
        'savi_base': savi_base_corr,
        'ndsi': ndsi_corr,
        'ndwi': ndwi_corr,
        'swir': swir_corr,
        'validaciones': {
            'savi': validacion_savi,
            'ndwi': validacion_ndwi,
            'ndsi': validacion_ndsi,
            'swir': validacion_swir
        }
    }


# --- 5. GENERADOR DE REPORTE COMPLETO ---

def generar_reporte_total(p):
    """Genera reporte unificado para Telegram y PDF"""
    
    PERFILES = {
        "MINERIA": {"cat": "RCA Minería (F-30)"},
        "GLACIAR": {"cat": "RCA Criosfera"},
        "BOSQUE": {"cat": "Ley 20.283"},
        "HUMEDAL": {"cat": "Ramsar"},
        "AGRICOLA": {"cat": "Ley de Riego"}
    }

    tipo = p.get('Tipo', 'MINERIA')
    perfil = PERFILES.get(tipo, PERFILES["MINERIA"])

    try:
        raw_coords = p.get('Coordenadas')
        if raw_coords is None:
            return {'error': 'Coordenadas vacías', 'tipo': 'error'}

        if isinstance(raw_coords, str):
            import json
            try:
                raw_coords = json.loads(raw_coords)
            except:
                raw_coords = eval(raw_coords)

        geom = ee.Geometry.Polygon(raw_coords)

    except Exception as e:
        return {'error': f'Error en geometría: {str(e)}', 'tipo': 'error'}

    # PROCESAMIENTO SATELITAL
    s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')\
        .filterBounds(geom)\
        .sort('system:time_start', False)\
        .first()

    try:
        timestamp_ms = s2.get('system:time_start').getInfo()
        f_rep = datetime.fromtimestamp(timestamp_ms/1000).strftime('%d/%m/%Y') if timestamp_ms else "N/A"
    except:
        f_rep = "N/A"

    # Temperatura
    temp_img = ee.ImageCollection("MODIS/061/MOD11A1")\
        .filterBounds(geom)\
        .sort('system:time_start', False)\
        .first()

    try:
        temp_val = float(temp_img.select('LST_Day_1km').multiply(0.02).subtract(273.15)\
            .reduceRegion(ee.Reducer.mean(), geom, 1000).getInfo().get('LST_Day_1km', 0))
    except:
        temp_val = 0

    # CÁLCULO DE ÍNDICES
    def calcular_idx(img):
        savi = img.expression('((NIR - RED) / (NIR + RED + 0.5)) * (1.5)', {
            'NIR': img.select('B8'),
            'RED': img.select('B4')
        }).rename('savi')
        ndsi = img.normalizedDifference(['B3', 'B11']).rename('ndsi')
        swir = img.select('B11').divide(10000).rename('swir')
        ndwi = img.normalizedDifference(['B8', 'B11']).rename('ndwi')
        return img.addBands([savi, ndsi, swir, ndwi])

    img_now = calcular_idx(s2)
    idx = img_now.reduceRegion(ee.Reducer.mean(), geom, 30).getInfo()

    # LÍNEA BASE
    anio_base = p.get('anio_linea_base', 2017)
    s2_base = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')\
        .filterBounds(geom)\
        .filterDate(f'{anio_base}-01-01', f'{anio_base}-12-31')\
        .sort('CLOUDY_PIXEL_PERCENTAGE')\
        .first()

    img_base = calcular_idx(s2_base)
    idx_base = img_base.reduceRegion(ee.Reducer.mean(), geom, 30).getInfo()

    # VALORES CRUDOS
    ndsi_now = float(idx.get('ndsi', 0))
    ndwi_now = float(idx.get('ndwi', 0))
    savi_now = float(idx.get('savi', 0))
    swir_now = float(idx.get('swir', 0))

    ndsi_base = float(idx_base.get('ndsi', 0))
    ndwi_base = float(idx_base.get('ndwi', 0))
    savi_base = float(idx_base.get('savi', 0))
    swir_base = float(idx_base.get('swir', 0))

    # EVALUAR CON PROTOCOLO BASELINE
    resultado = evaluar_proyecto_con_protocolo(
        tipo, 
        ndsi_now, ndwi_now, savi_now, swir_now,
        ndsi_base, ndwi_base, savi_base, swir_base
    )

    # Texto para Telegram
    texto_telegram = f"""
╔════════════════════════════════════════╗
║  🛰️ REPORTE BIOCORE {tipo.upper():26s}║
║  {p['Proyecto']:40s}║
╚════════════════════════════════════════╝

📅 Análisis: {f_rep} | Base: {anio_base}
🎯 {resultado['estado']}
💡 Terreno: {resultado['tipo_terreno']}
───────────────────────────────────────

📊 ÍNDICES (Normalizados):
• SAVI: {resultado['savi_actual']:.4f} (Base: {resultado['savi_base']:.4f})
• NDSI: {resultado['ndsi']:.4f} | NDWI: {resultado['ndwi']:.4f}
• SWIR: {resultado['swir']:.4f}

🌡️ Temperatura: {temp_val:.1f}°C

✅ {resultado['diagnostico']}

Riesgo: {resultado['nivel']}
Perfil: {perfil['cat']}
    """

    resultado['texto_telegram'] = texto_telegram
    resultado['temp'] = temp_val
    resultado['fecha'] = f_rep
    resultado['anio_base'] = anio_base
    resultado['tipo'] = tipo
    resultado['perfil'] = perfil['cat']
    resultado['proyecto'] = p['Proyecto']

    return resultado


# --- 6. GENERADOR PDF ---
def generar_pdf_profesional(df, proyecto_nombre, tipo_proyecto, img_path, reporte_data, logo_consultora=None):
    """PDF profesional con protocolo baseline aplicado"""
    
    pdf = FPDF()
    pdf.add_page()
    
    # Encabezado
    pdf.set_fill_color(20, 50, 80)
    pdf.rect(0, 0, 210, 40, 'F')
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("helvetica", "B", 16)
    pdf.cell(0, 20, clean(f"AUDITORÍA {proyecto_nombre.upper()}"), align="C", ln=1)
    pdf.set_font("helvetica", "I", 10)
    pdf.cell(0, 5, clean("BioCore Intelligence V7 - Protocolo Baseline"), align="C", ln=1)
    
    # Logo de consultora (si existe)
    if logo_consultora and os.path.exists(logo_consultora):
        try:
            pdf.image(logo_consultora, x=175, y=5, w=25)
        except:
            pass
    
    # Tipo y terreno
    pdf.ln(10)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("helvetica", "B", 11)
    pdf.cell(0, 8, clean(f"Tipo: {tipo_proyecto} | Terreno: {reporte_data.get('tipo_terreno', 'N/A')}"), ln=1)
    
    # Estado
    color_r, color_g, color_b = reporte_data['color']
    pdf.set_fill_color(color_r, color_g, color_b)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("helvetica", "B", 11)
    pdf.cell(0, 10, clean(f" {reporte_data['estado']}"), ln=1, fill=True)
    
    # Diagnóstico
    pdf.ln(3)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("helvetica", "", 9)
    pdf.multi_cell(0, 4, clean(reporte_data['diagnostico']), border=1)
    
    # Validaciones detalladas
    pdf.ln(5)
    pdf.set_font("helvetica", "B", 10)
    pdf.cell(0, 8, clean("PROTOCOLO DE VALIDACIÓN - ANÁLISIS POR ÍNDICE:"), ln=1)
    pdf.set_font("helvetica", "", 8)
    
    for idx_name, validacion in reporte_data['validaciones'].items():
        txt = f"{idx_name.upper()}: {validacion['clasificacion']} - {validacion['razon']}"
        pdf.multi_cell(0, 4, clean(txt), border=0)
    
    # Gráficos
    pdf.add_page()
    pdf.set_font("helvetica", "B", 12)
    pdf.cell(0, 10, clean("SERIES TEMPORALES - ANÁLISIS ESPECTRAL"), ln=1)
    
    if img_path and os.path.exists(img_path):
        try:
            pdf.image(img_path, x=15, y=30, w=180)
        except:
            pdf.set_text_color(200, 0, 0)
            pdf.cell(0, 10, clean("Gráficos no disponibles"), ln=1)
    
    # Firma
    pdf.set_y(260)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("helvetica", "B", 9)
    pdf.cell(0, 5, clean("BioCore Intelligence V7"), align="C", ln=1)
    pdf.set_font("helvetica", "I", 8)
    pdf.cell(0, 5, clean(f"Protocolo: Validación de Línea Base Espectral"), align="C", ln=1)
    pdf.cell(0, 5, clean(f"{reporte_data['fecha']} | Base: {reporte_data['anio_base']}"), align="C", ln=1)
    
    return pdf


# --- 7. INICIALIZAR SESSION STATE ---
if 'authenticated' not in st.session_state:
    st.session_state['authenticated'] = False
    st.session_state['admin_mode'] = False
    st.session_state['proyecto_cliente'] = None


# --- 8. SIDEBAR CON LOGO Y AUTENTICACIÓN ---

with st.sidebar:
    # Logo
    if os.path.exists("logo_biocore.png"):
        try:
            st.image("logo_biocore.png", width=250)
        except:
            st.info("Logo no disponible")
    
    st.markdown("---")
    
    # Sistema de autenticación
    with st.expander("🔐 Iniciar Sesión", expanded=True):
        proyecto_login = st.text_input("Proyecto", key="login_proyecto")
        password_login = st.text_input("Contraseña", type="password", key="login_pwd")
        admin_mode = st.checkbox("Modo Admin", key="admin_check")
        
        if st.button("Entrar", key="btn_login"):
            if admin_mode:
                if es_admin(password_login):
                    st.session_state['admin_mode'] = True
                    st.session_state['authenticated'] = True
                    st.success("✅ Modo Admin activado")
                else:
                    st.error("❌ Contraseña de admin incorrecta")
            else:
                is_valid, cliente = verificar_credenciales_usuario(proyecto_login, password_login)
                if is_valid:
                    st.session_state['authenticated'] = True
                    st.session_state['proyecto_cliente'] = proyecto_login
                    st.session_state['cliente_data'] = cliente
                    st.success(f"✅ Bienvenido {proyecto_login}")
                else:
                    st.error("❌ Proyecto o contraseña inválidos")
    
    st.markdown("---")
    
    # Info usuario
    if st.session_state.get('authenticated'):
        if st.session_state.get('admin_mode'):
            st.info("🔑 **Sesión Admin Activa**")
        else:
            proyecto = st.session_state.get('proyecto_cliente', 'N/A')
            st.info(f"👤 **Usuario**: {proyecto}")
    
    # Botón logout
    if st.session_state.get('authenticated'):
        if st.button("🚪 Cerrar Sesión"):
            st.session_state['authenticated'] = False
            st.session_state['admin_mode'] = False
            st.session_state['proyecto_cliente'] = None
            st.rerun()


# --- 9. VERIFICACIÓN DE ACCESO ---

if not st.session_state.get('authenticated'):
    st.warning("⚠️ Debes iniciar sesión para acceder a BioCore Intelligence")
    st.stop()


# --- 10. INTERFAZ STREAMLIT ---

tab_names = ["🛰️ Vigilancia", "📋 Auditorías", "📊 Base Datos", "⚙️ Admin", "📖 Guía Protocolo"]
tab_list = st.tabs(tab_names)

tab1, tab_informe, tab_excel, tab_admin, tab_guia = tab_list

# PESTAÑA 1: VIGILANCIA
with tab1:
    try:
        proyectos = supabase.table("usuarios").select("*").execute().data
    except:
        proyectos = []

    if st.session_state.get('admin_mode'):
        proyectos_mostrar = proyectos
    else:
        proyecto_cliente = st.session_state.get('proyecto_cliente')
        proyectos_mostrar = [p for p in proyectos if p.get('Proyecto') == proyecto_cliente]

    if proyectos_mostrar:
        for p in proyectos_mostrar:
            st.markdown(f"### {p['Proyecto']}")

            col_mapa, col_reporte = st.columns([2.5, 1])

            with col_mapa:
                m_obj = dibujar_mapa_biocore(p['Coordenadas'])
                folium_static(m_obj, width=850, height=500)

            with col_reporte:
                if st.button("Ejecutar Reporte", key=f"btn_{p['Proyecto']}"):
                    with st.spinner("Analizando con Protocolo Baseline..."):
                        reporte = generar_reporte_total(p)
                        
                        if reporte.get('tipo') != 'error':
                            try:
                                requests.post(
                                    f"https://api.telegram.org/bot{st.secrets['telegram']['token']}/sendMessage",
                                    data={
                                        "chat_id": p.get('telegram_id'),
                                        "text": reporte['texto_telegram'],
                                        "parse_mode": "Markdown"
                                    },
                                    timeout=10
                                )
                                st.success("✅ Telegram OK")
                            except Exception as e:
                                st.warning(f"⚠️ Telegram: {e}")

                            st.metric(
                                label=f"SAVI vs {reporte['anio_base']}",
                                value=f"{reporte['savi_actual']:.4f}",
                                delta=f"{reporte['savi_base']:.4f}"
                            )

                            col_a, col_b = st.columns(2)
                            with col_a:
                                st.info(f"**Terreno**: {reporte['tipo_terreno']}")
                            with col_b:
                                st.warning(f"**Riesgo**: {reporte['nivel']}")
                            
                            st.success(reporte['estado'])
                            st.write(reporte['diagnostico'])


# PESTAÑA 2: AUDITORÍAS
with tab_informe:
    st.subheader("📋 Generador de Auditorías")
    
    try:
        proyectos_list = supabase.table("usuarios").select("Proyecto,Tipo").execute().data
        proyectos_dict = {p['Proyecto']: p.get('Tipo', 'MINERIA') for p in proyectos_list}
    except:
        proyectos_dict = {}
    
    if st.session_state.get('admin_mode'):
        proyectos_disponibles = list(proyectos_dict.keys())
    else:
        proyecto_cliente = st.session_state.get('proyecto_cliente')
        proyectos_disponibles = [proyecto_cliente] if proyecto_cliente in proyectos_dict else []
    
    if proyectos_disponibles:
        col1, col2, col3 = st.columns(3)
        with col1:
            proyecto = st.selectbox("Proyecto", proyectos_disponibles)
        with col2:
            mes = st.selectbox("Mes", ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
                                       "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"])
        with col3:
            anio = st.number_input("Año", value=2026, min_value=2020)
        
        if st.button("📊 Generar PDF Auditoría"):
            with st.spinner("Procesando..."):
                try:
                    res = supabase.table("historial_reportes").select("*").eq("proyecto", proyecto).execute()
                    if res.data:
                        df = pd.DataFrame(res.data)
                        df['Fecha'] = pd.to_datetime(df['created_at'])
                        
                        meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
                                "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
                        mes_num = meses.index(mes) + 1
                        
                        df_mes = df[(df['Fecha'].dt.month == mes_num) & (df['Fecha'].dt.year == anio)]
                        
                        if not df_mes.empty:
                            p = supabase.table("usuarios").select("*").eq("Proyecto", proyecto).execute().data[0]
                            reporte = generar_reporte_total(p)
                            
                            img_path, _ = generar_graficos(df_mes)
                            
                            logo_consultora = st.secrets.get("logo_consultora_path", "logo_consultora.jpg")
                            
                            pdf = generar_pdf_profesional(df_mes, proyecto, proyectos_dict[proyecto], 
                                                         img_path, reporte, logo_consultora)
                            
                            pdf_file = f"Auditoria_{proyecto}_{mes}_{anio}.pdf"
                            pdf.output(pdf_file)
                            
                            with open(pdf_file, "rb") as f:
                                st.download_button("📥 Descargar PDF", f.read(), pdf_file)
                            
                            if img_path and os.path.exists(img_path):
                                os.remove(img_path)
                        else:
                            st.warning(f"Sin datos para {mes}/{anio}")
                except Exception as e:
                    st.error(f"Error: {e}")


# PESTAÑA 3: EXCEL
with tab_excel:
    st.subheader("📊 Base de Datos")
    
    if st.session_state.get('admin_mode'):
        try:
            res = supabase.table("historial_reportes").select("*").execute()
            if res.data:
                st.dataframe(pd.DataFrame(res.data), use_container_width=True)
        except Exception as e:
            st.error(f"Error: {e}")
    else:
        proyecto_cliente = st.session_state.get('proyecto_cliente')
        try:
            res = supabase.table("historial_reportes").select("*").eq("proyecto", proyecto_cliente).execute()
            if res.data:
                st.dataframe(pd.DataFrame(res.data), use_container_width=True)
        except Exception as e:
            st.error(f"Error: {e}")


# PESTAÑA 4: ADMIN (SOLO ADMIN)
with tab_admin:
    if not st.session_state.get('admin_mode'):
        st.error("❌ Esta sección solo es accesible para administradores")
    else:
        st.title("⚙️ Panel de Admin")
        
        tab_admin_clientes, tab_admin_config = st.tabs(["Clientes", "Configuración"])
        
        with tab_admin_clientes:
            st.subheader("Gestión de Clientes")
            
            with st.form("form_nuevo_cliente", clear_on_submit=True):
                c1, c2 = st.columns(2)
                with c1:
                    titular = st.text_input("Titular")
                    nombre = st.text_input("Proyecto")
                    tipo = st.selectbox("Tipo", ["MINERIA", "GLACIAR", "BOSQUE", "HUMEDAL", "AGRICOLA"])
                    anio_lb = st.number_input("Año Base", value=2017)
                with c2:
                    telegram = st.text_input("Telegram ID")
                    coords = st.text_input("Coordenadas (JSON)")
                    hora = st.time_input("Hora", value=time(8, 0))
                    pwd_cliente = st.text_input("Contraseña Cliente", type="password")

                if st.form_submit_button("💾 Guardar Cliente"):
                    try:
                        nuevo_cliente = {
                            "titular": titular,
                            "Proyecto": nombre,
                            "Tipo": tipo,
                            "anio_linea_base": anio_lb,
                            "telegram_id": telegram,
                            "Coordenadas": coords,
                            "hora_envio": hora.strftime("%H:%M"),
                            "password_cliente": hash_password(pwd_cliente) if pwd_cliente else ""
                        }
                        supabase.table("usuarios").upsert(nuevo_cliente).execute()
                        st.success(f"✅ {nombre} guardado")
                        st.balloons()
                    except Exception as e:
                        st.error(f"Error: {e}")
        
        with tab_admin_config:
            st.subheader("Configuración")
            st.info("Sección de configuración general del sistema")


# PESTAÑA 5: GUÍA DEL PROTOCOLO (SOLO ADMIN)
with tab_guia:
    if not st.session_state.get('admin_mode'):
        st.error("❌ Esta sección solo es accesible para administradores")
    else:
        st.title("📖 Guía del Protocolo de Validación de Línea Base Espectral")
        
        with st.expander("📚 1. Introducción", expanded=True):
            st.markdown("""
El **Protocolo de Validación de Línea Base Espectral** es un sistema avanzado que distingue entre:
- **Cambios reales** (degradación, contaminación, etc.)
- **Ruido de sensor** (variaciones naturales en zonas áridas/minerales)
            """)
        
        with st.expander("🎯 2. Clasificación Automática del Terreno"):
            df_terrenos = pd.DataFrame({
                'Clasificación': ['MINERAL_ARIDO', 'VEGETADO', 'CRIOSFERA', 'HIDRICO'],
                'Criterio': ['SAVI < 0.10', 'SAVI >= 0.30', 'NDSI >= 0.35', 'NDWI >= 0.20'],
                'Características': [
                    'Sin vegetación, ruido permitido',
                    'Bosques, cultivos, frágiles',
                    'Glaciares, nieve permanente',
                    'Lagos, humedales, ríos'
                ]
            })
            st.dataframe(df_terrenos, use_container_width=True)
        
        with st.expander("🔍 3. Reglas de Validación"):
            st.markdown("")
        
        st.markdown("---")
        st.info("📞 Para ajustar parámetros específicos, contacta al equipo de BioCore")
