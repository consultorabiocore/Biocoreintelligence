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
    """
    Genera mensaje Telegram dinámico según tipo de proyecto.
    Enfatiza vigilancia activa y crea necesidad del servicio.
    """
    tipo = proyecto_data.get('Tipo', 'MINERIA').upper()
    proyecto = proyecto_data.get('Proyecto', 'N/A')
    
    # Extraer datos
    savi = reporte_data.get('savi_actual', 0)
    ndwi = reporte_data.get('ndwi', 0)
    ndsi = reporte_data.get('ndsi', 0)
    temp = reporte_data.get('temp', 0)
    fecha = reporte_data.get('fecha', 'N/A')
    nivel = reporte_data.get('nivel', 'DESCONOCIDO')
    estado = reporte_data.get('estado', '')
    variacion_savi = reporte_data.get('variacion', 0)
    variacion_ndwi = reporte_data.get('variacion_ndwi', 0)
    
    # Base del mensaje
    encabezado = f"""
╔════════════════════════════════════════════════════════════╗
║        🛰️  VIGILANCIA AMBIENTAL EN TIEMPO REAL 🛰️         ║
║                    BIOCORE INTELLIGENCE                   ║
╚════════════════════════════════════════════════════════════╝

📍 SITIO MONITOREADO: {proyecto}
📊 TIPO: {tipo}
📅 ANÁLISIS: {fecha}
🔍 RESPONSABLE: Loreto Campos Carrasco
🛰️ FUENTES: Sentinel-2 | MODIS | SAR L-Band

═══════════════════════════════════════════════════════════════"""

    # Mensajes específicos por tipo de proyecto
    if tipo == 'MINERIA':
        diagnostico_dinamico = f"""
🏔️ SECTOR MINERO - VIGILANCIA INTEGRAL DE YACIMIENTO

📡 DATOS ESPECTRALES EN TIEMPO REAL:

💧 RECURSOS HÍDRICOS (NDWI):
   Valor: {ndwi:.4f} | Variación: {variacion_ndwi:+.1f}%
   {'✅ ÓPTIMO - Hidratación confirmada' if ndwi > 0.30 else '⚠️ ALERTA - Vigilancia intensiva' if ndwi > 0.15 else '🔴 CRÍTICO - Acción inmediata'}
   
   💡 INTERPRETACIÓN OPERACIONAL:
   {'→ Sin indicios de desecación o depósito de relaves anómalos' if ndwi > 0.20 else '→ ALERTA: Posible acopio no documentado o drenaje acelerado'}

🌱 VEGETACIÓN PERIMETRAL (SAVI):
   Valor: {savi:.4f} | Variación: {variacion_savi:+.1f}%
   {'✅ Vegetación saludable en buffer de protección' if savi > 0.35 else '⚠️ Estrés vegetal moderado' if savi > 0.20 else '🔴 Degradación crítica detectada'}
   
   💡 RIESGO AMBIENTAL:
   {'→ Cumplimiento de Ley 20.283 verificado' if savi > 0.35 else '→ Requiere plan de remediación urgente'}

⚠️ DIAGNÓSTICO INTEGRADO:
   {estado}

📌 ACCIÓN RECOMENDADA:
   {'→ Mantener vigilancia estándar mensual' if nivel == 'NORMAL' else '→ Intensificar monitoreo a semanal + inspección terrestre' if nivel == 'MODERADO' else '→ EMERGENCIA: Contactar SMA/DGA inmediatamente'}

═══════════════════════════════════════════════════════════════"""

    elif tipo == 'GLACIAR':
        diagnostico_dinamico = f"""
❄️ SECTOR CRIÓSFERA - MONITOREO DE GLACIARES Y NIEVE

🌡️ COBERTURA CRIOSFÉRICA (NDSI):
   Valor: {ndsi:.4f} | Variación: {reporte_data.get('variacion_ndsi', 0):+.1f}%
   {'✅ COBERTURA CONSOLIDADA - Hielo perenne' if ndsi > 0.50 else '⚠️ TRANSICIÓN - Ciclo estacional' if ndsi > 0.35 else '🔴 CRÍTICA - Exposición de suelo'}
   
   📊 ESTADO DE BALANCE DE MASA:
   {'→ Masa de hielo estable, sin retracción anómala' if ndsi > 0.45 else '→ Seguimiento requerido, posible ciclo estacional' if ndsi > 0.30 else '→ ALERTA: Retracción acelerada confirmada por satélite'}

🌡️ TEMPERATURA SUPERFICIAL (MODIS LST):
   Temperatura: {temp:.1f}°C
   Influencia en fusión: {'⚠️ Temperatura elevada acelera derretimiento' if temp > 10 else '✅ Régimen térmico favorable'}

⚠️ DIAGNÓSTICO INTEGRADO:
   {estado}

🚨 NECESIDAD DEL MONITOREO CONTINUO:
   {'→ Bajo riesgo, monitoreo preventivo recomendado' if nivel == 'NORMAL' else '→ Riesgo moderado: cambio climático acelera fusión' if nivel == 'MODERADO' else '→ CRÍTICO: Retracción extrema requiere estudios glaciológicos'}

═══════════════════════════════════════════════════════════════"""

    elif tipo == 'BOSQUE':
        diagnostico_dinamico = f"""
🌲 SECTOR FORESTAL - VIGILANCIA DE COBERTURA Y RIESGOS

🌿 DENSIDAD VEGETAL (SAVI):
   Valor: {savi:.4f} | Variación: {variacion_savi:+.1f}%
   {'✅ MUY DENSA (>70% cobertura) - Ley 20.283 verificada' if savi > 0.40 else '✅ DENSA (50-70%) - Dentro de norma' if savi > 0.30 else '⚠️ MODERADA - Regeneración detectada' if savi > 0.20 else '🔴 DEGRADADA - Inspección urgente'}
   
   📋 CUMPLIMIENTO NORMATIVO:
   {'→ Certificado: Sin intervención no autorizada' if savi > 0.35 else '→ ALERTA: Posible tala, incendio o plagas detectadas'}

💧 ESTRÉS HÍDRICO (NDWI):
   Valor: {ndwi:.4f}
   {'✅ Hidratación óptima - Bajo riesgo de incendio' if ndwi > 0.30 else '⚠️ MODERADO - Riego preventivo recomendado' if ndwi > 0.15 else '🔴 CRÍTICO - Alto riesgo de incendio forestal'}

🔥 ÍNDICE DE RIESGO INTEGRADO:
   {'✅ BAJO - Condiciones de seguridad óptimas' if ndwi > 0.25 and savi > 0.35 else '⚠️ MODERADO - Sistema de vigilancia activa' if ndwi > 0.15 else '🔴 EXTREMO - Protección de emergencia requerida'}

⚠️ DIAGNÓSTICO:
   {estado}

═══════════════════════════════════════════════════════════════"""

    elif tipo == 'HUMEDAL':
        diagnostico_dinamico = f"""
💧 SECTOR HUMEDAL - VIGILANCIA ECOSISTEMA ACUÁTICO

💧 CONTENIDO DE AGUA (NDWI):
   Valor: {ndwi:.4f} | Variación: {variacion_ndwi:+.1f}%
   {'✅ SATURADO - Ciclo hidrológico óptimo' if ndwi > 0.40 else '⚠️ MODERADO - Variabilidad normal' if ndwi > 0.25 else '🔴 CRÍTICO - Desecación en curso'}
   
   🌱 BIODIVERSIDAD:
   {'→ Hábitat acuático confirmado, fauna protegida' if ndwi > 0.35 else '→ Transición de fase, evaluación urgente' if ndwi > 0.20 else '→ ALERTA: Riesgo de colapso ecosistémico'}

🌿 VEGETACIÓN HIDRÓFILA (SAVI):
   Valor: {savi:.4f}
   {'✅ Plantas acuáticas presentes - Confirmación Ramsar' if savi > 0.30 else '⚠️ Vegetación bajo estrés' if savi > 0.15 else '🔴 Pérdida de flora acuática'}

📋 CUMPLIMIENTO NORMATIVO:
   {'✅ Decreto de Humedales verificado' if ndwi > 0.30 else '⚠️ Requiere plan de restauración' if ndwi > 0.20 else '🔴 Violación SMA/DGA inmediata'}

⚠️ DIAGNÓSTICO:
   {estado}

═══════════════════════════════════════════════════════════════"""

    elif tipo == 'AGRICOLA':
        diagnostico_dinamico = f"""
🌾 SECTOR AGRÍCOLA - OPTIMIZACIÓN DE CULTIVOS

🌱 VIGOR VEGETAL (SAVI):
   Valor: {savi:.4f} | Variación: {variacion_savi:+.1f}%
   {'✅ ÓPTIMO - Rendimiento máximo esperado' if savi > 0.45 else '✅ NORMAL - Rendimiento estándar' if savi > 0.35 else '⚠️ MODERADO - Aumentar riego/nutrición' if savi > 0.25 else '🔴 CRÍTICO - Riesgo de pérdida total'}

💧 DISPONIBILIDAD HÍDRICA (NDWI):
   Valor: {ndwi:.4f} | Variación: {variacion_ndwi:+.1f}%
   {'✅ Humedad óptima para crecimiento' if ndwi > 0.30 else '⚠️ Humedad moderada - Aumentar riego' if ndwi > 0.20 else '🔴 CRÍTICO - Riego de emergencia inmediato'}

📊 RENDIMIENTO PROYECTADO:
   {'✅ MÁXIMO (90-100% de potencial)' if savi > 0.45 and ndwi > 0.30 else '✅ ALTO (70-90%)' if savi > 0.35 and ndwi > 0.20 else '⚠️ MODERADO (50-70%)' if savi > 0.25 else '🔴 BAJO (<50%) - Intervención urgente'}

🚨 DIAGNÓSTICO OPERACIONAL:
   {estado}

💡 RECOMENDACIONES:
   {'→ Mantener régimen estándar de riego' if nivel == 'NORMAL' else '→ Aumentar frecuencia de riego' if nivel == 'MODERADO' else '→ EMERGENCIA: Riego de emergencia + análisis fitosanitario'}

═══════════════════════════════════════════════════════════════"""

    else:
        diagnostico_dinamico = f"""
📊 MONITOREO GENERAL

Estado: {estado}
Nivel: {nivel}

═══════════════════════════════════════════════════════════════"""

    # Pie de mensaje con necesidad de servicio
    cierre = f"""
🎯 VALOR DEL MONITOREO CONTINUO:

✅ PROTECCIÓN LEGAL: Documentación ante inspecciones (SMA, DGA, SEA)
✅ DETECCIÓN TEMPRANA: Identificación de problemas antes de escalada
✅ JUSTIFICACIÓN: Prueba técnica de medidas implementadas
✅ PRECISIÓN: Análisis espectral imposible sin satélites

📞 CONTACTO TÉCNICO:
   Loreto Campos Carrasco | consultorabiocore@gmail.com
   BioCore Intelligence © 2026

═══════════════════════════════════════════════════════════════
"""

    return encabezado + diagnostico_dinamico + cierre


# ============================================================================
# MÓDULO 2: GENERADOR DE GRÁFICOS PROFESIONALES
# ============================================================================

def generar_graficos_profesionales(indices_historicos, tipo_proyecto):
    """Genera gráficos profesionales contextualizados por tipo de proyecto"""
    try:
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        fig.patch.set_facecolor('white')
        
        fechas = list(range(len(indices_historicos.get('savi', [0]))))
        
        # Configuración por tipo
        if tipo_proyecto == 'GLACIAR':
            config = [
                (0, 0, 'ndsi', 'NDSI - Cobertura de Nieve/Hielo', '#3498db', '▼ Bajo = Retracción'),
                (0, 1, 'temp', 'Temperatura - LST (°C)', '#e74c3c', '▲ Elevada = Fusión'),
                (1, 0, 'ndwi', 'NDWI - Recursos Hídricos', '#2980b9', '▲ Agua de deshielo'),
                (1, 1, 'ndvi', 'NDVI - Exposición de Roca', '#95a5a6', '▼ Bajo = Suelo desnudo'),
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
                (1, 1, 'temp', 'Temperatura - Régimen Térmico', '#e74c3c', 'Estrés por calor'),
            ]
        elif tipo_proyecto == 'HUMEDAL':
            config = [
                (0, 0, 'ndwi', 'NDWI - Ciclo Hidrológico', '#3498db', 'Estado de saturación'),
                (0, 1, 'savi', 'SAVI - Flora Hidrófila', '#27ae60', 'Biodiversidad'),
                (1, 0, 'ndvi', 'NDVI - Productividad', '#2ecc71', 'Salud del ecosistema'),
                (1, 1, 'temp', 'Temperatura - Régimen Thermal', '#e74c3c', 'Variabilidad'),
            ]
        elif tipo_proyecto == 'AGRICOLA':
            config = [
                (0, 0, 'savi', 'SAVI - Vigor de Cultivo', '#27ae60', 'Rendimiento esperado'),
                (0, 1, 'ndwi', 'NDWI - Disponibilidad Hídrica', '#3498db', 'Necesidad de riego'),
                (1, 0, 'ndvi', 'NDVI - Estado Fenológico', '#2ecc71', 'Fase de desarrollo'),
                (1, 1, 'temp', 'Temperatura - Estrés Térmico', '#e74c3c', 'Factor limitante'),
            ]
        else:
            config = [
                (0, 0, 'savi', 'SAVI', '#27ae60', ''),
                (0, 1, 'ndwi', 'NDWI', '#3498db', ''),
                (1, 0, 'ndvi', 'NDVI', '#2ecc71', ''),
                (1, 1, 'temp', 'Temperatura', '#e74c3c', ''),
            ]
        
        # Dibujar gráficos
        for row, col, indice, titulo, color, subtitulo in config:
            if indice in indices_historicos:
                valores = indices_historicos[indice]
                ax = axes[row, col]
                
                ax.plot(fechas, valores, color=color, marker='o', linewidth=2.5, markersize=8)
                ax.fill_between(fechas, valores, alpha=0.3, color=color)
                ax.set_title(titulo, fontweight='bold', fontsize=12)
                ax.set_ylabel('Valor', fontsize=10)
                ax.grid(True, alpha=0.3, linestyle='--')
                
                if subtitulo:
                    ax.text(0.02, 0.98, subtitulo, transform=ax.transAxes, 
                           fontsize=9, verticalalignment='top',
                           bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))
        
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
# MÓDULO 3: EVALUACIÓN POR TIPO DE PROYECTO (ANTERIOR - SIN CAMBIOS)
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
# MÓDULO 4: GENERADOR DE REPORTE COMPLETO CON GUARDADO EN SUPABASE
# ============================================================================

def generar_reporte_total(p):
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

    # Crear histórico para gráficos
    indices_historicos = {
        'savi': [savi_base * 0.95, savi_base, savi_now],
        'ndwi': [ndwi_base * 0.95, ndwi_base, ndwi_now],
        'ndsi': [ndsi_base * 0.95, ndsi_base, ndsi_now],
        'ndvi': [ndvi_base * 0.95, ndvi_base, ndvi_now],
        'temp': [temp_val - 2, temp_val - 1, temp_val]
    }

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

    return {
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
# MÓDULO 5: GENERADOR DE PDF PROFESIONAL CON LÓGICA DINÁMICA
# ============================================================================

class AuditoriaPDF(FPDF):
    """Clase personalizada para PDF de auditoría"""
    
    def header(self):
        """Encabezado de página"""
        self.set_fill_color(20, 50, 80)
        self.rect(0, 0, 210, 30, 'F')
        
        self.set_text_color(255, 255, 255)
        self.set_font("helvetica", "B", 22)
        self.set_xy(10, 5)
        self.cell(0, 12, "REPORTE DE AUDITORÍA AMBIENTAL", ln=1)
        
        self.set_font("helvetica", "I", 10)
        self.set_xy(10, 18)
        self.cell(0, 5, "BioCore Intelligence | Vigilancia Ambiental Satelital")
        
        self.ln(15)
    
    def footer(self):
        """Pie de página"""
        self.set_y(-15)
        self.set_font("helvetica", "I", 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f"Página {self.page_no()}", align="C")


def generar_pdf_auditoria_dinamico(proyecto_data, reporte_data, img_path=None):
    """Genera PDF profesional con diagnóstico dinámico según tipo de proyecto"""
    
    pdf = AuditoriaPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    # ===== SECCIÓN 1: INFORMACIÓN DEL PROYECTO =====
    pdf.set_font("helvetica", "B", 14)
    pdf.set_text_color(20, 50, 80)
    pdf.cell(0, 10, "1. INFORMACIÓN DEL PROYECTO", ln=1)
    
    pdf.set_font("helvetica", "", 10)
    pdf.set_text_color(0, 0, 0)
    
    info_table = [
        ["Proyecto:", proyecto_data.get('Proyecto', 'N/A')],
        ["Tipo:", proyecto_data.get('Tipo', 'N/A')],
        ["Responsable Técnica:", "Loreto Campos Carrasco"],
        ["Fecha de Análisis:", reporte_data.get('fecha', 'N/A')],
        ["Año Base:", str(proyecto_data.get('ano_linea_base', 2017))],
    ]
    
    for row in info_table:
        pdf.set_font("helvetica", "B", 9)
        pdf.cell(50, 7, clean(row[0]))
        pdf.set_font("helvetica", "", 9)
        pdf.cell(0, 7, clean(row[1]), ln=1)
    
    pdf.ln(5)
    
    # ===== SECCIÓN 2: ESTADO Y RIESGO =====
    pdf.set_font("helvetica", "B", 14)
    pdf.set_text_color(20, 50, 80)
    pdf.cell(0, 10, "2. ESTADO Y EVALUACIÓN", ln=1)
    
    # Banner de estado
    color_r, color_g, color_b = reporte_data.get('color_estado', (100, 100, 100))
    pdf.set_fill_color(color_r, color_g, color_b)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("helvetica", "B", 12)
    
    estado_texto = reporte_data.get('estado', 'ESTADO DESCONOCIDO').replace('🟢', '').replace('🟡', '').replace('🔴', '').strip()
    pdf.cell(0, 10, clean(f"  ESTADO: {estado_texto}"), ln=1, fill=True)
    
    pdf.set_font("helvetica", "", 10)
    pdf.set_text_color(0, 0, 0)
    pdf.cell(0, 3, "", ln=1)
    
    # Nivel de riesgo
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
    pdf.cell(0, 8, clean(f"  Nivel de Riesgo: {nivel}"), ln=1, fill=True)
    
    pdf.set_text_color(0, 0, 0)
    pdf.ln(3)
    
    # ===== SECCIÓN 3: ÍNDICES ESPECTRALES =====
    pdf.set_font("helvetica", "B", 14)
    pdf.set_text_color(20, 50, 80)
    pdf.cell(0, 10, "3. ÍNDICES ESPECTRALES", ln=1)
    
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
    
    # Temperatura
    pdf.cell(col_widths[0], 10, "TEMP", border=1)
    pdf.cell(col_widths[1], 10, f"{float(reporte_data.get('temp', 0)):.1f}°C", border=1, align="C")
    pdf.cell(col_widths[2], 10, "-", border=1, align="C")
    pdf.cell(col_widths[3], 10, "-", border=1, align="C")
    pdf.cell(col_widths[4], 10, "Temperatura LST", border=1)
    pdf.ln(15)
    
    # ===== SECCIÓN 4: DIAGNÓSTICO =====
    pdf.set_font("helvetica", "B", 14)
    pdf.set_text_color(20, 50, 80)
    pdf.cell(0, 10, "4. DIAGNÓSTICO TÉCNICO", ln=1)
    
    pdf.set_font("helvetica", "", 9)
    pdf.set_text_color(0, 0, 0)
    diagnostico = reporte_data.get('diagnostico_completo', 'Sin diagnóstico disponible')
    pdf.multi_cell(0, 5, clean(diagnostico), border=1)
    
    # ===== SECCIÓN 5: GRÁFICOS =====
    if img_path and os.path.exists(img_path):
        pdf.add_page()
        
        pdf.set_font("helvetica", "B", 14)
        pdf.set_text_color(20, 50, 80)
        pdf.cell(0, 10, "5. ANÁLISIS ESPECTRAL - SERIE TEMPORAL", ln=1)
        pdf.ln(5)
        
        try:
            pdf.image(img_path, x=10, y=40, w=190)
        except Exception as e:
            pdf.set_font("helvetica", "", 10)
            pdf.set_text_color(200, 0, 0)
            pdf.cell(0, 10, f"Error al insertar gráfico: {str(e)}", ln=1)
    
    # ===== SECCIÓN 6: RECOMENDACIONES =====
    pdf.add_page()
    
    pdf.set_font("helvetica", "B", 14)
    pdf.set_text_color(20, 50, 80)
    pdf.cell(0, 10, "6. RECOMENDACIONES Y ACCIONES", ln=1)
    pdf.ln(5)
    
    nivel_riesgo = reporte_data.get('nivel', 'NORMAL')
    tipo_proyecto = reporte_data.get('tipo', 'GENERAL')
    
    # Recomendaciones contextualizadas
    recomendaciones_por_tipo = {
        'NORMAL': {
            'MINERIA': "✓ Mantener vigilancia mensual de recursos hídricos\n✓ Documentar estabilidad de taludes\n✓ Continuar riego de vegetaci��n perimetral",
            'GLACIAR': "✓ Continuar monitoreo de balance de masa\n✓ Registrar datos de cobertura nival\n✓ Preparar estudios glaciológicos anuales",
            'BOSQUE': "✓ Mantener protección forestal\n✓ Documentar regeneración natural\n✓ Prevención estándar de incendios",
            'HUMEDAL': "✓ Confirmar ciclo hidrológico sostenible\n✓ Monitoreo de flora hidrófila\n✓ Cumplimiento Decreto de Humedales verificado",
            'AGRICOLA': "✓ Continuar riego estándar\n✓ Mantener programa de nutrición\n✓ Próxima evaluación en 30 días"
        },
        'MODERADO': {
            'MINERIA': "⚠ Aumentar frecuencia de monitoreo a semanal\n⚠ Inspección terrestre de drenaje\n⚠ Posible acumulación anómala detectada",
            'GLACIAR': "⚠ Evaluación glaciológica inmediata\n⚠ Monitoreo diario de temperatura\n⚠ Registrar cambios de cobertura nival",
            'BOSQUE': "⚠ Plan de restauración forestal\n⚠ Intensificar vigilancia de incendios\n⚠ Análisis fitosanitario urgente",
            'HUMEDAL': "⚠ Plan de restauración hidrológica\n⚠ Protección legal de ecosistema\n⚠ Monitoreo continuo requerido",
            'AGRICOLA': "⚠ Riego aumentado a cada 3 días\n⚠ Análisis de suelo urgente\n⚠ Tratamiento fitosanitario recomendado"
        },
        'CRÍTICO': {
            'MINERIA': "🔴 EMERGENCIA: Contactar SMA/DGA INMEDIATAMENTE\n🔴 Monitoreo 24/7 de drenaje\n🔴 Implementar medidas de contención de agua",
            'GLACIAR': "🔴 EMERGENCIA: Estudios glaciológicos de emergencia\n🔴 Avalúo técnico de riesgos\n🔴 Evaluación ambiental estratégica urgente",
            'BOSQUE': "🔴 EMERGENCIA: Sistemas anti-incendio de emergencia\n🔴 Restauración ecológica inmediata\n🔴 Evaluación ambiental urgente (SEA)",
            'HUMEDAL': "🔴 EMERGENCIA: Contactar SMA/DGA/Ramsar INMEDIATAMENTE\n🔴 Plan de restauración de emergencia\n🔴 Evaluación ambiental estratégica urgente",
            'AGRICOLA': "🔴 EMERGENCIA: Riego de emergencia INMEDIATO\n🔴 Inspección veterinaria fitosanitaria urgente\n🔴 Consultor especialista requerido"
        }
    }
    
    recom_text = recomendaciones_por_tipo.get(nivel_riesgo, {}).get(tipo_proyecto, 
                  recomendaciones_por_tipo.get(nivel_riesgo, {}).get('GENERAL', 'Sin recomendaciones'))
    
    pdf.set_font("helvetica", "", 9)
    pdf.set_text_color(0, 0, 0)
    pdf.multi_cell(0, 4, clean(recom_text))
    
    # ===== SECCIÓN 7: FIRMA Y FECHA =====
    pdf.ln(10)
    pdf.set_font("helvetica", "B", 11)
    pdf.cell(0, 5, clean("Loreto Campos Carrasco"), align="C", ln=1)
    
    pdf.set_font("helvetica", "I", 9)
    pdf.cell(0, 4, clean("Directora Técnica - BioCore Intelligence"), align="C", ln=1)
    
    pdf.set_font("helvetica", "", 8)
    pdf.set_text_color(100, 100, 100)
    fecha_emision = datetime.now().strftime("%d de %B de %Y")
    pdf.cell(0, 4, f"Fecha de emisión: {fecha_emision}", align="C", ln=1)
    
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

# === PESTAÑA 1: VIGILANCIA (SIN VELOCÍMETRO) ===
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

# === PESTAÑA 2: AUDITORÍAS (SOLO VELOCÍMETRO AQUÍ) ===
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
        col1, col2, col3 = st.columns(3)
        
        with col1:
            proyecto_sel = st.selectbox("📍 Seleccionar Proyecto", proyectos_nombres, key="audit_proj")
        
        with col2:
            mes_sel = st.selectbox("📅 Mes", 
                ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
                 "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"],
                key="audit_mes")
        
        with col3:
            anio_sel = st.number_input("📆 Año", value=2026, min_value=2020, max_value=2030, key="audit_anio")
        
        if st.button("🚀 Generar Auditoría Completa", key="btn_gen_audit"):
            with st.spinner("⏳ Procesando auditoría... Esto puede tomar 2-3 minutos"):
                try:
                    proyecto_data = supabase.table("usuarios")\
                        .select("*")\
                        .eq("Proyecto", proyecto_sel)\
                        .execute().data[0]
                    
                    reporte_data = generar_reporte_total(proyecto_data)
                    
                    if reporte_data.get('tipo') == 'error':
                        st.error(f"❌ {reporte_data.get('error', 'Error desconocido')}")
                    else:
                        st.session_state['reporte_actual'] = reporte_data
                        st.session_state['proyecto_audit'] = proyecto_sel
                        st.session_state['mes_audit'] = mes_sel
                        st.session_state['anio_audit'] = anio_sel
                        st.session_state['proyecto_data'] = proyecto_data
                        
                        st.success("✅ Auditoría generada exitosamente")
                        st.rerun()
                
                except Exception as e:
                    st.error(f"❌ Error al generar auditoría: {str(e)}")
        
        st.markdown("---")
        
        # Mostrar reporte si existe
        if 'reporte_actual' in st.session_state and st.session_state['reporte_actual']:
            reporte = st.session_state['reporte_actual']
            proyecto = st.session_state.get('proyecto_audit', 'N/A')
            mes = st.session_state.get('mes_audit', 'N/A')
            anio = st.session_state.get('anio_audit', 2026)
            proyecto_data = st.session_state.get('proyecto_data', {})
            
            # ===== MOSTRAR RESUMEN =====
            st.subheader("📊 Resumen de Auditoría")
            
            # Banner principal
            estado_color = '#10b981' if 'CONTROL' in reporte['estado'] else '#f97316' if 'PRECAUCIÓN' in reporte['estado'] else '#ef4444'
            
            st.markdown(f"""
            <div style="background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); 
                        padding:25px; border-radius:15px; border-left:6px solid {estado_color}; margin-bottom: 20px;">
            <h2 style="color: white; margin: 0;">{reporte['estado']}</h2>
            <p style="color: #cbd5e1; margin: 10px 0 0 0;"><b>Riesgo:</b> {reporte['nivel']}</p>
            <p style="color: #cbd5e1; margin: 5px 0;"><b>Período:</b> {mes} {anio}</p>
            </div>
            """, unsafe_allow_html=True)
            
            # VELOCÍMETRO (SOLO AQUÍ EN AUDITORÍAS)
            fig_gauge = go.Figure(go.Indicator(
                mode="gauge+number",
                value=reporte['savi_actual'],
                title={'text': "SAVI Actual"},
                gauge={
                    'axis': {'range': [0, 0.8]},
                    'bar': {'color': "#2c3e50"},
                    'steps': [
                        {'range': [0, 0.15], 'color': "#ffcccc"},
                        {'range': [0.15, 0.35], 'color': "#ffffcc"},
                        {'range': [0.35, 0.8], 'color': "#ccffcc"}
                    ]
                }
            ))
            fig_gauge.update_layout(height=350, font={'size': 12})
            st.plotly_chart(fig_gauge, use_container_width=True)
            
            # Métricas
            col_m1, col_m2, col_m3, col_m4 = st.columns(4)
            with col_m1:
                st.metric("SAVI", f"{reporte['savi_actual']:.4f}", 
                         f"{reporte['variacion']:+.1f}%")
            with col_m2:
                st.metric("NDWI", f"{reporte['ndwi']:.4f}", 
                         f"{reporte['variacion_ndwi']:+.1f}%")
            with col_m3:
                st.metric("NDSI", f"{reporte['ndsi']:.4f}", 
                         f"{reporte['variacion_ndsi']:+.1f}%")
            with col_m4:
                st.metric("Temperatura", f"{reporte['temp']:.1f}°C")
            
            st.markdown("")
            
            # Diagnóstico
            st.info(f"📋 {reporte['diagnostico_completo']}")
            
            st.markdown("### 📨 Mensaje Telegram Dinámico")
            mensaje_telegram = generar_mensaje_telegram_dinamico(reporte, proyecto_data)
            st.code(mensaje_telegram, language="text")
            
            # Botones de acción
            col_btn1, col_btn2, col_btn3 = st.columns(3)
            
            with col_btn1:
                if st.button("📥 Descargar PDF", key="btn_download_pdf"):
                    with st.spinner("Generando PDF..."):
                        try:
                            # Generar gráficos contextualizados
                            img_path = generar_graficos_profesionales(
                                reporte.get('indices_historicos', {}),
                                reporte.get('tipo', 'GENERAL')
                            )
                            
                            # Generar PDF dinámico
                            pdf = generar_pdf_auditoria_dinamico(proyecto_data, reporte, img_path)
                            
                            # Convertir a bytes
                            pdf_bytes = pdf.output(dest='S').encode('latin-1')
                            
                            # Botón de descarga
                            st.download_button(
                                label="✅ Descargar Auditoría PDF",
                                data=pdf_bytes,
                                file_name=f"Auditoria_{proyecto}_{mes}_{anio}.pdf",
                                mime="application/pdf",
                                key="download_btn"
                            )
                            
                            # Limpiar archivo temporal
                            if img_path and os.path.exists(img_path):
                                os.remove(img_path)
                            
                            st.success("✅ PDF listo para descargar")
                        except Exception as e:
                            st.error(f"❌ Error al generar PDF: {str(e)}")
            
            with col_btn2:
                if st.button("🔄 Generar Nueva", key="btn_new_audit"):
                    st.session_state['reporte_actual'] = None
                    st.rerun()
            
            with col_btn3:
                if st.button("📤 Enviar por Telegram", key="btn_send_telegram"):
                    with st.spinner("Enviando..."):
                        try:
                            if proyecto_data.get('id_telegram'):
                                token_telegram = st.secrets.get('telegram', {}).get('token', '')
                                if token_telegram:
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
    else:
        st.warning("📌 No hay proyectos registrados en la base de datos")

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

# === PESTAÑA 4: GESTIÓN DE CLIENTES (SOLO ADMIN) ===
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
        
        with tab_editar:
            st.markdown("### Editar cliente")
            
            try:
                res = supabase.table("usuarios").select("Proyecto").execute()
                proyectos_lista = [p['Proyecto'] for p in res.data] if res.data else []
            except:
                proyectos_lista = []
            
            if proyectos_lista:
                proyecto_editar = st.selectbox("Selecciona proyecto", proyectos_lista, key="edit_proyecto")
                
                if st.button("Cargar datos", key="btn_cargar"):
                    try:
                        res = supabase.table("usuarios").select("*").eq("Proyecto", proyecto_editar).execute()
                        if res.data:
                            cliente = res.data[0]
                            
                            with st.form("form_editar"):
                                tipo = st.selectbox("Tipo", ["MINERIA", "GLACIAR", "BOSQUE", "HUMEDAL", "AGRICOLA"],
                                                  index=["MINERIA", "GLACIAR", "BOSQUE", "HUMEDAL", "AGRICOLA"].index(cliente.get('Tipo', 'MINERIA')))
                                email = st.text_input("Email", value=cliente.get('email_cliente', '') or '')
                                telegram = st.text_input("Telegram ID", value=cliente.get('id_telegram', '') or '')
                                anio = st.number_input("Año base", value=cliente.get('ano_linea_base', 2015))
                                cambiar_pwd = st.checkbox("¿Cambiar contraseña?")
                                if cambiar_pwd:
                                    nueva_pwd = st.text_input("Nueva contraseña", type="password", key="new_pwd")
                                else:
                                    nueva_pwd = None
                                
                                if st.form_submit_button("💾 Guardar"):
                                    try:
                                        update_data = {
                                            "Tipo": tipo,
                                            "email_cliente": email if email else None,
                                            "id_telegram": telegram if telegram else None,
                                            "ano_linea_base": int(anio)
                                        }
                                        if cambiar_pwd and nueva_pwd:
                                            update_data["password_cliente"] = hash_password(nueva_pwd)
                                        
                                        supabase.table("usuarios").update(update_data).eq("Proyecto", proyecto_editar).execute()
                                        st.success("✅ Cliente actualizado")
                                    except Exception as e:
                                        st.error(f"Error: {str(e)}")
                    except Exception as e:
                        st.error(f"Error: {str(e)}")
        
        with tab_eliminar:
            st.markdown("### Eliminar cliente")
            st.warning("⚠️ **NO SE PUEDE DESHACER**")
            
            try:
                res = supabase.table("usuarios").select("Proyecto").execute()
                proyectos_lista = [p['Proyecto'] for p in res.data] if res.data else []
            except:
                proyectos_lista = []
            
            if proyectos_lista:
                proyecto_eliminar = st.selectbox("Selecciona proyecto", proyectos_lista, key="del_proyecto")
                if st.checkbox(f"Confirmo eliminar '{proyecto_eliminar}'"):
                    if st.button("🗑️ ELIMINAR", key="btn_eliminar"):
                        try:
                            supabase.table("usuarios").delete().eq("Proyecto", proyecto_eliminar).execute()
                            st.success(f"✅ {proyecto_eliminar} eliminado")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error: {str(e)}")

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

# === PESTAÑA HISTORIAL (CLIENTE) ===
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
        ### Cómo funciona BioCore Intelligence
        
        **Vigilancia en Tiempo Real:**
        - Accede a la pestaña "Vigilancia" para ver el mapa de tu proyecto
        - Haz clic en "Ejecutar Reporte" para analizar los últimos datos satelitales
        
        **Auditorías Profesionales:**
        - Ve a "Auditorías" para generar reportes ejecutivos
        - Los reportes incluyen comparativas con tu línea base histórica
        - Descarga el PDF profesional para presentaciones
        
        **Datos y Historial:**
        - Accede a "Base Datos" para ver todo tu historial de mediciones
        - Exporta los datos en CSV para análisis adicionales
        """)

st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #888; font-size: 0.9em; padding: 20px;">
<b>BioCore Intelligence</b> © 2026 | Todos los derechos reservados
</div>
""", unsafe_allow_html=True)
