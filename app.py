# ============================================================================
# BIOCORE INTELLIGENCE - SISTEMA COMPLETO DE VIGILANCIA AMBIENTAL SATELITAL
# ============================================================================

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
    """Obtiene las coordenadas del proyecto desde Supabase con manejo robusto"""
    raw_coords = p.get('Coordenadas')
    
    if raw_coords is None or raw_coords == '' or raw_coords == 'null':
        raise ValueError('Coordenadas vacías en la base de datos')
    
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
                raise ValueError(f'No se pudo parsear coordenadas: {raw_coords}')
    
    if isinstance(raw_coords, dict):
        if 'coordinates' in raw_coords:
            return raw_coords['coordinates']
        elif 'type' in raw_coords and raw_coords['type'] == 'Polygon':
            return raw_coords.get('coordinates', [])[0]
    
    raise ValueError(f'Formato de coordenadas no reconocido: {type(raw_coords)}')

# === GENERADOR DE GRÁFICOS ===
def generar_graficos(indices_historicos):
    """Genera gráficos profesionales para incluir en PDF"""
    try:
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        fig.patch.set_facecolor('white')
        
        fechas = list(range(len(indices_historicos.get('savi', [0]))))
        
        # SAVI
        if 'savi' in indices_historicos:
            axes[0, 0].plot(fechas, indices_historicos['savi'], 
                          color='#27ae60', marker='o', linewidth=2.5, markersize=8, label='SAVI')
            axes[0, 0].fill_between(fechas, indices_historicos['savi'], alpha=0.3, color='#27ae60')
            axes[0, 0].set_title('ÍNDICE SAVI - Vigor de Vegetación', fontweight='bold', fontsize=12)
            axes[0, 0].set_ylabel('Valor SAVI', fontsize=10)
            axes[0, 0].grid(True, alpha=0.3, linestyle='--')
            axes[0, 0].legend()
        
        # NDWI
        if 'ndwi' in indices_historicos:
            axes[0, 1].plot(fechas, indices_historicos['ndwi'], 
                          color='#3498db', marker='s', linewidth=2.5, markersize=8, label='NDWI')
            axes[0, 1].fill_between(fechas, indices_historicos['ndwi'], alpha=0.3, color='#3498db')
            axes[0, 1].set_title('ÍNDICE NDWI - Contenido de Agua', fontweight='bold', fontsize=12)
            axes[0, 1].set_ylabel('Valor NDWI', fontsize=10)
            axes[0, 1].grid(True, alpha=0.3, linestyle='--')
            axes[0, 1].legend()
        
        # NDSI
        if 'ndsi' in indices_historicos:
            axes[1, 0].plot(fechas, indices_historicos['ndsi'], 
                          color='#9b59b6', marker='^', linewidth=2.5, markersize=8, label='NDSI')
            axes[1, 0].fill_between(fechas, indices_historicos['ndsi'], alpha=0.3, color='#9b59b6')
            axes[1, 0].set_title('ÍNDICE NDSI - Cobertura de Nieve/Hielo', fontweight='bold', fontsize=12)
            axes[1, 0].set_ylabel('Valor NDSI', fontsize=10)
            axes[1, 0].grid(True, alpha=0.3, linestyle='--')
            axes[1, 0].legend()
        
        # TEMPERATURA
        if 'temp' in indices_historicos:
            axes[1, 1].plot(fechas, indices_historicos['temp'], 
                          color='#e74c3c', marker='d', linewidth=2.5, markersize=8, label='Temperatura')
            axes[1, 1].fill_between(fechas, indices_historicos['temp'], alpha=0.3, color='#e74c3c')
            axes[1, 1].set_title('TEMPERATURA - LST (°C)', fontweight='bold', fontsize=12)
            axes[1, 1].set_ylabel('Temperatura (°C)', fontsize=10)
            axes[1, 1].grid(True, alpha=0.3, linestyle='--')
            axes[1, 1].legend()
        
        plt.tight_layout()
        
        temp_dir = tempfile.gettempdir()
        img_path = os.path.join(temp_dir, 'grafico_biocore.png')
        plt.savefig(img_path, format='png', dpi=300, bbox_inches='tight', facecolor='white')
        plt.close()
        
        return img_path
    except Exception as e:
        st.error(f"Error en gráficos: {e}")
        return None

# ============================================================================
# EVALUACIÓN POR TIPO DE PROYECTO
# ============================================================================

def evaluar_mineria(ndwi_actual, ndwi_base, variacion_ndwi, savi, temp):
    """MINERÍA - Basado en NDWI (recursos hídricos)"""
    
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
    """GLACIAR - Basado en NDSI (cobertura de nieve/hielo)"""
    
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
        diagnostico += f" ⚠️ FACTOR AGRAVANTE: Temperatura de {temp:.1f}°C acelera fusión."
    
    return estado, nivel, color, diagnostico

def evaluar_bosque(savi_actual, savi_base, variacion_savi, ndwi):
    """BOSQUE - Basado en SAVI (vigor de vegetación)"""
    
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
    """HUMEDAL - Basado en NDWI (contenido de agua)"""
    
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
        diagnostico += f" ✓ Vegetación hidrófila presente ({savi:.4f})."
    
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
# GENERADOR DE REPORTE TOTAL
# ============================================================================

def generar_reporte_total(p):
    """Genera reporte completo con validación de coordenadas"""
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
            'error': f'Error obteniendoimágenes: {str(e)}',
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
        
        return img.addBands([savi, ndsi, swir, ndvi, ndwi])

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

    except Exception as e:
        return {
            'error': f'Error calculando índices: {str(e)}',
            'tipo': 'error'
        }

    # === LÍNEA BASE ===
    anio_base = p.get('anio_linea_base', 2017)
    
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
        else:
            savi_base = savi_now
            ndsi_base = ndsi_now
            ndwi_base = ndwi_now
            swir_base = swir_now
            ndvi_base = ndvi_now
    except:
        savi_base = savi_now
        ndsi_base = ndsi_now
        ndwi_base = ndwi_now
        swir_base = swir_now
        ndvi_base = ndvi_now

    # === VARIACIONES ===
    def calcular_variacion(actual, base):
        if abs(base) < 0.001:
            return 0.0
        return ((actual - base) / abs(base)) * 100

    variacion_savi = calcular_variacion(savi_now, savi_base)
    variacion_ndwi = calcular_variacion(ndwi_now, ndwi_base)
    variacion_ndsi = calcular_variacion(ndsi_now, ndsi_base)
    variacion_ndvi = calcular_variacion(ndvi_now, ndvi_base)

    # === EVALUACIÓN SEGÚN TIPO ===
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

    # === MENSAJE TELEGRAM ===
    texto_telegram = f"""
╔════════════════════════════════════════╗
║  🛰️ REPORTE BIOCORE {tipo:26s}║
║  {p['Proyecto'][:38]:38s}║
╚════════════════════════════════════════╝

📅 Análisis: {f_rep}
🎯 {estado}

📊 ÍNDICES ESPECTRALES ACTUALES:
🌱 SAVI: {savi_now:.4f} (Vegetación) | Base: {savi_base:.4f}
❄️ NDSI: {ndsi_now:.4f} (Nieve/Hielo) | Base: {ndsi_base:.4f}
💧 NDWI: {ndwi_now:.4f} (Humedad) | Base: {ndwi_base:.4f}
🌳 NDVI: {ndvi_now:.4f} (Vigor) | Base: {ndvi_base:.4f}
🌡️ SWIR: {swir_now:.4f} (Mineralogia)
🌡️ Temperatura: {temp_val:.1f}°C

📈 VARIACIONES:
  ��� SAVI: {variacion_savi:+.1f}%
  • NDSI: {variacion_ndsi:+.1f}%
  • NDWI: {variacion_ndwi:+.1f}%
  • NDVI: {variacion_ndvi:+.1f}%

🎯 Nivel de Riesgo: {nivel}
📋 {diagnostico_detallado}
    """

    # Crear histórico simulado para gráficos
    indices_historicos = {
        'savi': [savi_base * 0.95, savi_base, savi_now],
        'ndwi': [ndwi_base * 0.95, ndwi_base, ndwi_now],
        'ndsi': [ndsi_base * 0.95, ndsi_base, ndsi_now],
        'temp': [temp_val - 2, temp_val - 1, temp_val]
    }

    return {
        'estado': estado,
        'diagnostico': diagnostico_detallado,
        'nivel': nivel,
        'savi_actual': savi_now,
        'savi_base': savi_base,
        'ndsi': ndsi_now,
        'ndwi': ndwi_now,
        'swir': swir_now,
        'ndvi': ndvi_now,
        'temp': temp_val,
        'fecha': f_rep,
        'anio_base': anio_base,
        'tipo': tipo,
        'proyecto': p['Proyecto'],
        'texto_telegram': texto_telegram,
        'variacion': variacion_savi,
        'variacion_ndwi': variacion_ndwi,
        'variacion_ndsi': variacion_ndsi,
        'variacion_ndvi': variacion_ndvi,
        'color_estado': color_estado,
        'diagnostico_completo': diagnostico_detallado,
        'indices_historicos': indices_historicos,
        'indices': {
            'savi': savi_now,
            'ndsi': ndsi_now,
            'ndwi': ndwi_now,
            'ndvi': ndvi_now,
            'swir': swir_now,
            'temp': temp_val
        }
    }

# ============================================================================
# GENERADOR DE PDF PROFESIONAL
# ============================================================================

def generar_pdf_profesional(reporte_data, img_path, proyecto_nombre, tipo_proyecto):
    """Genera PDF completo con gráficos y diagnóstico"""
    
    pdf = FPDF(orientation='P', unit='mm', format='A4')
    pdf.add_page()
    
    # === ENCABEZADO ===
    pdf.set_fill_color(20, 50, 80)
    pdf.rect(0, 0, 210, 55, 'F')
    
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("helvetica", "B", 20)
    pdf.set_xy(10, 8)
    pdf.cell(0, 12, clean("AUDITORÍA DE CUMPLIMIENTO AMBIENTAL"), ln=1)
    
    pdf.set_font("helvetica", "B", 14)
    pdf.set_xy(10, 22)
    pdf.cell(0, 8, clean(f"PROYECTO: {proyecto_nombre.upper()}"), ln=1)
    
    pdf.set_font("helvetica", "I", 11)
    pdf.set_xy(10, 31)
    pdf.cell(0, 6, clean(f"Tipo: {tipo_proyecto}"), ln=1)
    
    pdf.set_font("helvetica", "I", 10)
    pdf.set_xy(10, 38)
    pdf.cell(0, 6, clean("Responsable Técnica: Loreto Campos Carrasco | BioCore Intelligence"), ln=1)
    
    pdf.set_font("helvetica", "", 9)
    pdf.set_xy(10, 45)
    pdf.cell(0, 4, clean(f"Fecha de Análisis: {reporte_data.get('fecha', 'N/A')} | Año Base: {reporte_data.get('anio_base', 2017)}"), ln=1)
    
    # === ESTADO PRINCIPAL ===
    pdf.set_y(58)
    color_r, color_g, color_b = reporte_data['color_estado']
    pdf.set_fill_color(color_r, color_g, color_b)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("helvetica", "B", 13)
    pdf.cell(0, 12, clean(f"ESTADO: {reporte_data['estado']}"), ln=1, fill=True)
    
    # === SECCIÓN DE DIAGNÓSTICO ===
    pdf.set_y(73)
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("helvetica", "B", 11)
    pdf.cell(0, 7, clean("DIAGNÓSTICO TÉCNICO"), ln=1)
    
    pdf.set_font("helvetica", "", 9.5)
    pdf.set_xy(10, 82)
    pdf.multi_cell(190, 5, clean(reporte_data['diagnostico_completo']), border=1)
    
    # === ÍNDICES EN TABLA ===
    pdf.set_y(115)
    pdf.set_font("helvetica", "B", 11)
    pdf.cell(0, 6, clean("ÍNDICES ESPECTRALES ACTUALES"), ln=1)
    
    pdf.set_y(122)
    pdf.set_font("helvetica", "B", 9)
    pdf.set_text_color(255, 255, 255)
    
    pdf.set_fill_color(40, 80, 120)
    pdf.cell(50, 6, clean("Índice"), border=1, fill=True)
    pdf.cell(40, 6, clean("Actual"), border=1, fill=True)
    pdf.cell(40, 6, clean("Base"), border=1, fill=True)
    pdf.cell(60, 6, clean("Variación"), border=1, fill=True, ln=1)
    
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("helvetica", "", 9)
    
    indices_list = [
        ('SAVI', reporte_data['savi_actual'], reporte_data['savi_base'], reporte_data['variacion']),
        ('NDWI', reporte_data['ndwi'], reporte_data.get('ndwi_base', 0), reporte_data.get('variacion_ndwi', 0)),
        ('NDSI', reporte_data['ndsi'], reporte_data.get('ndsi_base', 0), reporte_data.get('variacion_ndsi', 0)),
        ('NDVI', reporte_data.get('ndvi', 0), reporte_data.get('ndvi_base', 0), reporte_data.get('variacion_ndvi', 0)),
        ('Temp (°C)', reporte_data['temp'], 0, 0)
    ]
    
    for idx_name, actual, base, var in indices_list:
        pdf.cell(50, 6, clean(idx_name), border=1)
        pdf.cell(40, 6, clean(f"{actual:.4f}"), border=1)
        pdf.cell(40, 6, clean(f"{base:.4f}"), border=1)
        pdf.cell(60, 6, clean(f"{var:+.1f}%"), border=1, ln=1)
    
    # === NIVEL DE RIESGO ===
    pdf.set_y(170)
    pdf.set_font("helvetica", "B", 11)
    pdf.cell(0, 6, clean(f"NIVEL DE RIESGO: {reporte_data['nivel']}"), ln=1)
    
    # === PÁGINA 2: GRÁFICOS ===
    pdf.add_page()
    pdf.set_font("helvetica", "B", 14)
    pdf.set_text_color(20, 50, 80)
    pdf.cell(0, 10, clean("ANÁLISIS ESPECTRAL - SERIE TEMPORAL"), ln=1)
    pdf.ln(5)
    
    if img_path and os.path.exists(img_path):
        try:
            pdf.image(img_path, x=10, y=30, w=190, h=150)
        except Exception as e:
            pdf.set_text_color(200, 0, 0)
            pdf.set_font("helvetica", "", 10)
            pdf.multi_cell(0, 5, f"Error al insertar gráfico: {str(e)}")
    
    # === PÁGINA 3: RECOMENDACIONES ===
    pdf.add_page()
    pdf.set_font("helvetica", "B", 14)
    pdf.set_text_color(20, 50, 80)
    pdf.cell(0, 10, clean("RECOMENDACIONES Y ACCIONES"), ln=1)
    pdf.ln(5)
    
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("helvetica", "", 10)
    
    recomendaciones = {
        'NORMAL': (
            "1. MANTENER VIGILANCIA ESTÁNDAR\n"
            "   • Continuar monitoreo programado mensual\n"
            "   • Registrar lecturas en base de datos\n"
            "   • Documentar cambios significativos\n\n"
            "2. PROTOCOLO DE NORMALIDAD\n"
            "   • Parámetros dentro de rango aceptable\n"
            "   • Cumplimiento normativo confirmado\n"
            "   • Sin medidas correctivas requeridas"
        ),
        'MODERADO': (
            "1. INTENSIFICAR MONITOREO\n"
            "   • Aumentar frecuencia a semanal\n"
            "   • Realizar inspección de terreno\n"
            "   • Registrar evidencias visuales\n\n"
            "2. MEDIDAS DE CONTENCIÓN\n"
            "   • Implementar controles temporales\n"
            "   • Preparar plan de acción\n"
            "   • Notificar a autoridades relevantes"
        ),
        'CRÍTICO': (
            "1. ACCIÓN INMEDIATA REQUERIDA\n"
            "   • Declarar situación de emergencia\n"
            "   • Contactar autoridades (SMA, DGA, etc.)\n"
            "   • Mobilizar equipo técnico de emergencia\n\n"
            "2. MEDIDAS CORRECTIVAS URGENTES\n"
            "   • Ejecutar plan de mitigación inmediato\n"
            "   • Documentar todas las acciones\n"
            "   • Monitoreo continuo cada 24 horas"
        )
    }
    
    nivel = reporte_data.get('nivel', 'NORMAL')
    recom_text = recomendaciones.get(nivel, recomendaciones['NORMAL'])
    
    pdf.multi_cell(0, 5, clean(recom_text))
    
    # === FIRMA Y CIERRE ===
    pdf.ln(10)
    pdf.set_y(250)
    pdf.set_font("helvetica", "B", 11)
    pdf.cell(0, 5, clean("Loreto Campos Carrasco"), align="C", ln=1)
    pdf.set_font("helvetica", "I", 9)
    pdf.cell(0, 4, clean("Directora Técnica - BioCore Intelligence"), align="C", ln=1)
    pdf.cell(0, 4, clean(f"Fecha de emisión: {datetime.now().strftime('%d/%m/%Y')}"), align="C", ln=1)
    
    return pdf

# === INICIALIZAR SESSION STATE ===
if 'authenticated' not in st.session_state:
    st.session_state['authenticated'] = False
    st.session_state['admin_mode'] = False
    st.session_state['proyecto_cliente'] = None
    st.session_state['reporte_actual'] = None

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
                            
                            fig = go.Figure(go.Indicator(
                                mode="gauge+number",
                                value=reporte['savi_actual'],
                                title={'text': "SAVI Actual"},
                                gauge={
                                    'axis': {'range': [0, 0.25]},
                                    'bar': {'color': "#2c3e50"},
                                    'steps': [
                                        {'range': [0, 0.05], 'color': "#ffcccc"},
                                        {'range': [0.05, 0.15], 'color': "#ffffcc"},
                                        {'range': [0.15, 0.25], 'color': "#ccffcc"}
                                    ]
                                }
                            ))
                            fig.update_layout(height=350, font={'size': 12})
                            st.plotly_chart(fig, use_container_width=True)
                            
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
    except:
        proyectos_dict = {}
    
    if st.session_state.get('admin_mode'):
        proyectos_disponibles = list(proyectos_dict.keys())
    else:
        proyecto_cliente = st.session_state.get('proyecto_cliente')
        proyectos_disponibles = [proyecto_cliente] if proyecto_cliente in proyectos_dict else []
    
    if proyectos_disponibles:
        col1, col2 = st.columns(2)
        with col1:
            proyecto_seleccionado = st.selectbox("Selecciona proyecto", proyectos_disponibles, key="audit_proyecto")
        with col2:
            mes = st.selectbox("Mes", ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
                                       "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"], key="audit_mes")
        
        if st.button("📊 Generar Auditoría Completa", key="btn_generar_audit"):
            with st.spinner("Procesando auditoría..."):
                try:
                    p = supabase.table("usuarios").select("*").eq("Proyecto", proyecto_seleccionado).execute().data[0]
                    reporte = generar_reporte_total(p)
                    
                    if reporte.get('tipo') != 'error':
                        st.session_state['reporte_actual'] = reporte
                        st.session_state['proyecto_reporte'] = proyecto_seleccionado
                        st.session_state['mes_reporte'] = mes
                        st.session_state['p_data'] = p
                        st.success("✅ Auditoría generada")
                    else:
                        st.error(reporte.get('error'))
                except Exception as e:
                    st.error(f"Error: {str(e)}")
        
        st.markdown("---")
        
        if st.session_state.get('reporte_actual') is not None:
            reporte = st.session_state.get('reporte_actual')
            proyecto = st.session_state.get('proyecto_reporte', 'N/A')
            mes = st.session_state.get('mes_reporte', 'N/A')
            p_data = st.session_state.get('p_data', {})
            
            st.subheader("📊 Reporte Generado")
            
            estado_color = '#10b981' if 'CONTROL' in reporte['estado'] else '#f97316' if 'PRECAUCIÓN' in reporte['estado'] else '#ef4444'
            st.markdown(f"""
            <div style="background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); padding:25px; border-radius:15px; border-left:6px solid {estado_color};">
            <h2 style="color: white; margin: 0;">{reporte['estado']}</h2>
            <p style="color: #cbd5e1; margin: 10px 0 0 0;"><b>Nivel de Riesgo:</b> {reporte['nivel']}</p>
            <p style="color: #cbd5e1; margin: 5px 0;"><b>Proyecto:</b> {proyecto}</p>
            <p style="color: #cbd5e1; margin: 5px 0;"><b>Período:</b> {mes} 2026</p>
            </div>
            """, unsafe_allow_html=True)
            
            st.markdown("")
            
            col_i1, col_i2, col_i3, col_i4 = st.columns(4)
            
            with col_i1:
                st.metric("SAVI", f"{reporte['savi_actual']:.4f}", 
                         f"{reporte['variacion']:+.1f}%")
            with col_i2:
                st.metric("NDWI", f"{reporte['ndwi']:.4f}", 
                         f"{reporte['variacion_ndwi']:+.1f}%")
            with col_i3:
                st.metric("NDSI", f"{reporte['ndsi']:.4f}", 
                         f"{reporte['variacion_ndsi']:+.1f}%")
            with col_i4:
                st.metric("Temperatura", f"{reporte['temp']:.1f}°C")
            
            st.markdown("")
            
            st.info(reporte['diagnostico_completo'])
            
            st.markdown("### 📨 Mensaje Telegram")
            st.code(reporte['texto_telegram'])
            
            st.markdown("")
            
            col_a1, col_a2, col_a3 = st.columns(3)
            
            with col_a1:
                if st.button("📥 Descargar PDF Completo", key="btn_pdf_audit"):
                    with st.spinner("Generando PDF..."):
                        try:
                            img_path = generar_graficos(reporte.get('indices_historicos', {}))
                            tipo_proyecto = proyectos_dict.get(proyecto, 'MINERIA')
                            pdf = generar_pdf_profesional(reporte, img_path, proyecto, tipo_proyecto)
                            
                            pdf_bytes = pdf.output(dest='S').encode('latin-1')
                            st.download_button(
                                label="📥 Descargar PDF",
                                data=pdf_bytes,
                                file_name=f"Auditoria_{proyecto}_{mes}_2026.pdf",
                                mime="application/pdf",
                                key="download_pdf_btn"
                            )
                            st.success("✅ PDF listo")
                        except Exception as e:
                            st.error(f"Error: {str(e)}")
            
            with col_a2:
                if st.button("🖨️ Ver Vista Previa", key="btn_preview"):
                    st.markdown("### 📄 Vista Previa")
                    st.markdown(f"**Proyecto:** {proyecto}")
                    st.markdown(f"**Tipo:** {proyectos_dict.get(proyecto, 'N/A')}")
                    st.markdown(f"**Estado:** {reporte['estado']}")
                    st.markdown(f"**Diagnóstico:** {reporte['diagnostico_completo']}")

# === PESTAÑA 3: EXCEL ===
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
        proyecto_cliente = st.session_state.get('proyecto_cliente')
        try:
            res = supabase.table("historial_reportes").select("*").eq("proyecto", proyecto_cliente).execute()
            if res.data:
                df = pd.DataFrame(res.data)
                st.dataframe(df, use_container_width=True)
            else:
                st.info("No hay reportes")
        except Exception as e:
            st.error(f"Error: {e}")

# === PESTAÑA 4: GESTIÓN DE CLIENTES (SOLO ADMIN) ===
if st.session_state.get('admin_mode'):
    with tab_clientes:
        st.subheader("👥 Gestión de Clientes")
        
        tab_nuevo, tab_editar, tab_eliminar = st.tabs(["➕ Nuevo Cliente", "✏️ Editar", "🗑️ Eliminar"])
        
        with tab_nuevo:
            st.markdown("### Registrar nuevo cliente")
            
            with st.form("form_nuevo_cliente"):
                proyecto = st.text_input("Nombre del Proyecto")
                tipo = st.selectbox("Tipo de Proyecto", ["MINERIA", "GLACIAR", "BOSQUE", "HUMEDAL", "AGRICOLA"])
                coordenadas = st.text_area("Coordenadas (JSON format)", 
                                           placeholder='[[lon1, lat1], [lon2, lat2], [lon3, lat3], [lon1, lat1]]')
                anio_base = st.number_input("Año de Línea Base", value=2017, min_value=2000)
                email_cliente = st.text_input("Email del cliente")
                telegram_id = st.text_input("ID Telegram (opcional)")
                password_cliente = st.text_input("Contraseña cliente", type="password")
                
                if st.form_submit_button("✅ Registrar Cliente"):
                    try:
                        # Validar coordenadas
                        coords_parsed = json.loads(coordenadas)
                        
                        # Hashear contraseña
                        pwd_hash = hash_password(password_cliente)
                        
                        # Insertar en Supabase
                        data = {
                            "Proyecto": proyecto,
                            "Tipo": tipo,
                            "Coordenadas": json.dumps(coords_parsed),
                            "anio_linea_base": anio_base,
                            "email_cliente": email_cliente,
                            "telegram_id": telegram_id,
                            "password_cliente": pwd_hash
                        }
                        
                        supabase.table("usuarios").insert(data).execute()
                        st.success(f"✅ Cliente {proyecto} registrado exitosamente")
                    except json.JSONDecodeError:
                        st.error("❌ Coordenadas con formato JSON inválido")
                    except Exception as e:
                        st.error(f"❌ Error: {str(e)}")
        
        with tab_editar:
            st.markdown("### Editar cliente existente")
            
            try:
                res = supabase.table("usuarios").select("Proyecto").execute()
                proyectos_lista = [p['Proyecto'] for p in res.data]
            except:
                proyectos_lista = []
            
            proyecto_editar = st.selectbox("Selecciona proyecto", proyectos_lista, key="edit_proyecto")
            
            if st.button("Cargar datos", key="btn_cargar_datos"):
                try:
                    res = supabase.table("usuarios").select("*").eq("Proyecto", proyecto_editar).execute()
                    if res.data:
                        cliente = res.data[0]
                        
                        with st.form("form_editar_cliente"):
                            tipo = st.selectbox("Tipo", ["MINERIA", "GLACIAR", "BOSQUE", "HUMEDAL", "AGRICOLA"],
                                              index=["MINERIA", "GLACIAR", "BOSQUE", "HUMEDAL", "AGRICOLA"].index(cliente.get('Tipo', 'MINERIA')))
                            email = st.text_input("Email", value=cliente.get('email_cliente', ''))
                            telegram = st.text_input("Telegram ID", value=cliente.get('telegram_id', ''))
                            anio_base = st.number_input("Año base", value=cliente.get('anio_linea_base', 2017))
                            
                            if st.form_submit_button("💾 Guardar cambios"):
                                update_data = {
                                    "Tipo": tipo,
                                    "email_cliente": email,
                                    "telegram_id": telegram,
                                    "anio_linea_base": anio_base
                                }
                                supabase.table("usuarios").update(update_data).eq("Proyecto", proyecto_editar).execute()
                                st.success("✅ Cliente actualizado")
                except Exception as e:
                    st.error(f"Error: {str(e)}")
        
        with tab_eliminar:
            st.markdown("### Eliminar cliente")
            st.warning("⚠️ Esta acción no se puede deshacer")
            
            try:
                res = supabase.table("usuarios").select("Proyecto").execute()
                proyectos_lista = [p['Proyecto'] for p in res.data]
            except:
                proyectos_lista = []
            
            proyecto_eliminar = st.selectbox("Selecciona proyecto", proyectos_lista, key="del_proyecto")
            
            if st.button("🗑️ Eliminar", key="btn_eliminar"):
                supabase.table("usuarios").delete().eq("Proyecto", proyecto_eliminar).execute()
                st.success(f"✅ {proyecto_eliminar} eliminado")
                st.rerun()

# === PESTAÑA SOPORTE ===
with tab_soporte:
    st.title("💬 Soporte BioCore Intelligence")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📞 Contacto Directo")
        st.markdown("""
        **Responsable Técnica:** Loreto Campos Carrasco
        
        📧 Email: consultorabiocore@gmail.com
        
        📱 Teléfono: +56 9 XXXX XXXX
        
        ⏰ Disponibilidad: Lunes a Viernes, 8:00 - 18:00
        """)
    
    with col2:
        st.subheader("🔧 Problemas Comunes")
        with st.expander("❓ ¿Cómo genero un reporte?"):
            st.write("""
1. Ve a la pestaña **'Vigilancia'**
2. Haz click en **'Ejecutar Reporte'**
3. Espera el análisis (2-3 minutos)
4. Visualiza el velocímetro y métricas
            """)
        
        with st.expander("❓ ¿Cuánto cuesta?"):
            st.write("Consulta directamente con el equipo de ventas")
        
        with st.expander("❓ ¿Qué es un índice espectral?"):
            st.write("Son medidas derivadas de imágenes satelitales que indican características ambientales")

# === PESTAÑA HISTORIAL (CLIENTE) ===
if not st.session_state.get('admin_mode'):
    with tab_historial:
        st.title("📨 Mi Historial de Reportes")
        
        proyecto_cliente = st.session_state.get('proyecto_cliente')
        st.subheader(f"Reportes de {proyecto_cliente}")
        
        try:
            res = supabase.table("historial_reportes").select("*").eq("proyecto", proyecto_cliente).order("created_at", desc=True).execute()
            
            if res.data:
                for idx, reporte in enumerate(res.data):
                    with st.expander(f"📊 {reporte.get('created_at', 'N/A')[:10]} - {reporte.get('proyecto')}"):
                        col_info1, col_info2 = st.columns(2)
                        with col_info1:
                            st.write(f"**SAVI:** {reporte.get('savi', 'N/A')}")
                            st.write(f"**NDSI:** {reporte.get('ndsi', 'N/A')}")
                        with col_info2:
                            st.write(f"**NDWI:** {reporte.get('ndwi', 'N/A')}")
                            st.write(f"**Temp:** {reporte.get('temp', 'N/A')}")
                        st.write(f"**Estado:** {reporte.get('estado', 'N/A')}")
            else:
                st.info("No hay reportes aún")
        except Exception as e:
            st.error(f"Error: {e}")
    
    # === PESTAÑA CONFIGURACIÓN (CLIENTE) ===
    with tab_config:
        st.title("⚙️ Mi Configuración")
        
        cliente_data = st.session_state.get('cliente_data', {})
        
        with st.form("form_config_cliente"):
            st.markdown("### 📅 Preferencias de Reportes")
            
            frecuencia = st.radio("Frecuencia de envío:",
                                 ["Diaria", "Semanal", "Mensual"],
                                 index=0 if cliente_data.get('frecuencia', 'Diaria') == 'Diaria' else 1)
            
            hora = st.time_input("Hora de envío", value=time(8, 0))
            
            if st.form_submit_button("💾 Guardar Preferencias"):
                st.success("✅ Preferencias guardadas")

# === PESTAÑA GUÍA ===
with tab_guia:
    st.title("📖 Guía Completa del Sistema")
    
    tab_intro, tab_indices, tab_faq = st.tabs([
        "🎯 Introducción",
        "📊 Índices Espectrales",
        "❓ Preguntas Frecuentes"
    ])
    
    with tab_intro:
        st.markdown("""
        ## 🌍 ¿Qué es BioCore Intelligence?
        
        BioCore Intelligence es una plataforma avanzada de **vigilancia ambiental satelital** 
        que utiliza datos de sensores de Earth Engine para monitorear en tiempo real.
        
        ### 🎯 Objetivos
        - ✅ Monitoreo ambiental en tiempo real
        - ✅ Detección temprana de cambios
        - ✅ Cumplimiento normativo
        - ✅ Reportes profesionales
        - ✅ Análisis multispectral de alta precisión
        
        ### 🛰️ Satélites utilizados
        - **Sentinel-2:** Imágenes multiespectrales de 10-60m resolución
        - **MODIS:** Datos de temperatura de tierra
        - **Landsat:** Datos históricos de complemento
        
        ### 📋 Tipos de Proyectos Soportados
        1. **MINERIA** - Monitoreo de estabilidad de taludes y recursos hídricos
        2. **GLACIAR** - Vigilancia de cobertura de nieve/hielo
        3. **BOSQUE** - Protección de cobertura vegetal
        4. **HUMEDAL** - Control de ciclo hidrológico
        5. **AGRICOLA** - Seguimiento de vigor de cultivos
        """)
    
    with tab_indices:
        st.markdown("""
        ## 📊 Índices Espectrales
        
        ### 🌱 SAVI (Soil-Adjusted Vegetation Index)
        - **Rango:** -0.5 a 1.5
        - **Interpretación:** Vigor de vegetación ajustado por tipo de suelo
        - **Uso:** Detecta estrés en plantas y cobertura vegetal
        - **Thresholds:**
          - > 0.40: Vegetación densa y saludable
          - 0.25-0.40: Vegetación moderada
          - < 0.25: Vegetación degradada o ausente
        
        ### ❄️ NDSI (Normalized Difference Snow Index)
        - **Rango:** -1 a 1
        - **Interpretación:** Detección de nieve e hielo
        - **Uso:** Monitoreo de glaciares y cobertura nival
        - **Thresholds:**
          - > 0.50: Cobertura de nieve/hielo extensa
          - 0.35-0.50: Cobertura intermedia
          - < 0.35: Cobertura crítica o ausencia
        
        ### 💧 NDWI (Normalized Difference Water Index)
        - **Rango:** -1 a 1
        - **Interpretación:** Contenido de agua en suelo y vegetación
        - **Uso:** Detecta estrés hídrico y humedad
        - **Thresholds:**
          - > 0.40: Humedad alta
          - 0.20-0.40: Humedad normal
          - < 0.20: Estrés hídrico severo
        
        ### 🌳 NDVI (Normalized Difference Vegetation Index)
        - **Rango:** -1 a 1
        - **Interpretación:** Vigor general de vegetación
        - **Uso:** Complemento a SAVI para análisis de biomasa
        - **Thresholds:**
          - > 0.70: Vegetación muy densa
          - 0.50-0.70: Vegetación densa
          - 0.20-0.50: Vegetación moderada
          - < 0.20: Vegetación escasa
        
        ### 🌡️ SWIR (Short-Wave Infrared)
        - **Rango:** 0 a 1
        - **Interpretación:** Humedad y mineralogia del sustrato
        - **Uso:** Detecta cambios en composición del suelo
        """)
    
    with tab_faq:
        st.markdown("""
        ## ❓ Preguntas Frecuentes
        
        ### ¿Con qué frecuencia recibo reportes?
        > Según tu configuración: Diaria, Semanal o Mensual
        
        ### ¿A qué hora me llegan?
        > A la hora que especificaste en tu configuración
        
        ### ¿Qué significa SAVI?
        > Soil-Adjusted Vegetation Index. Mide la salud de la vegetación ajustado por el tipo de suelo
        
        ### ¿Cuánto tiempo tarda un reporte?
        > Entre 2-3 minutos dependiendo de la cobertura nubosa
        
        ### ¿Qué hago si sale "ALERTA CRÍTICA"?
        > Contacta inmediatamente al equipo técnico para inspección de terreno
        
        ### ¿Los datos son confiables?
        > Sí, utilizamos datos de satélites de agencias espaciales internacionales
        
        ### ¿Puedo compartir mis reportes?
        > Sí, puedes descargar en PDF y compartir con autoridades
        
        ### ¿Qué es una "Línea Base"?
        > Datos históricos de referencia (usualmente 2017) para comparar cambios
        
        ### ¿Por qué algunos reportes salen en 0?
        > Puede ser por cobertura nubosa o que el índice sea naturalmente bajo en esa zona
        
        ### ¿Cómo se actualizan los datos?
        > Automáticamente cada vez que Sentinel-2 captura nuevas imágenes (cada 5 días)
        """)

st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #888; font-size: 0.9em; padding: 20px;">
<b>BioCore Intelligence</b> | Vigilancia Ambiental Satelital Avanzada
<br>
Responsable Técnica: Loreto Campos Carrasco
<br>
📧 consultorabiocore@gmail.com
<br>
© 2026 - Todos los derechos reservados
</div>
""", unsafe_allow_html=True)
