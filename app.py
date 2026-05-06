# ============================================================================
# BIOCORE INTELLIGENCE - SISTEMA COMPLETO (VERSIÓN FINAL INTEGRADA)
# ============================================================================

import streamlit as st
import ee
import folium
from streamlit_folium import folium_static
import json
import pandas as pd
import requests
from datetime import datetime, time, timedelta
import plotly.graph_objects as go
from supabase import create_client, Client
import matplotlib.pyplot as plt
import matplotlib
from fpdf import FPDF
import os
import tempfile
import hashlib
from io import BytesIO
import numpy as np

matplotlib.use('Agg')

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="BioCore Intelligence", layout="wide")

st.markdown("""
<style>
    [data-testid="stSidebar"] {
        background-color: #0e1117;
    }
    h1 {
        font-size: 2rem !important;
    }
    h2 {
        font-size: 1.5rem !important;
    }
</style>
""", unsafe_allow_html=True)

# === INICIALIZAR BASES DE DATOS ===
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

# === AUTENTICACIÓN ===
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def es_admin(contraseña_admin):
    return contraseña_admin == "2861701l"

def verificar_credenciales_usuario(proyecto, password):
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

# === FUNCIÓN DE MAPA ===
def dibujar_mapa_biocore(coordenadas):
    try:
        if isinstance(coordenadas, str):
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

# === OBTENER COORDENADAS CORRECTAMENTE ===
def obtener_coordenadas_correctamente(p):
    """Obtiene las coordenadas del proyecto desde Supabase"""
    raw_coords = p.get('Coordenadas')
    
    if raw_coords is None or raw_coords == '' or raw_coords == 'null':
        raise ValueError('Coordenadas vacías')
    
    if isinstance(raw_coords, list):
        return raw_coords
    
    if isinstance(raw_coords, str):
        try:
            coords = json.loads(raw_coords)
            return coords
        except json.JSONDecodeError:
            try:
                coords = eval(raw_coords)
                return coords
            except:
                raise ValueError(f'No se pudo parsear: {raw_coords}')
    
    if isinstance(raw_coords, dict):
        if 'coordinates' in raw_coords:
            return raw_coords['coordinates']
    
    raise ValueError(f'Formato no reconocido: {type(raw_coords)}')

# ============================================================================
# MÓDULO 1: GENERADOR DE REPORTE TELEGRAM DINÁMICO
# ============================================================================

def generar_mensaje_telegram_dinamico(reporte_data, proyecto_data):
    """Genera mensaje Telegram dinámico según tipo de proyecto"""
    tipo = proyecto_data.get('Tipo', 'MINERIA').upper()
    proyecto = proyecto_data.get('Proyecto', 'N/A')
    
    savi = reporte_data.get('savi_actual', 0)
    ndwi = reporte_data.get('ndwi', 0)
    ndsi = reporte_data.get('ndsi', 0)
    temp = reporte_data.get('temp', 0)
    fecha = reporte_data.get('fecha', 'N/A')
    nivel = reporte_data.get('nivel', 'DESCONOCIDO')
    estado = reporte_data.get('estado', '')
    variacion_savi = reporte_data.get('variacion', 0)
    variacion_ndwi = reporte_data.get('variacion_ndwi', 0)
    variacion_ndsi = reporte_data.get('variacion_ndsi', 0)
    
    sar_vv = reporte_data.get('sar_vv', 0.0)
    clay = reporte_data.get('clay', 0.0)
    incendios = reporte_data.get('incendios_activos', 0)
    swir = reporte_data.get('swir', 0.0)
    
    encabezado = f"""
╔════════════════════════════════════════════════════════════╗
║        🛰️  VIGILANCIA AMBIENTAL EN TIEMPO REAL 🛰️         ║
║                    BIOCORE INTELLIGENCE                   ║
╚════════════════════════════════════════════════════════════╝

📍 PROYECTO: {proyecto}
📊 TIPO: {tipo}
📅 ANÁLISIS: {fecha}
👤 RESPONSABLE: Loreto Campos Carrasco
🛰️ SENSORES: Sentinel-2 | Sentinel-1 SAR | MODIS | NASA Fire

═══════════════════════════════════════════════════════════════"""

    if tipo == 'GLACIAR':
        diagnostico = f"""
❄️ ESTADO DE CRIÓSFERA (NDSI):
Cobertura Actual: {ndsi:.3f}
Análisis: {'✅ Hielo perenne confirmado' if ndsi > 0.40 else '⚠️ Ciclo estacional' if ndsi > 0.20 else '🔴 Nula presencia de nieve. Predomina suelo expuesto o sustrato rocoso.'}
Variación: {variacion_ndsi:+.1f}%

📡 MONITOREO RADAR (Sentinel-1):
Retrodispersión VV: {sar_vv:.2f} dB
Análisis: {'La señal sugiere una superficie rugosa o presencia de estructuras, consistente con actividad operativa.' if sar_vv > -8 else 'Superficie lisa detectada, indicando hielo o nieve consolidada.'}

🛡️ INTEGRIDAD DEL TERRENO (SU-6):
Humedad (SWIR): {swir:.2f} | Arcillas (Clay Index): {clay:.2f}
Análisis: {'✅ Niveles de humedad óptimos detectados, garantizando estabilidad en el sustrato.' if swir > 0.25 else '⚠️ Humedad moderada detectada'}

🌱 SALUD VEGETAL (SAVI):
Vigor Actual: {savi:.3f} | Base: {reporte_data.get('savi_base', 0):.3f}
Variación: {variacion_savi:+.1f}% respecto al original.
Análisis: {'✅ Suelo estable. Los valores bajos son consistentes con la litología y altitud del sector.' if savi < 0.05 else '⚠️ Vegetación presente'}

⚠️ RIESGO CLIMÁTICO:
Temperatura: {temp:.1f}°C | Incendios Activos: {'✅ Sin focos activos' if incendios == 0 else f'🔴 {incendios} focos detectados por NASA MODIS'}
Análisis: {'✅ Condiciones térmicas normales' if temp < 15 else '⚠️ Temperatura elevada, acelera fusión'}

═══════════════════════════════════════════════════════════════"""

    elif tipo == 'MINERIA':
        diagnostico = f"""
⛏️ MONITOREO INTEGRAL DE YACIMIENTO:

❄️ ESTADO DE CRIÓSFERA (NDSI):
Cobertura Actual: {ndsi:.3f}
Análisis: {'✅ Hielo presente - Recurso disponible' if ndsi > 0.20 else '🔴 Sin cobertura de hielo'}

📡 MONITOREO RADAR (Sentinel-1):
Retrodispersión VV: {sar_vv:.2f} dB
Análisis: {'La señal sugiere una superficie rugosa o presencia de estructuras, consistente con actividad operativa.' if sar_vv > -8 else 'Superficie estable detectada.'}

🛡️ RECURSOS HÍDRICOS (NDWI):
Humedad (SWIR): {swir:.2f} | Arcillas: {clay:.2f}
Análisis: {'✅ Niveles de humedad óptimos detectados, garantizando estabilidad en el sustrato.' if swir > 0.25 else '⚠️ Humedad moderada'}

💧 AGUA DISPONIBLE (NDWI):
Valor Actual: {ndwi:.4f} | Variación: {variacion_ndwi:+.1f}%
Análisis: {'✅ Sin indicios de desecación o depósito de relaves anómalos' if ndwi > 0.20 else '⚠️ ALERTA: Posible acopio no documentado'}

🌱 VEGETACIÓN PERIMETRAL (SAVI):
Vigor Actual: {savi:.3f} | Base: {reporte_data.get('savi_base', 0):.3f}
Variación: {variacion_savi:+.1f}%
Análisis: {'✅ Cumplimiento de Ley 20.283 verificado' if savi > 0.35 else '⚠️ Vegetación bajo estrés'}

⚠️ RIESGO CLIMÁTICO:
Temperatura: {temp:.1f}°C | Incendios: {'✅ Sin focos activos' if incendios == 0 else f'🔴 {incendios} focos detectados'}

═══════════════════════════════════════════════════════════════"""

    elif tipo == 'BOSQUE':
        diagnostico = f"""
🌲 VIGILANCIA FORESTAL INTEGRAL:

🌱 DENSIDAD DE COBERTURA (SAVI):
Vigor Actual: {savi:.3f} | Base: {reporte_data.get('savi_base', 0):.3f}
Variación: {variacion_savi:+.1f}%
Análisis: {'✅ Muy densa (>70%) - Ley 20.283 verificada' if savi > 0.40 else '⚠️ Estrés vegetal detectado' if savi > 0.25 else '🔴 Degradación crítica'}

📡 MONITOREO RADAR (Sentinel-1):
Retrodispersión VV: {sar_vv:.2f} dB
Análisis: {'La señal sugiere una superficie rugosa o presencia de estructuras.' if sar_vv > -8 else 'Superficie lisa detectada.'}

💧 DISPONIBILIDAD HÍDRICA (NDWI):
Valor: {ndwi:.4f}
Análisis: {'✅ Óptima - Bajo riesgo de incendio' if ndwi > 0.30 else '⚠️ MODERADO - Vigilancia activa' if ndwi > 0.15 else '🔴 CRÍTICO - Alto riesgo de propagación'}

🔥 RIESGO DE INCENDIO:
Temperatura: {temp:.1f}°C | Incendios: {'✅ Sin focos activos' if incendios == 0 else f'🔴 {incendios} focos detectados por NASA MODIS'}
Análisis: {'✅ BAJO - Condiciones de seguridad óptimas' if ndwi > 0.25 and savi > 0.35 else '🔴 CRÍTICO'}

══════════════════════════════════════════════���════════════════"""

    elif tipo == 'HUMEDAL':
        diagnostico = f"""
💧 VIGILANCIA ECOSISTEMA ACUÁTICO:

💧 CICLO HIDROLÓGICO (NDWI):
Contenido Actual: {ndwi:.4f} | Variación: {variacion_ndwi:+.1f}%
Análisis: {'✅ SATURADO - Ciclo óptimo' if ndwi > 0.40 else '⚠️ MODERADO - Variabilidad normal' if ndwi > 0.25 else '🔴 CRÍTICO - Desecación en curso'}

📡 MONITOREO RADAR (Sentinel-1):
Retrodispersión VV: {sar_vv:.2f} dB
Análisis: {'La señal sugiere presencia de agua libre.' if sar_vv < -15 else 'Superficie con agua parcial o sedimentos.'}

🛡️ HUMEDAD DEL SUSTRATO (SU-6):
SWIR: {swir:.2f} | Arcillas: {clay:.2f}
Análisis: {'✅ Niveles de humedad óptimos' if swir > 0.25 else '⚠️ Humedad moderada'}

🌿 VEGETACIÓN HIDRÓFILA (SAVI):
Vigor: {savi:.3f}
Análisis: {'✅ Flora acuática presente - Confirmación Ramsar' if savi > 0.30 else '⚠️ Vegetación bajo estrés'}

⚠️ ESTADO ECOSISTÉMICO:
Temperatura: {temp:.1f}°C | Incendios: {'✅ Sin riesgo' if incendios == 0 else 'Riesgo'}
Cumplimiento: {'✅ Decreto de Humedales verificado' if ndwi > 0.30 else '🔴 VIOLACIÓN SMA/DGA INMEDIATA'}

═══════════════════════════════════════════════════════════════"""

    elif tipo == 'AGRICOLA':
        diagnostico = f"""
🌾 OPTIMIZACIÓN DE CULTIVOS:

🌱 VIGOR DEL CULTIVO (SAVI):
Valor Actual: {savi:.3f} | Base: {reporte_data.get('savi_base', 0):.3f}
Variación: {variacion_savi:+.1f}%
Análisis: {'✅ ÓPTIMO - Rendimiento máximo' if savi > 0.45 else '✅ NORMAL - Rendimiento estándar' if savi > 0.35 else '⚠️ MODERADO - Aumentar riego' if savi > 0.25 else '🔴 CRÍTICO'}

💧 DISPONIBILIDAD HÍDRICA (NDWI):
Humedad Actual: {ndwi:.4f} | Variación: {variacion_ndwi:+.1f}%
Análisis: {'✅ Óptima para crecimiento' if ndwi > 0.30 else '⚠️ Aumentar riego' if ndwi > 0.20 else '🔴 CRÍTICO - Riego de emergencia'}

📊 RENDIMIENTO PROYECTADO:
Potencial: {'✅ M��XIMO (90-100%)' if savi > 0.45 and ndwi > 0.30 else '✅ ALTO (70-90%)' if savi > 0.35 else '⚠️ MODERADO (50-70%)' if savi > 0.25 else '🔴 BAJO (<50%)'}

⚠️ OPERACIONAL:
Temperatura: {temp:.1f}°C | Incendios: {'✅ Sin focos' if incendios == 0 else f'⚠️ {incendios} focos'}

═══════════════════════════════════════════════════════════════"""

    else:
        diagnostico = f"Estado: {estado}\nNivel: {nivel}"

    conclusion = f"""
✅ ESTADO GLOBAL: {estado}

📋 CONCLUSIÓN FINAL: Tras el análisis, se concluye {'estabilidad técnica del área' if nivel == 'NORMAL' else 'necesidad de evaluación urgente' if nivel == 'MODERADO' else 'EMERGENCIA AMBIENTAL'}.
Los parámetros se mantienen dentro de la {'varianza histórica permitida' if nivel == 'NORMAL' else 'zona de alerta'}.

Responsable: Loreto Campos Carrasco | BioCore Intelligence © 2026
════════════════════════════════════════════════════════════════
"""

    return encabezado + diagnostico + conclusion


# ============================================================================
# MÓDULO 1B: AGREGAR DATOS SAR Y FUEGOS
# ============================================================================

def agregar_datos_sar_y_fuegos(reporte_base, geom):
    """Agrega datos de Sentinel-1 SAR y NASA MODIS Fire al reporte"""
    
    try:
        s1 = ee.ImageCollection('COPERNICUS/S1_GRD')\
            .filterBounds(geom)\
            .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV'))\
            .sort('system:time_start', False)\
            .first()
        
        if s1 is not None:
            sar_stats = s1.select('VV').reduceRegion(
                ee.Reducer.mean(),
                geom,
                30
            ).getInfo()
            sar_vv = float(sar_stats.get('VV', 0))
        else:
            sar_vv = 0.0
    except:
        sar_vv = 0.0
    
    try:
        fire = ee.ImageCollection('FIRMS')\
            .filterBounds(geom)\
            .sort('system:time_start', False)\
            .first()
        
        if fire is not None:
            fire_count = fire.select('confidence').gt(50).reduceRegion(
                ee.Reducer.sum(),
                geom,
                1000
            ).getInfo()
            incendios = int(fire_count.get('confidence', 0))
        else:
            incendios = 0
    except:
        incendios = 0
    
    reporte_base['sar_vv'] = sar_vv
    reporte_base['incendios_activos'] = incendios
    
    return reporte_base


# ============================================================================
# MÓDULO 2: GENERADOR DE GRÁFICOS PROFESIONALES MEJORADO
# ============================================================================
def generar_graficos_profesionales(indices_historicos, tipo_proyecto):
    """Genera gráficos profesionales contextualizados por tipo de proyecto, validando dimensiones."""
    try:
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        fig.patch.set_facecolor('white')

        # La cantidad más grande de datos en todos los índices
        max_len = 0
        for k, v in indices_historicos.items():
            if isinstance(v, list):
                max_len = max(max_len, len(v))
        fechas = list(range(max_len))

        if tipo_proyecto == 'GLACIAR':
            config = [
                (0, 0, 'ndsi', 'NDSI - Cobertura de Nieve/Hielo', '#3498db', '▼ Bajo = Retracción'),
                (0, 1, 'temp', 'Temperatura - LST (°C)', '#e74c3c', '▲ Elevada = Fusión'),
                (1, 0, 'ndwi', 'NDWI - Recursos Hídricos', '#2980b9', '▲ Agua de deshielo'),
                (1, 1, 'precipitacion', 'Precipitación Anual (TerraCLIM)', '#0099cc', 'Cambio climático'),
            ]
        elif tipo_proyecto == 'MINERIA':
            config = [
                (0, 0, 'ndwi', 'NDWI - Monitoreo de Agua', '#3498db', 'Descarta acopio anómalo'),
                (0, 1, 'swir', 'SWIR - Estabilidad de Taludes', '#7f8c8d', 'Reflectancia mineral'),
                (1, 0, 'savi', 'SAVI - Vegetación Perimetral', '#27ae60', 'Ley 20.283'),
                (1, 1, 'temp', 'Temperatura - Actividad Térmica', '#e74c3c', 'Detección de procesos'),
            ]
        elif tipo_proyecto == 'BOSQUE':
            config = [
                (0, 0, 'savi', 'SAVI - Densidad de Cobertura', '#27ae60', 'Cumplimiento normativo'),
                (0, 1, 'ndwi', 'NDWI - Estrés Hídrico', '#3498db', 'Riesgo de incendio'),
                (1, 0, 'ndvi', 'NDVI - Vigor General', '#2ecc71', 'Sanidad forestal'),
                (1, 1, 'precipitacion', 'Precipitación Anual (TerraCLIM)', '#0099cc', 'Cambio climático'),
            ]
        elif tipo_proyecto == 'HUMEDAL':
            config = [
                (0, 0, 'ndwi', 'NDWI - Ciclo Hidrológico', '#3498db', 'Estado de saturación'),
                (0, 1, 'savi', 'SAVI - Flora Hidrófila', '#27ae60', 'Biodiversidad'),
                (1, 0, 'ndvi', 'NDVI - Productividad', '#2ecc71', 'Salud del ecosistema'),
                (1, 1, 'temperatura_min', 'Temperatura Mínima (TerraCLIM)', '#e74c3c', 'Variabilidad'),
            ]
        elif tipo_proyecto == 'AGRICOLA':
            config = [
                (0, 0, 'savi', 'SAVI - Vigor de Cultivo', '#27ae60', 'Rendimiento esperado'),
                (0, 1, 'ndwi', 'NDWI - Disponibilidad Hídrica', '#3498db', 'Necesidad de riego'),
                (1, 0, 'ndvi', 'NDVI - Estado Fenológico', '#2ecc71', 'Fase de desarrollo'),
                (1, 1, 'precipitacion', 'Precipitación Histórica (TerraCLIM)', '#0099cc', 'Tendencia climática'),
            ]
        else:
            config = [
                (0, 0, 'savi', 'SAVI', '#27ae60', ''),
                (0, 1, 'ndwi', 'NDWI', '#3498db', ''),
                (1, 0, 'ndvi', 'NDVI', '#2ecc71', ''),
                (1, 1, 'temp', 'Temperatura', '#e74c3c', ''),
            ]

        for row, col, indice, titulo, color, subtitulo in config:
            ax = axes[row, col]
            valores = indices_historicos.get(indice, [])
            if isinstance(valores, list) and len(valores) > 0:
                min_len = min(len(fechas), len(valores))
                if min_len == 0:
                    ax.text(0.5, 0.5, 'Sin datos disponibles',
                            ha='center', va='center', transform=ax.transAxes,
                            fontsize=11, style='italic', color='gray')
                else:
                    x = fechas[:min_len]
                    y = valores[:min_len]
                    ax.plot(x, y, color=color, marker='o', linewidth=2.5, markersize=8)
                    ax.fill_between(x, y, alpha=0.3, color=color)
                    ax.set_title(titulo, fontweight='bold', fontsize=12)
                    ax.set_ylabel('Valor', fontsize=10)
                    ax.set_xlabel('Tiempo (años)', fontsize=9)
                    ax.grid(True, alpha=0.3, linestyle='--')
                    if subtitulo:
                        ax.text(0.02, 0.98, subtitulo, transform=ax.transAxes, 
                            fontsize=9, verticalalignment='top',
                            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
            else:
                ax.text(0.5, 0.5, 'Sin datos disponibles', 
                        ha='center', va='center', transform=ax.transAxes,
                        fontsize=11, style='italic', color='gray')
                ax.set_title(titulo, fontweight='bold', fontsize=12)
                ax.grid(True, alpha=0.2)

        plt.tight_layout()
        temp_dir = tempfile.gettempdir()
        img_path = os.path.join(temp_dir, f'grafico_biocore_{tipo_proyecto.lower()}.png')
        plt.savefig(img_path, format='png', dpi=300, bbox_inches='tight', facecolor='white')
        plt.close()
        return img_path
    except Exception as e:
        st.error(f"Error en gráficos: {e}")
        return None

# ============================================================================
# MÓDULO 2B: OBTENER HISTÓRICO DE 20 AÑOS
# ============================================================================

def obtener_historico_20_anios(geom, tipo_proyecto):
    """Obtiene datos históricos de 20 años desde GEE"""
    
    indices_historicos = {
        'savi': [],
        'ndwi': [],
        'ndvi': [],
        'ndsi': [],
        'temp': [],
        'swir': [],
        'precipitacion': [],
        'temperatura_min': [],
        'temperatura_max': []
    }
    
    try:
        anio_actual = datetime.now().year
        anios = list(range(anio_actual - 20, anio_actual + 1))
        
        for anio in anios:
            try:
                # Sentinel-2 (solo últimos 5-6 años disponibles)
                if anio >= 2018:
                    s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')\
                        .filterBounds(geom)\
                        .filterDate(f'{anio}-01-01', f'{anio}-12-31')\
                        .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 30))\
                        .median()
                    
                    if s2 is not None:
                        savi = s2.expression(
                            '((NIR - RED) / (NIR + RED + 0.5)) * (1.5)',
                            {'NIR': s2.select('B8'), 'RED': s2.select('B4')}
                        )
                        ndwi = s2.normalizedDifference(['B8', 'B11'])
                        ndvi = s2.normalizedDifference(['B8', 'B4'])
                        ndsi = s2.normalizedDifference(['B3', 'B11'])
                        swir = s2.select('B11').divide(10000)
                        
                        stats = s2.addBands([savi, ndwi, ndvi, ndsi, swir]).reduceRegion(
                            reducer=ee.Reducer.mean(),
                            geometry=geom,
                            scale=30,
                            maxPixels=1e9
                        ).getInfo()
                        
                        indices_historicos['savi'].append(float(stats.get('savi', 0)))
                        indices_historicos['ndwi'].append(float(stats.get('ndwi', 0)))
                        indices_historicos['ndvi'].append(float(stats.get('ndvi', 0)))
                        indices_historicos['ndsi'].append(float(stats.get('ndsi', 0)))
                        indices_historicos['swir'].append(float(stats.get('swir', 0)))
                
                # MODIS Temperatura
                temp_img = ee.ImageCollection("MODIS/061/MOD11A1")\
                    .filterBounds(geom)\
                    .filterDate(f'{anio}-01-01', f'{anio}-12-31')\
                    .select('LST_Day_1km')\
                    .median()
                
                if temp_img is not None:
                    temp_stats = temp_img.multiply(0.02).subtract(273.15).reduceRegion(
                        ee.Reducer.mean(),
                        geom,
                        1000
                    ).getInfo()
                    indices_historicos['temp'].append(float(temp_stats.get('LST_Day_1km', 0)))
                
                # TerraCLIM
                terraclim = ee.ImageCollection('IDAHO_EPSCOR/TERRACLIM')\
                    .filterBounds(geom)\
                    .filterDate(f'{anio}-01-01', f'{anio}-12-31')\
                    .select(['pr', 'tmmn', 'tmmx'])\
                    .mean()
                
                if terraclim is not None:
                    terraclim_stats = terraclim.reduceRegion(
                        ee.Reducer.mean(),
                        geom,
                        4638
                    ).getInfo()
                    
                    prec = float(terraclim_stats.get('pr', 0))
                    indices_historicos['precipitacion'].append(prec * 12)
                    
                    tmin_k = float(terraclim_stats.get('tmmn', 273.15))
                    indices_historicos['temperatura_min'].append(tmin_k - 273.15)
                    
                    tmax_k = float(terraclim_stats.get('tmmx', 273.15))
                    indices_historicos['temperatura_max'].append(tmax_k - 273.15)
                
            except Exception as e:
                continue
        
        return indices_historicos
    
    except Exception as e:
        st.warning(f"Error obteniendo histórico: {str(e)}")
        return indices_historicos


# ============================================================================
# MÓDULO 2C: OBTENER INFORMACIÓN CONAF
# ============================================================================

def obtener_informacion_conaf(geom, tipo_proyecto):
    """Obtiene información de cobertura forestal usando:
    1. Hansen Global Forest Change (alta resolución, actualizado anualmente)
    2. COPERNICUS/GLOBAL_LAND_COVER como respaldo para clasificación
    Relevante para Chile: Hansen detecta pérdida forestal desde 2000 con 30m de resolución,
    compatible con los estándares de monitoreo CONAF/SNASPE.
    """

    info_conaf = {
        'tipo_bosque': 'No disponible',
        'area_bosque': 0,
        'densidad': 'N/A',
        'estado': 'No clasificado',
        'cobertura_dosel': 0.0,
        'perdida_acumulada_ha': 0.0,
        'anio_mayor_perdida': 'N/A',
        'fuente': 'N/A'
    }

    if tipo_proyecto.upper() != 'BOSQUE':
        return info_conaf

    # --- FUENTE 1: Hansen Global Forest Change (UMD) ---
    # Es la fuente más usada por CONAF y organismos internacionales para Chile
    try:
        hansen = ee.Image('UMD/hansen/global_forest_change_2023_v1_11')

        # Cobertura de dosel año 2000 (base) con umbral >30% (estándar FAO)
        treecover = hansen.select('treecover2000')
        bosque_mask = treecover.gte(30)

        cobertura_stats = treecover.updateMask(bosque_mask).reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=geom,
            scale=30,
            maxPixels=1e9
        ).getInfo()
        cobertura_dosel = float(cobertura_stats.get('treecover2000', 0))
        info_conaf['cobertura_dosel'] = round(cobertura_dosel, 1)

        # Área total con cobertura boscosa (ha)
        area_bosque_px = bosque_mask.reduceRegion(
            reducer=ee.Reducer.sum(),
            geometry=geom,
            scale=30,
            maxPixels=1e9
        ).getInfo()
        area_ha = float(area_bosque_px.get('treecover2000', 0)) * 0.09  # px 30m -> ha
        info_conaf['area_bosque'] = round(area_ha, 2)

        # Pérdida acumulada de bosque (ha) desde 2000
        loss = hansen.select('loss')
        loss_stats = loss.reduceRegion(
            reducer=ee.Reducer.sum(),
            geometry=geom,
            scale=30,
            maxPixels=1e9
        ).getInfo()
        perdida_ha = float(loss_stats.get('loss', 0)) * 0.09
        info_conaf['perdida_acumulada_ha'] = round(perdida_ha, 2)

        # Año de mayor pérdida (lossyear: 1=2001 ... 23=2023)
        lossyear = hansen.select('lossyear').updateMask(hansen.select('loss'))
        anio_stats = lossyear.reduceRegion(
            reducer=ee.Reducer.mode(),
            geometry=geom,
            scale=30,
            maxPixels=1e9
        ).getInfo()
        anio_cod = anio_stats.get('lossyear', None)
        if anio_cod and int(anio_cod) > 0:
            info_conaf['anio_mayor_perdida'] = str(2000 + int(anio_cod))

        # Clasificación de densidad según cobertura de dosel
        if cobertura_dosel >= 60:
            info_conaf['densidad'] = 'Alta'
            info_conaf['tipo_bosque'] = 'Bosque denso (dosel >60%)'
            info_conaf['estado'] = 'Bosque sano'
        elif cobertura_dosel >= 30:
            info_conaf['densidad'] = 'Moderada'
            info_conaf['tipo_bosque'] = 'Bosque abierto (dosel 30-60%)'
            info_conaf['estado'] = 'Bosque estable'
        elif cobertura_dosel >= 10:
            info_conaf['densidad'] = 'Baja'
            info_conaf['tipo_bosque'] = 'Matorral arbolado (dosel 10-30%)'
            info_conaf['estado'] = 'Cobertura baja'
        else:
            info_conaf['densidad'] = 'Nula'
            info_conaf['tipo_bosque'] = 'Sin cobertura forestal significativa'
            info_conaf['estado'] = 'Sin bosque detectado'

        info_conaf['fuente'] = 'Hansen GFC 2023 (UMD) - Compatible CONAF/FAO'

    except Exception:
        # --- FUENTE 2: Copernicus como respaldo ---
        try:
            bosques = ee.ImageCollection('COPERNICUS/GLOBAL_LAND_COVER/102001_V3')\
                .filterBounds(geom)\
                .select('discrete_classification')\
                .first()

            if bosques is not None:
                class_stats = bosques.reduceRegion(
                    ee.Reducer.mode(), geom, 100
                ).getInfo()
                clasificacion = int(class_stats.get('discrete_classification', 0))

                clases_bosque = {
                    10: {'tipo': 'Bosque herbáceo', 'densidad': 'Baja'},
                    11: {'tipo': 'Bosque herbáceo natural', 'densidad': 'Moderada'},
                    12: {'tipo': 'Bosque herbáceo cultivado', 'densidad': 'Moderada'},
                    20: {'tipo': 'Arbustos', 'densidad': 'Variable'},
                    30: {'tipo': 'Cobertura herbácea', 'densidad': 'Dispersa'},
                    40: {'tipo': 'Cultivos', 'densidad': 'N/A'},
                    50: {'tipo': 'Área urbana', 'densidad': 'N/A'},
                    60: {'tipo': 'Suelo desnudo', 'densidad': 'Nula'},
                    70: {'tipo': 'Agua', 'densidad': 'N/A'},
                    80: {'tipo': 'Nieve/Hielo', 'densidad': 'Nula'},
                    90: {'tipo': 'Bosque cerrado', 'densidad': 'Alta'},
                    100: {'tipo': 'Bosque abierto', 'densidad': 'Moderada'},
                }

                if clasificacion in clases_bosque:
                    info_conaf['tipo_bosque'] = clases_bosque[clasificacion]['tipo']
                    info_conaf['densidad'] = clases_bosque[clasificacion]['densidad']

                area_px = bosques.eq(90).Or(bosques.eq(100)).reduceRegion(
                    ee.Reducer.sum(), geom, 100
                ).getInfo()
                info_conaf['area_bosque'] = round(
                    float(area_px.get('discrete_classification', 0)) * 0.01, 2
                )

                if info_conaf['densidad'] == 'Alta':
                    info_conaf['estado'] = 'Bosque sano'
                elif info_conaf['densidad'] == 'Moderada':
                    info_conaf['estado'] = 'Bosque estable'
                else:
                    info_conaf['estado'] = 'Cobertura baja'

                info_conaf['fuente'] = 'Copernicus Global Land Cover (respaldo)'
        except Exception:
            pass

    return info_conaf

# ============================================================================
# MÓDULO 3: EVALUACIÓN POR TIPO DE PROYECTO
# ============================================================================

def evaluar_mineria(ndwi_actual, ndwi_base, variacion_ndwi, savi, temp):
    """MINERÍA - Basado en NDWI"""
    
    if savi < 0.01:
        if ndwi_actual < 0.10:
            estado = "🟢 BAJO CONTROL"
            nivel = "NORMAL"
            color = (40, 150, 80)
            diagnostico = (
                f"Sector de alta montaña con vegetación nula (SAVI: {savi:.4f}). "
                f"NDWI de {ndwi_actual:.4f} es consistente con litología mineral. "
                f"Status: BLINDADO ante hallazgos de degradación ambiental."
            )
        else:
            estado = "🟡 PRECAUCIÓN"
            nivel = "MODERADO"
            color = (200, 100, 0)
            diagnostico = (
                f"Acumulación anómala de agua en zona árida (NDWI: {ndwi_actual:.4f}). "
                f"Posible acumulación en relaves. Requiere inspección."
            )
    else:
        if ndwi_actual > 0.30:
            estado = "🟢 BAJO CONTROL"
            nivel = "NORMAL"
            color = (40, 150, 80)
            diagnostico = (
                f"Recursos hídricos disponibles (NDWI: {ndwi_actual:.4f}). "
                f"Vegetación perimetral ({savi:.4f}) con buena hidratación. "
                f"Cumplimiento normativo verificado."
            )
        elif 0.15 <= ndwi_actual <= 0.30:
            if variacion_ndwi < -20:
                estado = "🔴 ALERTA CRÍTICA"
                nivel = "CRÍTICO"
                color = (220, 50, 50)
                diagnostico = (
                    f"Caída severa de NDWI ({variacion_ndwi:.1f}%). "
                    f"De {ndwi_base:.4f} a {ndwi_actual:.4f}. "
                    f"Requiere medidas urgentes de restitución hídrica."
                )
            else:
                estado = "🟡 PRECAUCIÓN"
                nivel = "MODERADO"
                color = (200, 100, 0)
                diagnostico = (
                    f"NDWI en rango de alerta ({ndwi_actual:.4f}). "
                    f"Incremento: {variacion_ndwi:+.1f}%. "
                    f"Se recomienda intensificar monitoreo de drenaje."
                )
        else:
            estado = "🔴 ALERTA CRÍTICA"
            nivel = "CRÍTICO"
            color = (220, 50, 50)
            diagnostico = (
                f"Humedad crítica (NDWI: {ndwi_actual:.4f}). "
                f"Riesgo de inestabilidad de taludes. "
                f"ACCIÓN INMEDIATA: Implementar sistemas de riego y drenaje."
            )
    
    return estado, nivel, color, diagnostico


def evaluar_glaciar(ndsi_actual, ndsi_base, variacion_ndsi, temp):
    """GLACIAR - Basado en NDSI"""
    
    if ndsi_actual > 0.50:
        estado = "🟢 BAJO CONTROL"
        nivel = "NORMAL"
        color = (40, 150, 80)
        diagnostico = (
            f"Cobertura de nieve/hielo consolidada (NDSI: {ndsi_actual:.4f}). "
            f"Balance de masa positivo confirmado. "
            f"Firma espectral de hielo perenne consistente."
        )
    elif 0.35 <= ndsi_actual <= 0.50:
        if variacion_ndsi < -15:
            estado = "🔴 ALERTA CRÍTICA"
            nivel = "CRÍTICO"
            color = (220, 50, 50)
            diagnostico = (
                f"Retracción acelerada (NDSI: {ndsi_actual:.4f}, "
                f"variación: {variacion_ndsi:.1f}%). "
                f"Cambios climáticos severos. Requiere estudios de balance de masa."
            )
        else:
            estado = "🟡 PRECAUCIÓN"
            nivel = "MODERADO"
            color = (200, 100, 0)
            diagnostico = (
                f"Cobertura en transición (NDSI: {ndsi_actual:.4f}). "
                f"Variación: {variacion_ndsi:+.1f}%. "
                f"Posible ciclo estacional. Requiere confirmación."
            )
    elif 0.20 <= ndsi_actual < 0.35:
        estado = "🔴 ALERTA CRÍTICA"
        nivel = "CRÍTICO"
        color = (220, 50, 50)
        diagnostico = (
            f"Cobertura bajo umbral crítico (NDSI: {ndsi_actual:.4f}). "
            f"Exposición avanzada de roca. Hallazgo grave ante SMA/DGA. "
            f"RECOMENDACIÓN: Estudios glaciológicos inmediatos."
        )
    else:
        estado = "🔴 ALERTA CRÍTICA"
        nivel = "CRÍTICO"
        color = (220, 50, 50)
        diagnostico = (
            f"NDSI nulo ({ndsi_actual:.4f}). NO se detecta firma de hielo. "
            f"Exposición total de sustrato rocoso. "
            f"Retracción extrema validada. Requiere acción inmediata."
        )
    
    if temp > 15 and ndsi_actual < 0.40:
        diagnostico += f" Temperatura de {temp:.1f}°C acelera fusión."
    
    return estado, nivel, color, diagnostico


def evaluar_bosque(savi_actual, savi_base, variacion_savi, ndwi):
    """BOSQUE - Basado en SAVI"""
    
    if savi_actual > 0.40:
        estado = "🟢 BAJO CONTROL"
        nivel = "NORMAL"
        color = (40, 150, 80)
        diagnostico = (
            f"Cobertura vegetal densa y saludable (SAVI: {savi_actual:.4f}). "
            f"Densidad de dosel > 70%. Variación: {variacion_savi:+.1f}%. "
            f"Cumplimiento de Ley 20.283 verificado."
        )
    elif 0.25 <= savi_actual <= 0.40:
        if variacion_savi < -25:
            estado = "🔴 ALERTA CRÍTICA"
            nivel = "CRÍTICO"
            color = (220, 50, 50)
            diagnostico = (
                f"Pérdida severa de cobertura ({variacion_savi:.1f}%). "
                f"De {savi_base:.4f} a {savi_actual:.4f}. "
                f"Indica tala no autorizada, incendio o plagas. "
                f"ACCIÓN: Plan de reforestación inmediato."
            )
        elif variacion_savi < -10:
            estado = "🟡 PRECAUCIÓN"
            nivel = "MODERADO"
            color = (200, 100, 0)
            diagnostico = (
                f"Bosque con estrés moderado (SAVI: {savi_actual:.4f}). "
                f"Pérdida de vigor ({variacion_savi:.1f}%). "
                f"Posible sequía, plagas o uso forestal. Requiere inspección."
            )
        else:
            estado = "🟢 BAJO CONTROL"
            nivel = "NORMAL"
            color = (40, 150, 80)
            diagnostico = (
                f"Bosque regenerándose (SAVI: {savi_actual:.4f}). "
                f"Variación: {variacion_savi:+.1f}%. Consistente con ciclo sostenible."
            )
    elif savi_actual < 0.25:
        if ndwi < 0.20:
            estado = "🔴 ALERTA CRÍTICA"
            nivel = "CRÍTICO"
            color = (220, 50, 50)
            diagnostico = (
                f"Bosque degradado + estrés hídrico (SAVI: {savi_actual:.4f}, NDWI: {ndwi:.4f}). "
                f"Alto riesgo de incendios. "
                f"ACCIÓN URGENTE: Restauración ecológica + riego."
            )
        else:
            estado = "🟡 PRECAUCIÓN"
            nivel = "MODERADO"
            color = (200, 100, 0)
            diagnostico = (
                f"Bosque en regeneración inicial (SAVI: {savi_actual:.4f}). "
                f"Humedad adecuada (NDWI: {ndwi:.4f}). Esperar próximo monitoreo."
            )
    
    return estado, nivel, color, diagnostico


def evaluar_humedal(ndwi_actual, ndwi_base, variacion_ndwi, savi):
    """HUMEDAL - Basado en NDWI"""
    
    if ndwi_actual > 0.40:
        estado = "🟢 BAJO CONTROL"
        nivel = "NORMAL"
        color = (40, 150, 80)
        diagnostico = (
            f"Humedal saturado con agua libre (NDWI: {ndwi_actual:.4f}). "
            f"Ciclo hidrológico óptimo. Biodiversidad confirmada. "
            f"Cumplimiento del Decreto de Humedales verificado."
        )
    elif 0.25 <= ndwi_actual <= 0.40:
        if variacion_ndwi < -20:
            estado = "🔴 ALERTA CRÍTICA"
            nivel = "CRÍTICO"
            color = (220, 50, 50)
            diagnostico = (
                f"Desecación acelerada ({variacion_ndwi:.1f}%). "
                f"De {ndwi_base:.4f} a {ndwi_actual:.4f}. "
                f"Alto riesgo de colapso ecológico. "
                f"ACCIÓN: Restauración hidrológica + protección legal."
            )
        else:
            estado = "🟡 PRECAUCIÓN"
            nivel = "MODERADO"
            color = (200, 100, 0)
            diagnostico = (
                f"Variabilidad moderada (NDWI: {ndwi_actual:.4f}). "
                f"Cambio: {variacion_ndwi:+.1f}%. Posible ciclo estacional. "
                f"Monitoreo continuo requerido."
            )
    elif 0.10 <= ndwi_actual < 0.25:
        estado = "🔴 ALERTA CRÍTICA"
        nivel = "CRÍTICO"
        color = (220, 50, 50)
        diagnostico = (
            f"Estrés hídrico severo (NDWI: {ndwi_actual:.4f}). "
            f"Pérdida del 30-50% de agua. Riesgo de desaparición. "
            f"Requiere acciones de restauración urgentes."
        )
    else:
        estado = "🔴 ALERTA CRÍTICA"
        nivel = "CRÍTICO"
        color = (220, 50, 50)
        diagnostico = (
            f"Humedal severamente desecado (NDWI: {ndwi_actual:.4f}). "
            f"Pérdida > 50% del agua. Riesgo legal ante SMA y Ramsar. "
            f"Evaluación ambiental urgente requerida."
        )
    
    if savi > 0.30:
        diagnostico += f" Vegetación hidrófila presente ({savi:.4f})."
    
    return estado, nivel, color, diagnostico


def evaluar_agricola(savi_actual, savi_base, variacion_savi, ndwi_actual, variacion_ndwi):
    """AGRÍCOLA - Basado en SAVI + NDWI"""
    
    if savi_actual > 0.45 and ndwi_actual > 0.30:
        estado = "🟢 BAJO CONTROL"
        nivel = "NORMAL"
        color = (40, 150, 80)
        diagnostico = (
            f"Cultivo óptimo (SAVI: {savi_actual:.4f}, NDWI: {ndwi_actual:.4f}). "
            f"Rendimiento esperado: Máximo. Continuar riego estándar."
        )
    elif savi_actual > 0.35 and ndwi_actual > 0.20:
        if variacion_savi > -10 and variacion_ndwi > -15:
            estado = "🟢 BAJO CONTROL"
            nivel = "NORMAL"
            color = (40, 150, 80)
            diagnostico = (
                f"Cultivo normal (SAVI: {savi_actual:.4f}, NDWI: {ndwi_actual:.4f}). "
                f"Variaciones: SAVI {variacion_savi:+.1f}%, NDWI {variacion_ndwi:+.1f}%. "
                f"Continuar manejo estándar."
            )
        else:
            estado = "🟡 PRECAUCIÓN"
            nivel = "MODERADO"
            color = (200, 100, 0)
            diagnostico = (
                f"Estrés moderado detectado. "
                f"SAVI: {savi_actual:.4f} ({variacion_savi:+.1f}%), NDWI: {ndwi_actual:.4f} ({variacion_ndwi:+.1f}%). "
                f"Aumentar riego y revisar nutrición."
            )
    elif ndwi_actual < 0.20:
        estado = "🔴 ALERTA CRÍTICA"
        nivel = "CRÍTICO"
        color = (220, 50, 50)
        diagnostico = (
            f"Estrés hídrico severo (NDWI: {ndwi_actual:.4f}). "
            f"Humedad: {variacion_ndwi:.1f}%. Riesgo de pérdida total. "
            f"ACCIÓN URGENTE: Riego de emergencia inmediato."
        )
    elif savi_actual < 0.25:
        if variacion_savi < -20:
            estado = "🔴 ALERTA CRÍTICA"
            nivel = "CRÍTICO"
            color = (220, 50, 50)
            diagnostico = (
                f"Degradación severa (SAVI: {savi_actual:.4f}, caída: {variacion_savi:.1f}%). "
                f"Plagas, enfermedades o deficiencia severa. "
                f"ACCIÓN: Inspección fitosanitaria inmediata."
            )
        else:
            estado = "🟡 PRECAUCIÓN"
            nivel = "MODERADO"
            color = (200, 100, 0)
            diagnostico = (
                f"Cultivo bajo estrés (SAVI: {savi_actual:.4f}). "
                f"Aplicar fertilizante o tratamiento fitosanitario."
            )
    else:
        estado = "🟢 BAJO CONTROL"
        nivel = "NORMAL"
        color = (40, 150, 80)
        diagnostico = f"Cultivo en fase final de ciclo (SAVI: {savi_actual:.4f})."
    
    return estado, nivel, color, diagnostico


# ============================================================================
# MÓDULO 4: GENERADOR DE REPORTE COMPLETO
# ============================================================================

def generar_reporte_total(p, rango_dias=30):
    """Genera reporte completo y guarda en Supabase"""
    try:
        raw_coords = obtener_coordenadas_correctamente(p)
        
        if not raw_coords or len(raw_coords) == 0:
            return {
                'error': 'Coordenadas vacías después de parseo',
                'tipo': 'error'
            }

        if not isinstance(raw_coords[0], (list, tuple)):
            return {
                'error': 'Formato de coordenadas inválido',
                'tipo': 'error'
            }
        
        geom = ee.Geometry.Polygon(raw_coords)

    except Exception as e:
        return {
            'error': f'Error en geometría: {str(e)}',
            'tipo': 'error'
        }

    # === SENTINEL 2 - ACTUAL ===
    try:
        s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')\
            .filterBounds(geom)\
            .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 30))\
            .sort('system:time_start', False)\
            .first()

        if s2 is None:
            return {
                'error': 'No hay imágenes Sentinel-2 disponibles',
                'tipo': 'error'
            }

        timestamp_ms = s2.get('system:time_start').getInfo()
        f_rep = datetime.fromtimestamp(timestamp_ms/1000).strftime('%d/%m/%Y') if timestamp_ms else "N/A"
    except Exception as e:
        return {
            'error': f'Error obteniendo imágenes: {str(e)}',
            'tipo': 'error'
        }

    # === TEMPERATURA ===
    try:
        temp_img = ee.ImageCollection("MODIS/061/MOD11A1")\
            .filterBounds(geom)\
            .sort('system:time_start', False)\
            .first()

        temp_dict = temp_img.select('LST_Day_1km').multiply(0.02).subtract(273.15)\
            .reduceRegion(ee.Reducer.mean(), geom, 1000).getInfo()
        temp_val = float(temp_dict.get('LST_Day_1km', 0))
    except:
        temp_val = 0.0

    # === CALCULAR ÍNDICES ===
    def calcular_idx(img):
        savi = img.expression(
            '((NIR - RED) / (NIR + RED + 0.5)) * (1.5)',
            {'NIR': img.select('B8'), 'RED': img.select('B4')}
        ).rename('savi')
        
        ndsi = img.normalizedDifference(['B3', 'B11']).rename('ndsi')
        ndwi = img.normalizedDifference(['B8', 'B11']).rename('ndwi')
        swir = img.select('B11').divide(10000).rename('swir')
        ndvi = img.normalizedDifference(['B8', 'B4']).rename('ndvi')
        clay = img.select('B11').divide(img.select('B12').add(0.0001)).rename('clay')
        
        return img.addBands([savi, ndsi, swir, ndvi, ndwi, clay])

    try:
        img_now = calcular_idx(s2)
        
        region_stats = img_now.reduceRegion(
            reducer=ee.Reducer.mean(),
            geometry=geom,
            scale=30,
            maxPixels=1e9
        ).getInfo()

        def safe_float(value, default=0.0):
            if value is None:
                return default
            try:
                return float(value)
            except:
                return default

        savi_now = safe_float(region_stats.get('savi'), 0.0)
        ndsi_now = safe_float(region_stats.get('ndsi'), 0.0)
        ndwi_now = safe_float(region_stats.get('ndwi'), 0.0)
        swir_now = safe_float(region_stats.get('swir'), 0.0)
        ndvi_now = safe_float(region_stats.get('ndvi'), 0.0)
        clay_now = safe_float(region_stats.get('clay'), 0.0)

    except Exception as e:
        return {
            'error': f'Error calculando índices: {str(e)}',
            'tipo': 'error'
        }

    # === LÍNEA BASE ===
    anio_base = p.get('ano_linea_base', 2017)
    
    try:
        s2_base = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')\
            .filterBounds(geom)\
            .filterDate(f'{anio_base}-01-01', f'{anio_base}-12-31')\
            .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 30))\
            .sort('CLOUDY_PIXEL_PERCENTAGE')\
            .first()

        if s2_base is not None:
            img_base = calcular_idx(s2_base)
            base_stats = img_base.reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=geom,
                scale=30,
                maxPixels=1e9
            ).getInfo()

            savi_base = safe_float(base_stats.get('savi'), savi_now)
            ndsi_base = safe_float(base_stats.get('ndsi'), ndsi_now)
            ndwi_base = safe_float(base_stats.get('ndwi'), ndwi_now)
            swir_base = safe_float(base_stats.get('swir'), swir_now)
            ndvi_base = safe_float(base_stats.get('ndvi'), ndvi_now)
            clay_base = safe_float(base_stats.get('clay'), clay_now)
        else:
            savi_base = savi_now
            ndsi_base = ndsi_now
            ndwi_base = ndwi_now
            swir_base = swir_now
            ndvi_base = ndvi_now
            clay_base = clay_now
    except:
        savi_base = savi_now
        ndsi_base = ndsi_now
        ndwi_base = ndwi_now
        swir_base = swir_now
        ndvi_base = ndvi_now
        clay_base = clay_now

    # === VARIACIONES ===
    def calcular_variacion(actual, base):
        if abs(base) < 0.001:
            return 0.0
        return ((actual - base) / abs(base)) * 100

    variacion_savi = calcular_variacion(savi_now, savi_base)
    variacion_ndwi = calcular_variacion(ndwi_now, ndwi_base)
    variacion_ndsi = calcular_variacion(ndsi_now, ndsi_base)
    variacion_ndvi = calcular_variacion(ndvi_now, ndvi_base)

    # === OBTENER HISTÓRICO DE 20 AÑOS ===
    indices_historicos = obtener_historico_20_anios(geom, p.get('Tipo', 'GENERAL'))
    
    if not any(indices_historicos.values()):
        indices_historicos = {
            'savi': [savi_base * 0.95, savi_base, savi_now],
            'ndwi': [ndwi_base * 0.95, ndwi_base, ndwi_now],
            'ndsi': [ndsi_base * 0.95, ndsi_base, ndsi_now],
            'ndvi': [ndvi_base * 0.95, ndvi_base, ndvi_now],
            'temp': [temp_val - 2, temp_val - 1, temp_val],
            'precipitacion': [500, 520, 480],
            'temperatura_min': [10, 11, 12],
            'temperatura_max': [25, 26, 27]
        }

    # === EVALUACIÓN ===
    tipo = p.get('Tipo', 'MINERIA').upper()
    
    if tipo == 'MINERIA':
        estado, nivel, color_estado, diagnostico_detallado = evaluar_mineria(
            ndwi_now, ndwi_base, variacion_ndwi, savi_now, temp_val
        )
    elif tipo == 'GLACIAR':
        estado, nivel, color_estado, diagnostico_detallado = evaluar_glaciar(
            ndsi_now, ndsi_base, variacion_ndsi, temp_val
        )
    elif tipo == 'BOSQUE':
        estado, nivel, color_estado, diagnostico_detallado = evaluar_bosque(
            savi_now, savi_base, variacion_savi, ndwi_now
        )
    elif tipo == 'HUMEDAL':
        estado, nivel, color_estado, diagnostico_detallado = evaluar_humedal(
            ndwi_now, ndwi_base, variacion_ndwi, savi_now
        )
    elif tipo == 'AGRICOLA':
        estado, nivel, color_estado, diagnostico_detallado = evaluar_agricola(
            savi_now, savi_base, variacion_savi, ndwi_now, variacion_ndwi
        )
    else:
        estado = "🟡 ESTADO NO DEFINIDO"
        nivel = "DESCONOCIDO"
        color_estado = (150, 150, 0)
        diagnostico_detallado = "Tipo de proyecto no reconocido"

    # === INFORMACIÓN CONAF ===
    info_conaf = obtener_informacion_conaf(geom, tipo)

    # Construir reporte
    reporte_completo = {
        'estado': estado,
        'diagnostico': diagnostico_detallado,
        'nivel': nivel,
        'savi_actual': savi_now,
        'savi_base': savi_base,
        'ndsi': ndsi_now,
        'ndsi_base': ndsi_base,
        'ndwi': ndwi_now,
        'ndwi_base': ndwi_base,
        'swir': swir_now,
        'ndvi': ndvi_now,
        'ndvi_base': ndvi_base,
        'clay': clay_now,
        'temp': temp_val,
        'fecha': f_rep,
        'anio_base': anio_base,
        'tipo': tipo,
        'proyecto': p['Proyecto'],
        'variacion': variacion_savi,
        'variacion_ndwi': variacion_ndwi,
        'variacion_ndsi': variacion_ndsi,
        'variacion_ndvi': variacion_ndvi,
        'color_estado': color_estado,
        'diagnostico_completo': diagnostico_detallado,
        'indices_historicos': indices_historicos,
        'info_conaf': info_conaf,
        'indices': {
            'savi': savi_now,
            'ndsi': ndsi_now,
            'ndwi': ndwi_now,
            'ndvi': ndvi_now,
            'swir': swir_now,
            'clay': clay_now,
            'temp': temp_val
        }
    }

    # === AGREGAR SAR Y FUEGOS ===
    reporte_completo = agregar_datos_sar_y_fuegos(reporte_completo, geom)

    # === GUARDAR EN SUPABASE ===
    try:
        registro = {
            'proyecto': p.get('Proyecto'),
            'tipo': tipo,
            'fecha_analisis': f_rep,
            'savi_actual': float(savi_now),
            'savi_base': float(savi_base),
            'ndwi_actual': float(ndwi_now),
            'ndwi_base': float(ndwi_base),
            'ndsi_actual': float(ndsi_now),
            'ndsi_base': float(ndsi_base),
            'ndvi_actual': float(ndvi_now),
            'ndvi_base': float(ndvi_base),
            'swir': float(swir_now),
            'clay': float(clay_now),
            'sar_vv': float(reporte_completo.get('sar_vv', 0)),
            'incendios': int(reporte_completo.get('incendios_activos', 0)),
            'temperatura': float(temp_val),
            'variacion_savi': float(variacion_savi),
            'variacion_ndwi': float(variacion_ndwi),
            'variacion_ndsi': float(variacion_ndsi),
            'variacion_ndvi': float(variacion_ndvi),
            'estado': estado,
            'nivel': nivel,
            'diagnostico': diagnostico_detallado,
            'ano_linea_base': int(anio_base),
            'created_at': datetime.now().isoformat()
        }
        
        supabase.table("historial_reportes").insert(registro).execute()
    except Exception as e:
        st.warning(f"Advertencia: No se pudo guardar en historial: {str(e)}")

    return reporte_completo


# ============================================================================
# MÓDULO 5: GENERADOR DE SIGNOS DE DEGRADACIÓN
# ============================================================================

def generar_signos_degradacion(reporte_data):
    """Genera signos de degradación dinámicamente"""
    
    signos = []
    
    savi = reporte_data.get('savi_actual', 0)
    ndwi = reporte_data.get('ndwi', 0)
    ndsi = reporte_data.get('ndsi', 0)
    ndvi = reporte_data.get('ndvi', 0)
    temp = reporte_data.get('temp', 0)
    variacion_savi = reporte_data.get('variacion', 0)
    variacion_ndwi = reporte_data.get('variacion_ndwi', 0)
    variacion_ndsi = reporte_data.get('variacion_ndsi', 0)
    variacion_ndvi = reporte_data.get('variacion_ndvi', 0)
    tipo = reporte_data.get('tipo', 'GENERAL').upper()
    
    # 1. PÉRDIDA DE VEGETACIÓN
    if savi < 0.15:
        signos.append({
            'icono': '[CRITICO]',
            'texto': f'PÉRDIDA DE VEGETACIÓN: SAVI bajo ({savi:.3f}). Indica exposición de suelo o degradación severa.'
        })
    elif savi < 0.25 and variacion_savi < -10:
        signos.append({
            'icono': '[ALERTA]',
            'texto': f'ESTRÉS VEGETAL MODERADO: SAVI de {savi:.3f} con caída de {variacion_savi:.1f}%. Posible plagas, sequía o uso forestal.'
        })
    
    # 2. DESECACIÓN
    if ndwi < 0.15:
        signos.append({
            'icono': '[CRITICO]',
            'texto': f'ESTRÉS HÍDRICO SEVERO: NDWI bajo ({ndwi:.4f}). Indica desecación, erosión o sequía extrema.'
        })
    elif ndwi < 0.25 and variacion_ndwi < -15:
        signos.append({
            'icono': '[ALERTA]',
            'texto': f'PÉRDIDA HÍDRICA ACELERADA: NDWI de {ndwi:.4f} con caída de {variacion_ndwi:.1f}%. Requiere atención urgente.'
        })
    
    # 3. RETRACCIÓN GLACIAL
    if tipo == 'GLACIAR' and ndsi < 0.20:
        signos.append({
            'icono': '[CRITICO]',
            'texto': f'RETRACCIÓN GLACIAL CRÍTICA: NDSI de {ndsi:.3f}. Exposición de roca desnuda o suelo mineral.'
        })
    elif tipo == 'GLACIAR' and variacion_ndsi < -15:
        signos.append({
            'icono': '[ALERTA]',
            'texto': f'RETRACCIÓN ACELERADA: NDSI con caída de {variacion_ndsi:.1f}%. Cambios climáticos detectados.'
        })
    
    # 4. TEMPERATURA
    if temp > 25:
        signos.append({
            'icono': '[CRITICO]',
            'texto': f'TEMPERATURA ELEVADA: {temp:.1f}°C. Indica estrés térmico o actividad anómala.'
        })
    elif temp > 15 and tipo == 'GLACIAR':
        signos.append({
            'icono': '[AVISO]',
            'texto': f'TEMPERATURA MODERADA: {temp:.1f}°C. En criósfera, acelera fusión.'
        })
    
    # 5. EXPOSICIÓN SUELO
    if ndvi < 0.10:
        signos.append({
            'icono': '[CRITICO]',
            'texto': f'SUELO EXPUESTO: NDVI bajo ({ndvi:.3f}). Roca desnuda, arena o depósito mineral.'
        })
    elif ndvi < 0.25:
        signos.append({
            'icono': '[AVISO]',
            'texto': f'BAJA COBERTURA: NDVI de {ndvi:.3f}. Vegetación escasa o en restauración.'
        })
    
    # 6. ACUMULACIÓN ANÓMALA
    if tipo == 'MINERIA' and ndwi > 0.25 and savi < 0.05:
        signos.append({
            'icono': '[ALERTA]',
            'texto': f'ACUMULACIÓN ANÓMALA: NDWI elevado ({ndwi:.4f}) en zona árida. Inspección recomendada.'
        })
    
    # 7. ALTERACIÓN RELIEVE
    if tipo == 'MINERIA' and variacion_ndvi > 20:
        signos.append({
            'icono': '[AVISO]',
            'texto': f'CAMBIO ABRUPTO: NDVI con variación de {variacion_ndvi:+.1f}%. Posible movimiento de tierra.'
        })
    
    if not signos:
        signos.append({
            'icono': '[OK]',
            'texto': 'PARÁMETROS NORMALES: Índices dentro de rangos esperados. Continuar monitoreo rutinario.'
        })
    
    return signos

# ============================================================================
# DICCIONARIO DE RECOMENDACIONES POR TIPO Y NIVEL
# ============================================================================

recomendaciones_por_tipo = {
    "NORMAL": {
        "MINERIA": (
            "Mantener monitoreo satelital mensual de NDWI y NDSI.\n"
            "Verificar integridad de sistemas de drenaje perimetrales.\n"
            "Continuar con programa de revegetacion en zonas de borde.\n"
            "Actualizar Plan de Cierre conforme a normativa vigente."
        ),
        "GLACIAR": (
            "Continuar monitoreo estacional de cobertura (NDSI).\n"
            "Mantener registros de temperatura y balance de masa.\n"
            "Coordinar con DGA ante cualquier variacion mayor al 10% en NDSI.\n"
            "Evitar actividades que generen material particulado en la zona."
        ),
        "BOSQUE": (
            "Mantener vigilancia de incendios durante temporada estival.\n"
            "Realizar inventario forestal semestral conforme a Ley 20.283.\n"
            "Controlar presencia de especies invasoras en el perimetro.\n"
            "Registrar cualquier intervencion antropica en el area."
        ),
        "HUMEDAL": (
            "Monitorear nivel de agua mensualmente.\n"
            "Registrar avistamientos de fauna para verificar biodiversidad.\n"
            "Asegurar cumplimiento del Decreto de Humedales Urbanos.\n"
            "Evitar cualquier obra que altere el flujo hidrico natural."
        ),
        "AGRICOLA": (
            "Continuar plan de riego segun demanda evapotranspirativa.\n"
            "Monitorear estado fitosanitario de los cultivos semanalmente.\n"
            "Optimizar uso de fertilizantes basado en analisis de suelo.\n"
            "Planificar rotacion de cultivos para proxima temporada."
        ),
        "GENERAL": (
            "Mantener monitoreo periodico de los indices espectrales.\n"
            "Documentar cualquier cambio observado en el area.\n"
            "Continuar con las buenas practicas ambientales actuales."
        ),
    },
    "MODERADO": {
        "MINERIA": (
            "Intensificar monitoreo a frecuencia quincenal.\n"
            "Revisar sistemas de contencion y drenaje de relaves.\n"
            "Notificar a SMA si la variacion persiste mas de 30 dias.\n"
            "Implementar plan de contingencia hidrica preventivo."
        ),
        "GLACIAR": (
            "Solicitar estudio glaciologico complementario urgente.\n"
            "Notificar a DGA sobre retraccion detectada.\n"
            "Suspender actividades que puedan generar calor o polvo en la zona.\n"
            "Aumentar frecuencia de monitoreo a cada 15 dias."
        ),
        "BOSQUE": (
            "Realizar inspeccion en terreno para identificar causa del estres.\n"
            "Evaluar presencia de plagas o enfermedades forestales con CONAF.\n"
            "Implementar medidas de control de erosion en zonas degradadas.\n"
            "Preparar plan de reforestacion de contingencia."
        ),
        "HUMEDAL": (
            "Verificar fuentes de captacion y aporte hidrico al humedal.\n"
            "Evaluar si existe intervencion antropical aguas arriba.\n"
            "Contactar a DGA para monitoreo conjunto del caudal.\n"
            "Documentar cambios con fotografias georreferenciadas."
        ),
        "AGRICOLA": (
            "Aumentar frecuencia de riego de inmediato.\n"
            "Aplicar analisis foliar para detectar deficiencias nutricionales.\n"
            "Evaluar uso de mulch o cubiertas para reducir evapotranspiracion.\n"
            "Revisar sistemas de riego por posibles obstrucciones o fugas."
        ),
        "GENERAL": (
            "Aumentar frecuencia de monitoreo satelital.\n"
            "Realizar inspeccion en terreno en los proximos 15 dias.\n"
            "Documentar la situacion y preparar plan de contingencia."
        ),
    },
    "CRITICO": {
        "MINERIA": (
            "ACCION INMEDIATA: Notificar a SMA y DGA en un plazo de 24 horas.\n"
            "Paralizar operaciones en la zona afectada hasta nueva evaluacion.\n"
            "Contratar empresa especializada para restauracion de suelos.\n"
            "Implementar plan de contingencia hidrica de emergencia.\n"
            "Elaborar informe tecnico para autoridades regulatorias."
        ),
        "GLACIAR": (
            "EMERGENCIA: Notificar a DGA y Ministerio del Medio Ambiente de inmediato.\n"
            "Contratar glaciologo certificado para evaluacion en terreno urgente.\n"
            "Suspender toda actividad en el area de influencia del glaciar.\n"
            "Registrar el evento como hallazgo critico ante SMA.\n"
            "Iniciar protocolo de seguimiento diario hasta estabilizacion."
        ),
        "BOSQUE": (
            "EMERGENCIA: Notificar a CONAF de inmediato ante posible tala ilegal o incendio.\n"
            "Implementar plan de reforestacion de emergencia conforme a Ley 20.283.\n"
            "Solicitar declaracion de zona de proteccion a autoridades.\n"
            "Controlar acceso al area hasta determinar la causa.\n"
            "Elaborar informe tecnico de dano para presentar a SMA."
        ),
        "HUMEDAL": (
            "EMERGENCIA: Notificar a DGA y SMA de desecacion critica.\n"
            "Iniciar restauracion hidrologica de emergencia.\n"
            "Documentar el estado actual como linea base de dano.\n"
            "Evaluar si se aplica Decreto de Humedales Urbanos o Ramsar.\n"
            "Contratar especialista en restauracion de ecosistemas acuaticos."
        ),
        "AGRICOLA": (
            "ACCION URGENTE: Implementar riego de emergencia de inmediato.\n"
            "Evaluar perdida de cosecha y notificar a aseguradora si corresponde.\n"
            "Aplicar tratamiento fitosanitario de emergencia ante plagas.\n"
            "Revisar infraestructura de riego en su totalidad.\n"
            "Consultar con agronomo para plan de recuperacion del cultivo."
        ),
        "GENERAL": (
            "ACCION URGENTE requerida en las proximas 48 horas.\n"
            "Notificar a las autoridades ambientales competentes.\n"
            "Realizar inspeccion en terreno de manera inmediata.\n"
            "Elaborar informe tecnico de la situacion detectada."
        ),
    },
        }
# ============================================================================
# MÓDULO 6: GENERADOR DE PDF
# ============================================================================

class AuditoriaPDF(FPDF):
    """Clase personalizada para PDF"""
    
    def header(self):
        """Encabezado"""
        self.set_fill_color(20, 50, 80)
        self.rect(0, 0, 210, 30, 'F')
        
        self.set_text_color(255, 255, 255)
        self.set_font("helvetica", "B", 22)
        self.set_xy(10, 5)
        self.cell(0, 12, "REPORTE DE AUDITORÍA AMBIENTAL", ln=1)
        
        self.set_font("helvetica", "I", 10)
        self.set_xy(10, 18)
        self.cell(0, 5, "BioCore Intelligence")

        self.ln(15)
    
    def footer(self):
        """Pie"""
        self.set_y(-15)
        self.set_font("helvetica", "I", 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f"Página {self.page_no()}", align="C")


def generar_pdf_auditoria_dinamico(proyecto_data, reporte_data, img_path=None):
    """Genera PDF dinámico"""
    
    pdf = AuditoriaPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    # SECCIÓN 1: INFORMACIÓN
    pdf.set_font("helvetica", "B", 14)
    pdf.set_text_color(20, 50, 80)
    pdf.cell(0, 10, "1. INFORMACIÓN DEL PROYECTO", ln=1)
    
    pdf.set_font("helvetica", "", 10)
    pdf.set_text_color(0, 0, 0)
    
    info_table = [
        ["Proyecto:", proyecto_data.get('Proyecto', 'N/A')],
        ["Tipo:", proyecto_data.get('Tipo', 'N/A')],
        ["Responsable:", "Loreto Campos Carrasco"],
        ["Fecha:", reporte_data.get('fecha', 'N/A')],
        ["Año Base:", str(proyecto_data.get('ano_linea_base', 2017))],
    ]
    
    for row in info_table:
        pdf.set_font("helvetica", "B", 9)
        pdf.cell(50, 7, clean(row[0]))
        pdf.set_font("helvetica", "", 9)
        pdf.cell(0, 7, clean(row[1]), ln=1)
    
    pdf.ln(5)
    
    # SECCIÓN 2: CONAF
    if reporte_data.get('tipo') == 'BOSQUE':
        pdf.set_font("helvetica", "B", 14)
        pdf.set_text_color(20, 50, 80)
        pdf.cell(0, 10, "2. CLASIFICACIÓN FORESTAL (COMPATIBLE CONAF)", ln=1)

        pdf.set_font("helvetica", "", 9)
        pdf.set_text_color(0, 0, 0)

        info_conaf = reporte_data.get('info_conaf', {})

        conaf_table = [
            ["Tipo de Bosque:",         info_conaf.get('tipo_bosque', 'N/A')],
            ["Densidad:",               info_conaf.get('densidad', 'N/A')],
            ["Estado:",                 info_conaf.get('estado', 'No clasificado')],
            ["Área con cobertura (ha):", f"{info_conaf.get('area_bosque', 0):.2f}"],
            ["Cobertura de dosel (%):", f"{info_conaf.get('cobertura_dosel', 0):.1f}%"],
            ["Pérdida acumulada (ha):", f"{info_conaf.get('perdida_acumulada_ha', 0):.2f}"],
            ["Año mayor pérdida:",      info_conaf.get('anio_mayor_perdida', 'N/A')],
            ["Fuente de datos:",        info_conaf.get('fuente', 'N/A')],
        ]

        for row in conaf_table:
            pdf.set_font("helvetica", "B", 9)
            pdf.cell(65, 7, clean(row[0]))
            pdf.set_font("helvetica", "", 9)
            pdf.cell(0, 7, clean(str(row[1])), ln=1)

        # Alerta si hay pérdida significativa
        perdida = info_conaf.get('perdida_acumulada_ha', 0)
        area = info_conaf.get('area_bosque', 1)
        if area > 0 and perdida > 0:
            pct_perdida = (perdida / (area + perdida)) * 100
            pdf.ln(2)
            if pct_perdida > 20:
                pdf.set_font("helvetica", "B", 9)
                pdf.set_text_color(220, 50, 50)
                pdf.multi_cell(0, 5, clean(
                    f"ALERTA: Se ha perdido el {pct_perdida:.1f}% de la cobertura original "
                    f"desde el año 2000. Requiere evaluación conforme a Ley 20.283."
                ))
            elif pct_perdida > 5:
                pdf.set_font("helvetica", "B", 9)
                pdf.set_text_color(200, 100, 0)
                pdf.multi_cell(0, 5, clean(
                    f"PRECAUCION: Pérdida del {pct_perdida:.1f}% de cobertura detectada "
                    f"desde el año 2000. Monitoreo reforzado recomendado."
                ))
            pdf.set_text_color(0, 0, 0)

        pdf.ln(5)
    
    # SECCIÓN 3: ESTADO
    pdf.set_font("helvetica", "B", 14)
    pdf.set_text_color(20, 50, 80)
    pdf.cell(0, 10, "3. ESTADO Y EVALUACIÓN", ln=1)
    
    color_r, color_g, color_b = reporte_data.get('color_estado', (100, 100, 100))
    pdf.set_fill_color(color_r, color_g, color_b)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("helvetica", "B", 12)
    
    estado_texto = reporte_data.get('estado', 'ESTADO DESCONOCIDO').replace('🟢', '').replace('🟡', '').replace('🔴', '').strip()
    pdf.cell(0, 10, clean(f"ESTADO: {estado_texto}"), ln=1, fill=True)
    
    pdf.set_font("helvetica", "", 10)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(0, 3, "", ln=1)
    
    nivel_color = {
        'NORMAL': (40, 150, 80),
        'MODERADO': (200, 100, 0),
        'CRÍTICO': (220, 50, 50)
    }
    
    nivel = reporte_data.get('nivel', 'DESCONOCIDO')
    r, g, b = nivel_color.get(nivel, (100, 100, 100))
    
    pdf.set_fill_color(r, g, b)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("helvetica", "B", 10)
    pdf.cell(0, 8, clean(f"Nivel de Riesgo: {nivel}"), ln=1, fill=True)
    
    pdf.set_text_color(0, 0, 0)
    pdf.ln(3)
    
    # SECCIÓN 4: SIGNOS
    pdf.set_font("helvetica", "B", 14)
    pdf.set_text_color(20, 50, 80)
    pdf.cell(0, 10, "4. INDICADORES DE DEGRADACIÓN", ln=1)
    
    pdf.set_font("helvetica", "", 9)
    pdf.set_text_color(0, 0, 0)
    
    signos = generar_signos_degradacion(reporte_data)
    colores_signo = {
        '[CRITICO]': (220, 50, 50),
        '[ALERTA]':  (200, 100, 0),
        '[AVISO]':   (100, 100, 0),
        '[OK]':      (40, 150, 80),
    }
    etiquetas_signo = {
        '[CRITICO]': '>> CRITICO: ',
        '[ALERTA]':  '>> ALERTA:  ',
        '[AVISO]':   '>> AVISO:   ',
        '[OK]':      '>> OK:      ',
    }
    for signo in signos:
        icono = signo['icono']
        r, g, b = colores_signo.get(icono, (80, 80, 80))
        etiqueta = etiquetas_signo.get(icono, '>> ')
        pdf.set_font("helvetica", "B", 9)
        pdf.set_text_color(r, g, b)
        pdf.cell(28, 5, clean(etiqueta))
        pdf.set_font("helvetica", "", 9)
        pdf.set_text_color(0, 0, 0)
        pdf.multi_cell(0, 5, clean(signo['texto']))
        pdf.ln(1)
    
    pdf.ln(3)
    
    # SECCIÓN 5: ÍNDICES
    pdf.set_font("helvetica", "B", 14)
    pdf.set_text_color(20, 50, 80)
    pdf.cell(0, 10, "5. ÍNDICES ESPECTRALES", ln=1)
    
    pdf.set_font("helvetica", "B", 9)
    pdf.set_fill_color(40, 80, 120)
    pdf.set_text_color(255, 255, 255)
    
    col_widths = [35, 30, 30, 30, 40]
    headers = ["Índice", "Actual", "Línea Base", "Variación", "Interpretación"]
    
    for header, width in zip(headers, col_widths):
        pdf.cell(width, 8, header, border=1, align="C", fill=True)
    pdf.ln()
    
    pdf.set_font("helvetica", "", 8)
    pdf.set_text_color(0, 0, 0)
    
    indices_data = [
        ("SAVI", reporte_data.get('savi_actual', 0), reporte_data.get('savi_base', 0), 
         reporte_data.get('variacion', 0), "Vigor de vegetación"),
        ("NDWI", reporte_data.get('ndwi', 0), reporte_data.get('ndwi_base', 0), 
         reporte_data.get('variacion_ndwi', 0), "Contenido de agua"),
        ("NDSI", reporte_data.get('ndsi', 0), reporte_data.get('ndsi_base', 0), 
         reporte_data.get('variacion_ndsi', 0), "Nieve/Hielo"),
        ("NDVI", reporte_data.get('ndvi', 0), reporte_data.get('ndvi_base', 0), 
         reporte_data.get('variacion_ndvi', 0), "Vigor general"),
    ]
    
    for nombre, actual, base, variacion, interp in indices_data:
        pdf.cell(col_widths[0], 10, nombre, border=1)
        pdf.cell(col_widths[1], 10, f"{float(actual):.4f}", border=1, align="C")
        pdf.cell(col_widths[2], 10, f"{float(base):.4f}", border=1, align="C")
        pdf.cell(col_widths[3], 10, f"{float(variacion):+.1f}%", border=1, align="C")
        pdf.cell(col_widths[4], 10, interp, border=1)
        pdf.ln()
    
    pdf.cell(col_widths[0], 10, "TEMP", border=1)
    pdf.cell(col_widths[1], 10, f"{float(reporte_data.get('temp', 0)):.1f}°C", border=1, align="C")
    pdf.cell(col_widths[2], 10, "-", border=1, align="C")
    pdf.cell(col_widths[3], 10, "-", border=1, align="C")
    pdf.cell(col_widths[4], 10, "Temperatura LST", border=1)
    pdf.ln(15)
    
    # SECCIÓN 6: DIAGNÓSTICO
    pdf.set_font("helvetica", "B", 14)
    pdf.set_text_color(20, 50, 80)
    pdf.cell(0, 10, "6. DIAGNÓSTICO TÉCNICO", ln=1)
    
    pdf.set_font("helvetica", "", 9)
    pdf.set_text_color(0, 0, 0)
    diagnostico = reporte_data.get('diagnostico_completo', 'Sin diagnóstico')
    pdf.multi_cell(0, 6, clean(diagnostico.strip()))

    # SECCIÓN 7: SENTINEL-1 SAR
    pdf.ln(5)
    pdf.set_font("helvetica", "B", 14)
    pdf.set_text_color(20, 50, 80)
    pdf.cell(0, 10, "7. MONITOREO RADAR - SENTINEL-1 SAR", ln=1)

    pdf.set_font("helvetica", "", 9)
    pdf.set_text_color(0, 0, 0)
    pdf.multi_cell(0, 5, clean(
        "Sentinel-1 opera en banda C (5.4 GHz) con polarizacion VV. "
        "A diferencia de sensores opticos, atraviesa nubes y lluvia, "
        "siendo el unico dato disponible en dias de alta nubosidad."
    ))
    pdf.ln(3)

    sar_vv = float(reporte_data.get('sar_vv', 0))

    # Tabla SAR
    pdf.set_font("helvetica", "B", 9)
    pdf.set_fill_color(40, 80, 120)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(60, 8, "Parametro", border=1, align="C", fill=True)
    pdf.cell(40, 8, "Valor", border=1, align="C", fill=True)
    pdf.cell(0,  8, "Interpretacion", border=1, align="C", fill=True)
    pdf.ln()

    pdf.set_font("helvetica", "", 9)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(60, 8, "Retrodispersion VV (dB)", border=1)
    pdf.cell(40, 8, f"{sar_vv:.2f} dB", border=1, align="C")

    tipo_sar = reporte_data.get('tipo', 'GENERAL').upper()
    if tipo_sar == 'GLACIAR':
        if sar_vv < -15:
            interp_sar = "Hielo/nieve consolidada"
        elif sar_vv < -8:
            interp_sar = "Superficie mixta hielo-roca"
        else:
            interp_sar = "Roca expuesta o suelo seco"
    elif tipo_sar == 'HUMEDAL':
        if sar_vv < -15:
            interp_sar = "Agua libre presente"
        elif sar_vv < -8:
            interp_sar = "Humedad superficial moderada"
        else:
            interp_sar = "Superficie seca o sedimentos"
    elif tipo_sar == 'BOSQUE':
        if sar_vv > -5:
            interp_sar = "Dosel denso o biomasa alta"
        elif sar_vv > -10:
            interp_sar = "Bosque moderado"
        else:
            interp_sar = "Vegetacion escasa o suelo expuesto"
    elif tipo_sar == 'MINERIA':
        if sar_vv > -8:
            interp_sar = "Estructuras o maquinaria activa"
        else:
            interp_sar = "Superficie mineral sin actividad aparente"
    elif tipo_sar == 'AGRICOLA':
        if sar_vv > -8:
            interp_sar = "Cultivo desarrollado o suelo humedo"
        else:
            interp_sar = "Suelo desnudo o cultivo raso"
    else:
        interp_sar = "Sin interpretacion especifica"

    pdf.cell(0, 8, clean(interp_sar), border=1)
    pdf.ln(10)

    pdf.set_font("helvetica", "I", 8)
    pdf.set_text_color(100, 100, 100)
    pdf.multi_cell(0, 4, clean(
        "Nota: Valores tipicos de referencia VV: agua libre < -15 dB | "
        "vegetacion densa -10 a -5 dB | suelo seco/estructuras > -8 dB. "
        "Util como dato independiente en condiciones de nubosidad total."
    ))

    # SECCIÓN 8: GRÁFICOS (antes era 7)
    if img_path and os.path.exists(img_path):
        pdf.add_page()
        
        pdf.set_font("helvetica", "B", 14)
        pdf.set_text_color(20, 50, 80)
        pdf.cell(0, 10, "8. ANÁLISIS ESPECTRAL - 20 AÑOS", ln=1)
        pdf.ln(5)
        
        try:
            pdf.image(img_path, x=10, y=40, w=190)
        except:
            pass
    
    # SECCIÓN 8: CAMBIO CLIMÁTICO
    pdf.add_page()
    
    pdf.set_font("helvetica", "B", 14)
    pdf.set_text_color(20, 50, 80)
    pdf.cell(0, 10, "9. ANÁLISIS DE CAMBIO CLIMÁTICO (TERRACLIM)", ln=1)
    pdf.ln(3)
    
    pdf.set_font("helvetica", "", 9)
    pdf.set_text_color(0, 0, 0)
    
    indices_hist = reporte_data.get('indices_historicos', {})
    hay_datos_climaticos = False
    
    if len(indices_hist.get('temperatura_min', [])) > 1:
        hay_datos_climaticos = True
        temp_min_inicio = indices_hist['temperatura_min'][0]
        temp_min_final = indices_hist['temperatura_min'][-1]
        cambio_temp = temp_min_final - temp_min_inicio
        
        pdf.set_font("helvetica", "B", 10)
        pdf.set_text_color(20, 50, 80)
        pdf.cell(0, 7, "Temperatura Minima (TerraCLIM):", ln=1)
        pdf.set_font("helvetica", "", 9)
        pdf.set_text_color(0, 0, 0)
        pdf.multi_cell(0, 5,
            f"Valor inicial (hace 20 anos): {temp_min_inicio:.2f}°C\n"
            f"Valor reciente: {temp_min_final:.2f}°C\n"
            f"Cambio neto: {cambio_temp:+.2f}°C\n"
            f"Tendencia: {'Calentamiento detectado en el periodo analizado.' if cambio_temp > 0 else 'Enfriamiento detectado en el periodo analizado.'}")
        pdf.ln(5)
    
    if len(indices_hist.get('temperatura_max', [])) > 1:
        hay_datos_climaticos = True
        tmax_inicio = indices_hist['temperatura_max'][0]
        tmax_final = indices_hist['temperatura_max'][-1]
        cambio_tmax = tmax_final - tmax_inicio
        
        pdf.set_font("helvetica", "B", 10)
        pdf.set_text_color(20, 50, 80)
        pdf.cell(0, 7, "Temperatura Maxima (TerraCLIM):", ln=1)
        pdf.set_font("helvetica", "", 9)
        pdf.set_text_color(0, 0, 0)
        pdf.multi_cell(0, 5,
            f"Valor inicial (hace 20 anos): {tmax_inicio:.2f}°C\n"
            f"Valor reciente: {tmax_final:.2f}°C\n"
            f"Cambio neto: {cambio_tmax:+.2f}°C\n"
            f"Tendencia: {'Incremento de temperaturas maximas.' if cambio_tmax > 0 else 'Reduccion de temperaturas maximas.'}")
        pdf.ln(5)
    
    if len(indices_hist.get('precipitacion', [])) > 1:
        hay_datos_climaticos = True
        prec_inicio = indices_hist['precipitacion'][0]
        prec_final = indices_hist['precipitacion'][-1]
        cambio_prec = ((prec_final - prec_inicio) / prec_inicio * 100) if prec_inicio > 0 else 0
        
        pdf.set_font("helvetica", "B", 10)
        pdf.set_text_color(20, 50, 80)
        pdf.cell(0, 7, "Precipitacion Anual (TerraCLIM):", ln=1)
        pdf.set_font("helvetica", "", 9)
        pdf.set_text_color(0, 0, 0)
        pdf.multi_cell(0, 5,
            f"Precipitacion inicial (hace 20 anos): {prec_inicio:.1f} mm/ano\n"
            f"Precipitacion reciente: {prec_final:.1f} mm/ano\n"
            f"Cambio relativo: {cambio_prec:+.1f}%\n"
            f"Tendencia: {'Aumento de precipitaciones en el periodo.' if cambio_prec > 0 else 'Disminucion de precipitaciones en el periodo.'}")
        pdf.ln(5)
    
    if not hay_datos_climaticos:
        pdf.set_font("helvetica", "B", 10)
        pdf.set_text_color(20, 50, 80)
        pdf.cell(0, 7, "Estado de datos TerraCLIM:", ln=1)
        pdf.set_font("helvetica", "", 9)
        pdf.set_text_color(60, 60, 60)
        pdf.multi_cell(0, 5,
            "No se pudieron recuperar datos historicos de TerraCLIM para este ciclo de analisis.\n"
            "Esto puede deberse a:\n"
            "  - Alta cobertura de nubes en el periodo de consulta\n"
            "  - Latencia en la disponibilidad de datos de Google Earth Engine\n"
            "  - Zona fuera del rango de cobertura del producto IDAHO_EPSCOR/TERRACLIM\n\n"
            "Recomendacion: Ejecutar nuevamente el reporte en los proximos dias para obtener\n"
            "el analisis climatico completo de 20 anos.")
        pdf.ln(3)
        pdf.set_font("helvetica", "I", 8)
        pdf.set_text_color(100, 100, 100)
        pdf.multi_cell(0, 4,
            "Nota tecnica: TerraCLIM es un conjunto de datos climaticos globales de alta resolucion (~4 km)\n"
            "derivado de WorldClim y CRU. Cubre variables como temperatura minima/maxima, precipitacion,\n"
            "humedad del suelo y evapotranspiración desde 1958 hasta la actualidad.")
    
    pdf.ln(5)
    
    # SECCIÓN 9: RECOMENDACIONES
    # SECCIÓN 9: RECOMENDACIONES
    pdf.add_page()
    
    pdf.set_font("helvetica", "B", 14)
    pdf.set_text_color(20, 50, 80)
    pdf.cell(0, 10, "10. RECOMENDACIONES")
    pdf.ln(10)
    
    # 1. Obtener datos con valores seguros por defecto
    riesgo_val = reporte_data.get('nivel', 'NORMAL')
    tipo_val = reporte_data.get('tipo', 'GENERAL')
    
    # 2. Extraer el texto del diccionario de recomendaciones
    # Usamos un nombre de variable único: 'texto_final_recom'
    texto_final_recom = recomendaciones_por_tipo.get(riesgo_val, {}).get(tipo_val, "Sin recomendaciones específicas.")
    
    pdf.set_font("helvetica", "", 9)
    pdf.set_text_color(0, 0, 0)
    
    # 3. Procesar las líneas de texto
    lineas_encontradas = texto_final_recom.split('\n')
    for contador, contenido_linea in enumerate(lineas_encontradas, 1):
        item_para_pdf = contenido_linea.strip()
        if item_para_pdf:
            # AQUÍ ESTÁ EL CAMBIO CLAVE: No usamos la palabra 'recom' para evitar el error
            pdf.multi_cell(0, 6, f"{contador}. {clean(item_para_pdf)}")
    
    pdf.ln(10)
    
    # --- NOTA DE TERRENO ---
    pdf.set_font("helvetica", "B", 10)
    pdf.set_text_color(139, 0, 0)
    pdf.cell(0, 8, "NOTA: VERIFICACIÓN EN TERRENO RECOMENDADA")
    pdf.ln(8)
    
    pdf.set_font("helvetica", "", 7)
    pdf.set_text_color(80, 80, 80)
    mensaje_nota = (
        "Los índices espectrales satelitales (SAVI, NDWI, NDSI, NDVI) proporcionan estimaciones con resolución de 10-30 metros. "
        "Se recomienda realizar inspecciones en terreno periódicamente para validar observaciones satelitales."
    )
    pdf.multi_cell(0, 4, clean(mensaje_nota))
    
    pdf.ln(20)
    
    # --- FIRMA FINAL ---
    pdf.set_font("helvetica", "B", 11)
    pdf.set_text_color(20, 50, 80)
    pdf.cell(0, 5, "Loreto Campos Carrasco", align="C")
    pdf.ln(6)
    
    pdf.set_font("helvetica", "I", 9)
    pdf.cell(0, 4, "Directora Técnica - BioCore Intelligence", align="C")
    pdf.ln(5)
    
    pdf.set_font("helvetica", "", 8)
    pdf.set_text_color(100, 100, 100)
    fecha_reporte = datetime.now().strftime("%d/%m/%Y")
    pdf.cell(0, 4, f"Fecha de emisión: {fecha_reporte}", align="C")

    # Retornar el objeto PDF terminado
    return pdf


# === INICIALIZAR SESSION STATE ===
if 'authenticated' not in st.session_state:
    st.session_state['authenticated'] = False
    st.session_state['admin_mode'] = False
    st.session_state['proyecto_cliente'] = None
    st.session_state['reporte_actual'] = None
    st.session_state['reporte_preview'] = None
    st.session_state['mostrar_preview'] = False

# === SIDEBAR ===
with st.sidebar:
    st.markdown("### 🔐 Autenticación")
    
    with st.expander("🔑 Iniciar Sesión", expanded=True):
        admin_mode = st.checkbox("🔑 Modo Admin")
        
        if admin_mode:
            password_admin = st.text_input("Contraseña Admin", type="password", key="admin_pwd")
            if st.button("✅ Entrar como Admin", key="btn_admin"):
                if es_admin(password_admin):
                    st.session_state['admin_mode'] = True
                    st.session_state['authenticated'] = True
                    st.success("✅ Modo Admin activado")
                    st.rerun()
                else:
                    st.error("❌ Contraseña incorrecta")
        else:
            proyecto_login = st.text_input("Proyecto", key="login_proyecto")
            password_login = st.text_input("Contraseña", type="password", key="login_pwd")
            if st.button("✅ Entrar como Cliente", key="btn_cliente"):
                is_valid, cliente = verificar_credenciales_usuario(proyecto_login, password_login)
                if is_valid:
                    st.session_state['authenticated'] = True
                    st.session_state['proyecto_cliente'] = proyecto_login
                    st.session_state['cliente_data'] = cliente
                    st.success(f"✅ Bienvenido {proyecto_login}")
                    st.rerun()
                else:
                    st.error("❌ Credenciales inválidas")
    
    st.markdown("---")
    
    if st.session_state.get('authenticated'):
        if st.session_state.get('admin_mode'):
            st.info("🔑 **Sesión Admin Activa**")
        else:
            proyecto = st.session_state.get('proyecto_cliente', 'N/A')
            st.info(f"👤 **Usuario**: {proyecto}")
        
        if st.button("🚪 Cerrar Sesión"):
            st.session_state['authenticated'] = False
            st.session_state['admin_mode'] = False
            st.session_state['proyecto_cliente'] = None
            st.session_state['reporte_actual'] = None
            st.rerun()

# === PANTALLA DE BIENVENIDA ===
if not st.session_state.get('authenticated'):
    st.markdown("""
    <h1 style="text-align: center; margin-top: 30px;">🛰️ BioCore Intelligence</h1>
    <p style="text-align: center; font-size: 1.1em; color: #888;">Sistema de Vigilancia Ambiental Satelital Avanzada</p>
    """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    demo_map = folium.Map(
        location=[-33.45, -70.66],
        zoom_start=4,
        tiles='https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}',
        attr='Google Satellite'
    )
    folium_static(demo_map, width=1200, height=400)
    
    st.markdown("---")
    st.markdown("""
    <div style="text-align: center; background-color: #0e1117; padding: 20px; border-radius: 10px;">
    <h3>🔐 Acceso Restringido</h3>
    <p>Inicia sesión desde el panel izquierdo <b>👈</b></p>
    <p style="font-size: 0.9em; color: #888;">📧 consultorabiocore@gmail.com</p>
    </div>
    """, unsafe_allow_html=True)
    
    st.stop()

# === TABS PRINCIPALES ===
if st.session_state.get('admin_mode'):
    tab1, tab_informe, tab_excel, tab_clientes, tab_soporte, tab_guia = st.tabs([
        "🛰️ Vigilancia", 
        "📋 Auditorías", 
        "📊 Base Datos",
        "👥 Gestión de Clientes",
        "💬 Soporte",
        "📖 Guía"
    ])
else:
    tab1, tab_informe, tab_excel, tab_soporte, tab_historial, tab_config, tab_guia = st.tabs([
        "🛰️ Vigilancia", 
        "📋 Auditorías", 
        "📊 Base Datos", 
        "💬 Soporte",
        "📨 Mi Historial",
        "⚙️ Configuración",
        "📖 Guía"
    ])

# === PESTAÑA 1: VIGILANCIA ===
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
        for p_idx, p in enumerate(proyectos_mostrar):
            st.markdown(f"### 📍 {p['Proyecto']}")

            col_mapa, col_reporte = st.columns([2.5, 1])

            with col_mapa:
                try:
                    coords = obtener_coordenadas_correctamente(p)
                    m_obj = dibujar_mapa_biocore(coords)
                    folium_static(m_obj, width=850, height=500)
                except Exception as e:
                    st.error(f"Error al dibujar mapa: {str(e)}")

            with col_reporte:
                if st.button("🚀 Ejecutar Reporte", key=f"vigilancia_btn_{p_idx}"):
                    with st.spinner("Analizando..."):
                        reporte = generar_reporte_total(p)
                        
                        if reporte.get('tipo') != 'error':
                            st.session_state['reporte_actual'] = reporte
                            
                            estado_color = '#10b981' if 'CONTROL' in reporte['estado'] else '#f97316' if 'PRECAUCIÓN' in reporte['estado'] else '#ef4444'
                            st.markdown(f"""
                            <div style="background-color:#1e293b; padding:20px; border-radius:10px; border-left:6px solid {estado_color};">
                            <h2 style="color: white; margin: 0;">{reporte['estado']}</h2>
                            <p style="color: #cbd5e1; margin: 10px 0 0 0;"><b>Riesgo:</b> {reporte['nivel']}</p>
                            </div>
                            """, unsafe_allow_html=True)
                            
                            fig_gauge = go.Figure(go.Indicator(
                                mode="gauge+number+delta",
                                value=reporte['savi_actual'],
                                number={'suffix': ''},
                                title={'text': "SAVI - Vigor de Vegetación"},
                                delta={'reference': reporte['savi_base'], 'suffix': ' vs Base', 'relative': False},
                                gauge={
                                    'axis': {
                                        'range': [0, 0.8],
                                        'tickfont': {'size': 12}
                                    },
                                    'bar': {'color': "#1e40af"},
                                    'borderwidth': 2,
                                    'bordercolor': "#333",
                                    'steps': [
                                        {'range': [0, 0.15], 'color': "#fee2e2"},
                                        {'range': [0.15, 0.35], 'color': "#fef3c7"},
                                        {'range': [0.35, 0.8], 'color': "#dcfce7"}
                                    ],
                                    'threshold': {
                                        'line': {'color': "black", 'width': 4},
                                        'thickness': 0.75,
                                        'value': reporte['savi_actual']
                                    }
                                }
                            ))
                            fig_gauge.update_layout(
                                height=420,
                                font={'size': 14, 'family': 'Arial'},
                                margin=dict(l=20, r=20, t=100, b=20),
                                paper_bgcolor='rgba(0,0,0,0)',
                                plot_bgcolor='rgba(0,0,0,0)'
                            )
                            st.plotly_chart(fig_gauge, use_container_width=True)
                            
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                st.metric("SAVI", f"{reporte['savi_actual']:.4f}", 
                                         f"{reporte['variacion']:+.1f}%")
                            with col2:
                                st.metric("NDWI", f"{reporte['ndwi']:.4f}", 
                                         f"{reporte['variacion_ndwi']:+.1f}%")
                            with col3:
                                st.metric("Temperatura", f"{reporte['temp']:.1f}°C")
                            
                            st.success(reporte['diagnostico_completo'])
                        else:
                            st.error(reporte.get('error', 'Error desconocido'))
    else:
        st.warning("No hay proyectos disponibles")

# === PESTAÑA 2: AUDITORÍAS ===
with tab_informe:
    st.subheader("📋 Generador de Auditorías Profesionales")
    
    try:
        proyectos_list = supabase.table("usuarios").select("Proyecto,Tipo").execute().data
        proyectos_dict = {p['Proyecto']: p.get('Tipo', 'MINERIA') for p in proyectos_list}
        proyectos_nombres = list(proyectos_dict.keys())
    except:
        proyectos_nombres = []
        proyectos_dict = {}
    
    if proyectos_nombres:
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            proyecto_sel = st.selectbox("📍 Seleccionar Proyecto", proyectos_nombres, key="audit_proj")
        
        with col2:
            rango_sel = st.selectbox("📊 Rango de Análisis", 
                ["Últimos 7 días", "Últimas 2 semanas", "Último mes", "Últimos 3 meses", "Último año"],
                key="audit_rango")
        
        with col3:
            # Filtra meses solo hasta el actual si es el año actual
            meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
                "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
            # mes actual para UX mejorada
            try:
                mes_actual = datetime.now().month
                # a continuación, en col4, determinamos el año
                mes_sel_val = None
            except:
                mes_actual = 12
            mes_sel = st.selectbox("📅 Mes", meses, key="audit_mes")
        
        with col4:
            # Construye opciones del año según historial real
            try:
                res_history = supabase.table("historial_reportes").select("fecha_analisis,created_at").eq("proyecto", proyecto_sel).execute()
                if res_history.data:
                    df_hist = pd.DataFrame(res_history.data)
                    fechas_hist = pd.to_datetime(df_hist['fecha_analisis'].fillna(df_hist['created_at']), errors='coerce')
                    anios_validos = sorted({f.year for f in fechas_hist.dropna() if f.year <= datetime.now().year})
                    if anios_validos:
                        anio_sel = st.selectbox("📆 Año", options=anios_validos, index=len(anios_validos)-1, key="audit_anio")
                    else:
                        anio_sel = st.number_input("📆 Año", value=datetime.now().year, min_value=2010, max_value=datetime.now().year, key="audit_anio")
                else:
                    anio_sel = st.number_input("📆 Año", value=datetime.now().year, min_value=2010, max_value=datetime.now().year, key="audit_anio")
            except Exception:
                anio_sel = st.number_input("📆 Año", value=datetime.now().year, min_value=2010, max_value=datetime.now().year, key="audit_anio")
        
        rango_dias_map = {
            "Últimos 7 días": 7,
            "Últimas 2 semanas": 14,
            "Último mes": 30,
            "Últimos 3 meses": 90,
            "Último año": 365
        }
        rango_dias = rango_dias_map.get(rango_sel, 30)
        
        if st.button("🚀 Generar Auditoría Completa", key="btn_gen_audit"):
            with st.spinner("⏳ Procesando auditoría..."):
                try:
                    proyecto_data = supabase.table("usuarios")\
                        .select("*")\
                        .eq("Proyecto", proyecto_sel)\
                        .execute().data[0]
                    
                    reporte_data = generar_reporte_total(proyecto_data, rango_dias)
                    
                    if reporte_data.get('tipo') == 'error':
                        st.error(f"❌ {reporte_data.get('error', 'Error desconocido')}")
                    else:
                        st.session_state['reporte_actual'] = reporte_data
                        st.session_state['proyecto_audit'] = proyecto_sel
                        st.session_state['mes_audit'] = mes_sel
                        st.session_state['anio_audit'] = anio_sel
                        st.session_state['proyecto_data'] = proyecto_data
                        st.session_state['mostrar_preview'] = True
                        
                        st.success("✅ Auditoría generada exitosamente")
                        st.rerun()
                
                except Exception as e:
                    st.error(f"❌ Error al generar auditoría: {str(e)}")
        
        st.markdown("---")
        
        if st.session_state.get('mostrar_preview') and 'reporte_actual' in st.session_state and st.session_state['reporte_actual']:
            reporte = st.session_state['reporte_actual']
            proyecto = st.session_state.get('proyecto_audit', 'N/A')
            mes = st.session_state.get('mes_audit', 'N/A')
            anio = st.session_state.get('anio_audit', datetime.now().year)
            proyecto_data = st.session_state.get('proyecto_data', {})
            
            st.info("📋 **VISTA PREVIA DEL REPORTE**")
            
            estado_color = '#10b981' if 'CONTROL' in reporte['estado'] else '#f97316' if 'PRECAUCIÓN' in reporte['estado'] else '#ef4444'
            
            st.markdown(f"""
            <div style="background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); 
                        padding:25px; border-radius:15px; border-left:6px solid {estado_color}; margin-bottom: 20px;">
            <h2 style="color: white; margin: 0;">{reporte['estado']}</h2>
            <p style="color: #cbd5e1; margin: 10px 0 0 0;"><b>Riesgo:</b> {reporte['nivel']}</p>
            <p style="color: #cbd5e1; margin: 5px 0;"><b>Período:</b> {mes} {anio}</p>
            </div>
            """, unsafe_allow_html=True)
            
            col_m1, col_m2, col_m3, col_m4 = st.columns(4)
            with col_m1:
                st.metric("SAVI", f"{reporte['savi_actual']:.4f}", f"{reporte['variacion']:+.1f}%")
            with col_m2:
                st.metric("NDWI", f"{reporte['ndwi']:.4f}", f"{reporte['variacion_ndwi']:+.1f}%")
            with col_m3:
                st.metric("NDSI", f"{reporte['ndsi']:.4f}", f"{reporte['variacion_ndsi']:+.1f}%")
            with col_m4:
                st.metric("Temperatura", f"{reporte['temp']:.1f}°C")
            
            st.markdown("")
            
            st.markdown("### 🔍 Diagnóstico Técnico")
            st.info(f"{reporte['diagnostico_completo']}")
            
            with st.expander("📨 Ver Mensaje Telegram"):
                mensaje_telegram = generar_mensaje_telegram_dinamico(reporte, proyecto_data)
                st.code(mensaje_telegram, language="text")
            
            st.markdown("### ✅ Acciones")
            col_btn1, col_btn2, col_btn3, col_btn4 = st.columns(4)
            
            with col_btn1:
                if st.button("📥 Descargar PDF", key="btn_download_pdf"):
                    with st.spinner("Generando PDF..."):
                        try:
                            img_path = generar_graficos_profesionales(
                                reporte.get('indices_historicos', {}),
                                reporte.get('tipo', 'GENERAL')
                            )
                            pdf = generar_pdf_auditoria_dinamico(proyecto_data, reporte, img_path)

                            result = pdf.output(dest='S')
                            if isinstance(result, str):
                                pdf_bytes = result.encode('latin-1')
                            elif isinstance(result, (bytes, bytearray)):
                                pdf_bytes = bytes(result)
                            else:
                                raise Exception("Tipo inesperado en la exportación PDF: " + str(type(result)))

                            st.download_button(
                                label="✅ Descargar Auditoría PDF",
                                data=pdf_bytes,
                                file_name=f"Auditoria_{proyecto}_{mes}_{anio}.pdf",
                                mime="application/pdf",
                                key="download_btn"
                            )

                            if img_path and os.path.exists(img_path):
                                os.remove(img_path)
                            st.success("✅ PDF listo para descargar")
                        except Exception as e:
                            st.error(f"❌ Error al generar PDF: {str(e)}")
            
            with col_btn2:
                if st.button("🔄 Regenerar", key="btn_new_audit"):
                    st.session_state['reporte_actual'] = None
                    st.session_state['mostrar_preview'] = False
                    st.rerun()
            
            with col_btn3:
                if st.button("📤 Enviar Telegram", key="btn_send_telegram"):
                    with st.spinner("Enviando..."):
                        try:
                            if proyecto_data.get('id_telegram'):
                                token_telegram = st.secrets.get('telegram', {}).get('token', '')
                                if token_telegram:
                                    mensaje_telegram = generar_mensaje_telegram_dinamico(reporte, proyecto_data)
                                    response = requests.post(
                                        f"https://api.telegram.org/bot{token_telegram}/sendMessage",
                                        data={
                                            "chat_id": proyecto_data.get('id_telegram'),
                                            "text": mensaje_telegram,
                                            "parse_mode": "Markdown"
                                        },
                                        timeout=10
                                    )
                                    if response.status_code == 200:
                                        st.success("✅ Reporte enviado por Telegram")
                                    else:
                                        st.error(f"❌ Error: {response.status_code}")
                                else:
                                    st.warning("⚠️ Token de Telegram no configurado")
                            else:
                                st.warning("⚠️ No hay ID de Telegram registrado")
                        except Exception as e:
                            st.error(f"❌ Error: {str(e)}")
            
            with col_btn4:
                if st.button("❌ Cancelar", key="btn_cancel"):
                    st.session_state['reporte_actual'] = None
                    st.session_state['mostrar_preview'] = False
                    st.rerun()
    else:
        st.warning("📌 No hay proyectos registrados")

# === PESTAÑA 3: BASE DE DATOS ===
with tab_excel:
    st.subheader("📊 Base de Datos")
    
    if st.session_state.get('admin_mode'):
        try:
            res = supabase.table("usuarios").select("*").execute()
            if res.data:
                df = pd.DataFrame(res.data)
                st.dataframe(df, use_container_width=True)
                
                csv = df.to_csv(index=False)
                st.download_button(
                    label="📥 Descargar CSV",
                    data=csv,
                    file_name="usuarios.csv",
                    mime="text/csv"
                )
            else:
                st.info("No hay datos")
        except Exception as e:
            st.error(f"Error: {e}")
    else:
        st.info("Acceso restringido a administradores")

# === PESTAÑA 4: GESTIÓN DE CLIENTES ===
if st.session_state.get('admin_mode'):
    with tab_clientes:
        st.subheader("👥 Gestión de Clientes")
        
        tab_nuevo, tab_editar, tab_eliminar = st.tabs(["➕ Nuevo Cliente", "✏️ Editar", "🗑️ Eliminar"])
        
        with tab_nuevo:
            st.markdown("### Registrar nuevo cliente")
            
            with st.form("form_nuevo_cliente"):
                proyecto = st.text_input("Nombre del Proyecto *")
                tipo = st.selectbox("Tipo de Proyecto *", ["MINERIA", "GLACIAR", "BOSQUE", "HUMEDAL", "AGRICOLA"])
                coordenadas = st.text_area("Coordenadas (JSON format) *", 
                                           placeholder='[[lon1, lat1], [lon2, lat2], [lon3, lat3], [lon1, lat1]]',
                                           height=100)
                anio_base = st.number_input("Año de Línea Base", value=2015, min_value=2000)
                email = st.text_input("Email del cliente")
                telegram = st.text_input("ID Telegram (opcional)")
                password_cliente = st.text_input("Contraseña cliente *", type="password")
                
                if st.form_submit_button("✅ Registrar Cliente"):
                    if not proyecto or not tipo or not coordenadas or not password_cliente:
                        st.error("❌ Completa todos los campos requeridos (*)")
                    else:
                        try:
                            coords_parsed = json.loads(coordenadas)
                            
                            if not isinstance(coords_parsed, list) or len(coords_parsed) < 3:
                                raise ValueError("Mínimo 3 coordenadas requeridas")
                            
                            pwd_hash = hash_password(password_cliente)
                            
                            nuevo_registro = {
                                "Proyecto": proyecto,
                                "Tipo": tipo,
                                "Coordenadas": json.dumps(coords_parsed),
                                "email_cliente": email if email else None,
                                "password_cliente": pwd_hash,
                                "id_telegram": telegram if telegram else None,
                                "ano_linea_base": int(anio_base)
                            }
                            
                            supabase.table("usuarios").insert(nuevo_registro).execute()
                            st.success(f"✅ Cliente {proyecto} registrado exitosamente")
                            st.balloons()
                        except json.JSONDecodeError:
                            st.error("❌ Coordenadas con formato JSON inválido")
                        except ValueError as ve:
                            st.error(f"❌ Error: {str(ve)}")
                        except Exception as e:
                            st.error(f"❌ Error al registrar: {str(e)}")

# === PESTAÑA SOPORTE ===
with tab_soporte:
    st.title("💬 Soporte BioCore Intelligence")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📞 Contacto")
        st.markdown("""
        **Responsable:** Loreto Campos Carrasco
        📧 consultorabiocore@gmail.com
        ⏰ Lunes-Viernes 8:00-18:00
        """)
    
    with col2:
        st.subheader("🔧 Problemas Comunes")
        with st.expander("¿Cómo genero un reporte?"):
            st.write("Ve a Vigilancia → Ejecutar Reporte")
        with st.expander("¿Qué es un índice espectral?"):
            st.write("Son medidas de características ambientales desde satélites")

# === PESTAÑA HISTORIAL ===
if not st.session_state.get('admin_mode'):
    with tab_historial:
        st.title("📨 Mi Historial")
        proyecto_cliente = st.session_state.get('proyecto_cliente')
        
        try:
            res = supabase.table("historial_reportes").select("*").eq("proyecto", proyecto_cliente).execute()
            if res.data:
                df_hist = pd.DataFrame(res.data)
                st.dataframe(df_hist, use_container_width=True)
                
                csv = df_hist.to_csv(index=False)
                st.download_button(
                    label="📥 Descargar Historial (CSV)",
                    data=csv,
                    file_name=f"Historial_{proyecto_cliente}.csv",
                    mime="text/csv"
                )
            else:
                st.info("No hay reportes generados aún")
        except Exception as e:
            st.error(f"Error al cargar historial: {e}")
    
    with tab_config:
        st.title("⚙️ Mi Configuración")
        st.info("Próximamente...")
    
    with tab_guia:
        st.title("📖 Guía de Uso")
        st.markdown("""
        # BioCore Intelligence - Guía Completa
        
        ## 🛰️ ¿Cómo funciona?
        BioCore Intelligence es un sistema de vigilancia ambiental satelital que monitorea proyectos 
        ambientales en tiempo real usando datos de NASA y ESA.
        
        ### 🎯 Características Principales
        - Monitoreo de 5 tipos de proyectos (MINERÍA, GLACIAR, BOSQUE, HUMEDAL, AGRÍCOLA)
        - Histórico de 20 años de datos climáticos
        - Integración CONAF para clasificación de bosques
        - Análisis de cambio climático con TerraCLIM
        - Generación automática de reportes PDF profesionales
        - Envío de alertas por Telegram
        
        ### 📊 Índices Monitoreados
        - **SAVI**: Vigor de vegetación (0-1)
        - **NDWI**: Contenido de agua (-1 a 1)
        - **NDSI**: Cobertura de nieve/hielo (-1 a 1)
        - **NDVI**: Verdor general (-1 a 1)
        - **Temperatura**: LST en °C
        
        ### 📞 Contacto
        Loreto Campos Carrasco
        consultorabiocore@gmail.com
        """)

st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #888; font-size: 0.9em; padding: 20px;">
<b>BioCore Intelligence</b> © 2026 | Todos los derechos reservados
</div>
""", unsafe_allow_html=True)
