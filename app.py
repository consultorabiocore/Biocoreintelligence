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
from io import BytesIO

# --- 1. CONFIGURACIÓN ---
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
    return text.encode('latin-1', errors='replace').decode('latin-1')

# === SISTEMA DE AUTENTICACIÓN ===
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

# === FUNCIÓN DE MAPA ---
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

# === GENERADOR DE GRÁFICOS ---
def generar_graficos(df):
    try:
        fig, axes = plt.subplots(4, 1, figsize=(12, 14))
        fig.patch.set_facecolor('white')
        
        config = [
            ('ndsi', '#2E86AB', 'ÁREA DE NIEVE/HIELO (NDSI)'),
            ('ndwi', '#A23B72', 'RECURSOS HÍDRICOS (NDWI)'),
            ('swir', '#F18F01', 'ESTABILIDAD DE SUSTRATO (SWIR)'),
            ('polvo', '#C73E1D', 'DEPÓSITO DE MATERIAL PARTICULADO')
        ]
        
        for i, (col, color, titulo) in enumerate(config):
            try:
                if col in df.columns:
                    df_clean = pd.to_numeric(df[col], errors='coerce').dropna()
                    
                    if not df_clean.empty:
                        axes[i].plot(df_clean.index, df_clean.values, 
                                   color=color, marker='o', linewidth=2.5, markersize=6)
                    else:
                        axes[i].text(0.5, 0.5, 'SIN DATOS', ha='center', va='center', 
                                   color='gray', fontsize=12)
            except:
                pass
            
            axes[i].set_title(titulo, fontweight='bold', fontsize=12, color='#1a1a1a')
            axes[i].grid(True, alpha=0.3, linestyle='--')
            axes[i].set_facecolor('#f9f9f9')
            axes[i].tick_params(colors='#1a1a1a', labelsize=10)
        
        plt.tight_layout(pad=3.0)
        
        temp_dir = tempfile.gettempdir()
        img_path = os.path.join(temp_dir, 'grafico_biocore.png')
        plt.savefig(img_path, format='png', dpi=300, bbox_inches='tight', facecolor='white')
        plt.close()
        
        return img_path
    except Exception as e:
        st.error(f"Error en gráficos: {e}")
        return None

# === GENERADOR DE REPORTE ---
def generar_reporte_total(p):
    try:
        raw_coords = p.get('Coordenadas')
        if raw_coords is None:
            return {'error': 'Coordenadas vacías', 'tipo': 'error'}

        if isinstance(raw_coords, str):
            raw_coords = json.loads(raw_coords)

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

    # EVALUACIÓN
    tipo = p.get('Tipo', 'MINERIA')
    variacion = ((savi_now - savi_base) / abs(savi_base if savi_base != 0 else 0.001)) * 100 if savi_base != 0 else 0

    if abs(savi_now) < 0.05 and abs(savi_base) < 0.05:
        estado = "🟢 BAJO CONTROL"
        nivel = "NORMAL"
        color_estado = (40, 150, 80)
    elif variacion < -15:
        estado = "🔴 ALERTA CRÍTICA"
        nivel = "CRÍTICO"
        color_estado = (220, 50, 50)
    else:
        estado = "🟡 PRECAUCIÓN"
        nivel = "MODERADO"
        color_estado = (200, 100, 0)

    texto_telegram = f"""
╔════════════════════════════════════════╗
║  🛰️ REPORTE BIOCORE {tipo.upper():26s}║
║  {p['Proyecto']:40s}║
╚════════════════════════════════════════╝

📅 Análisis: {f_rep}
🎯 {estado}
💡 SAVI: {savi_now:.4f} | Base: {savi_base:.4f}
📊 Variación: {variacion:.1f}%
🌡️ Temperatura: {temp_val:.1f}°C

Riesgo: {nivel}
    """

    return {
        'estado': estado,
        'diagnostico': f"Análisis completado. Estado: {estado}",
        'nivel': nivel,
        'tipo_terreno': 'ANÁLISIS',
        'savi_actual': savi_now,
        'savi_base': savi_base,
        'ndsi': ndsi_now,
        'ndwi': ndwi_now,
        'swir': swir_now,
        'temp': temp_val,
        'fecha': f_rep,
        'anio_base': anio_base,
        'tipo': tipo,
        'proyecto': p['Proyecto'],
        'texto_telegram': texto_telegram,
        'variacion': variacion,
        'color_estado': color_estado
    }

# === GENERADOR PDF PROFESIONAL ===
def generar_pdf_profesional(proyecto_nombre, tipo_proyecto, reporte_data, img_path):
    """Genera PDF profesional"""
    
    pdf = FPDF()
    pdf.add_page()
    
    # ENCABEZADO
    pdf.set_fill_color(20, 50, 80)
    pdf.rect(0, 0, 210, 50, 'F')
    
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("helvetica", "B", 18)
    pdf.set_xy(10, 15)
    pdf.cell(0, 10, clean("AUDITORÍA DE CUMPLIMIENTO AMBIENTAL"), ln=1)
    
    pdf.set_font("helvetica", "", 12)
    pdf.set_xy(10, 27)
    pdf.cell(0, 8, clean(f"PROYECTO: {proyecto_nombre.upper()}"), ln=1)
    
    pdf.set_font("helvetica", "I", 10)
    pdf.set_xy(10, 37)
    pdf.cell(0, 6, clean("Responsable Técnica: Loreto Campos Carrasco | BioCore Intelligence"), ln=1)
    
    # SECCIÓN DE DIAGNÓSTICO
    pdf.set_y(55)
    pdf.set_font("helvetica", "B", 12)
    pdf.set_text_color(40, 40, 40)
    pdf.cell(0, 8, clean("DIAGNÓSTICO TÉCNICO"), ln=1)
    
    # BANNER DE ESTADO
    color_r, color_g, color_b = reporte_data['color_estado']
    pdf.set_fill_color(color_r, color_g, color_b)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("helvetica", "B", 12)
    pdf.set_y(65)
    pdf.cell(0, 10, clean(f"ESTATUS: {reporte_data['estado']}"), ln=1, fill=True)
    
    # CONTENIDO DEL DIAGNÓSTICO
    pdf.set_y(78)
    pdf.set_text_color(40, 40, 40)
    pdf.set_font("helvetica", "", 10)
    
    diagnostico_text = f"""1. ESTADO GENERAL: El índice SAVI actual ({reporte_data['savi_actual']:.4f}) presenta una variación de {reporte_data['variacion']:.1f}% respecto a la línea base de {reporte_data['anio_base']}.

2. ANÁLISIS TÉCNICO: 
• NDSI (Nieve/Hielo): {reporte_data['ndsi']:.4f}
• NDWI (Recursos Hídricos): {reporte_data['ndwi']:.4f}
• SWIR (Estabilidad Sustrato): {reporte_data['swir']:.4f}
• Temperatura: {reporte_data['temp']:.1f}°C

3. NIVEL DE RIESGO: {reporte_data['nivel']}

4. RECOMENDACIÓN: {"Mantener vigilancia programada" if reporte_data['nivel'] == "NORMAL" else "Evaluación técnica inmediata requerida"}"""
    
    pdf.multi_cell(0, 5, clean(diagnostico_text), border=1)
    
    # GRÁFICOS
    if img_path and os.path.exists(img_path):
        pdf.add_page()
        pdf.set_font("helvetica", "B", 14)
        pdf.set_text_color(20, 50, 80)
        pdf.cell(0, 10, clean("ANÁLISIS ESPECTRAL HISTÓRICO"), ln=1)
        pdf.set_y(20)
        try:
            pdf.image(img_path, x=10, y=25, w=190)
        except Exception as e:
            pdf.set_text_color(200, 0, 0)
            pdf.cell(0, 10, clean(f"Error al insertar gráfico: {str(e)}"), ln=1)
    
    # FIRMA
    pdf.set_y(260)
    pdf.set_text_color(40, 40, 40)
    pdf.set_font("helvetica", "B", 10)
    pdf.cell(0, 5, clean("Loreto Campos Carrasco"), align="C", ln=1)
    pdf.set_font("helvetica", "I", 9)
    pdf.cell(0, 5, clean("Directora Técnica - BioCore Intelligence"), align="C", ln=1)
    pdf.cell(0, 5, clean(f"Fecha: {reporte_data['fecha']}"), align="C", ln=1)
    
    return pdf

# === INICIALIZAR SESSION STATE ===
if 'authenticated' not in st.session_state:
    st.session_state['authenticated'] = False
    st.session_state['admin_mode'] = False
    st.session_state['proyecto_cliente'] = None
    st.session_state['preview_pdf'] = None
    st.session_state['mostrar_preview'] = False

# === SIDEBAR ===
with st.sidebar:
    # LOGO
    if os.path.exists("logo_biocore.png"):
        st.image("logo_biocore.png", width=200)
    
    st.markdown("---")
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
                    st.error("❌ Contraseña de admin incorrecta")
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
                    st.error("❌ Proyecto o contraseña inválidos")
    
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
            st.session_state['preview_pdf'] = None
            st.session_state['mostrar_preview'] = False
            st.rerun()

# === PANTALLA DE BIENVENIDA PARA NO AUTENTICADOS ===
if not st.session_state.get('authenticated'):
    # Logo y Título
    col_logo = st.columns(1)[0]
    with col_logo:
        if os.path.exists("logo_biocore.png"):
            st.image("logo_biocore.png", width=250)
    
    st.markdown("""
    <h1 style="text-align: center; margin-top: 30px;">BioCore Intelligence</h1>
    <p style="text-align: center; font-size: 1.1em; color: #888;">Sistema de Vigilancia Ambiental Satelital</p>
    """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Mostrar mapa de demostración
    try:
        proyectos = supabase.table("usuarios").select("*").execute().data
        if proyectos:
            st.subheader("📍 Proyectos Activos")
            
            cols = st.columns(min(len(proyectos), 2))
            for idx, p in enumerate(proyectos[:6]):
                with cols[idx % 2]:
                    st.markdown(f"""
                    <div style="background-color: #1e293b; padding: 15px; border-radius: 10px; margin-bottom: 20px;">
                    <b>📌 {p['Proyecto']}</b><br>
                    Tipo: {p.get('Tipo', 'N/A')}<br>
                    Titular: {p.get('titular', 'N/A')}
                    </div>
                    """, unsafe_allow_html=True)
                    
                    m_obj = dibujar_mapa_biocore(p['Coordenadas'])
                    folium_static(m_obj, width=350, height=300)
    except:
        pass
    
    st.markdown("---")
    
    # Footer
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
    tab1, tab_informe, tab_excel, tab_config, tab_soporte, tab_guia = st.tabs([
        "🛰️ Vigilancia", 
        "📋 Auditorías", 
        "📊 Base Datos", 
        "⚙️ Configuración", 
        "💬 Soporte", 
        "📖 Guía"
    ])
else:
    tab1, tab_informe, tab_excel, tab_soporte, tab_config, tab_historial, tab_guia = st.tabs([
        "🛰️ Vigilancia", 
        "📋 Auditorías", 
        "📊 Base Datos", 
        "💬 Soporte",
        "⚙️ Configuración",
        "📨 Mi Historial",
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
        for p in proyectos_mostrar:
            st.markdown(f"### 📍 {p['Proyecto']}")

            col_mapa, col_reporte = st.columns([2.5, 1])

            with col_mapa:
                m_obj = dibujar_mapa_biocore(p['Coordenadas'])
                folium_static(m_obj, width=850, height=500)

            with col_reporte:
                if st.button("🚀 Ejecutar Reporte", key=f"btn_{p['Proyecto']}"):
                    with st.spinner("Analizando..."):
                        reporte = generar_reporte_total(p)
                        
                        if reporte.get('tipo') != 'error':
                            # === VELOCÍMETRO ACTUALIZADO (0 a 0.25) ===
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
                                    ],
                                    'threshold': {
                                        'line': {'color': "white", 'width': 3},
                                        'value': reporte['savi_base']
                                    }
                                }
                            ))
                            fig.update_layout(
                                height=350,
                                font={'size': 12}
                            )
                            st.plotly_chart(fig, use_container_width=True)

                            # EXPLICACIÓN
                            st.markdown(f"""
                            <div style="background-color:#1e293b; padding:15px; border-radius:10px; border-left:4px solid #60a5fa;">
                            <b>📊 Interpretación:</b><br>
                            Valor SAVI: <b>{reporte['savi_actual']:.4f}</b><br>
                            Base ({reporte['anio_base']}): <b>{reporte['savi_base']:.4f}</b><br>
                            Variación: <b>{reporte['variacion']:.1f}%</b><br>
                            Estado: <b>{reporte['nivel']}</b>
                            </div>
                            """, unsafe_allow_html=True)

                            col_a, col_b = st.columns(2)
                            with col_a:
                                st.metric(label="SAVI", value=f"{reporte['savi_actual']:.4f}")
                            with col_b:
                                st.metric(label="Temp", value=f"{reporte['temp']:.1f}°C")
                            
                            st.success(reporte['estado'])

# === PESTAÑA 2: AUDITORÍAS ===
# === PESTAÑA 2: AUDITORÍAS ===
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
        
        if st.button("📊 Generar Auditoría"):
            with st.spinner("Procesando auditoría..."):
                try:
                    p = supabase.table("usuarios").select("*").eq("Proyecto", proyecto).execute().data[0]
                    reporte = generar_reporte_total(p)
                    
                    st.session_state['reporte_actual'] = reporte
                    st.session_state['proyecto_reporte'] = proyecto
                    st.session_state['mes_reporte'] = mes
                    st.session_state['anio_reporte'] = anio
                    st.session_state['p_data'] = p
                    
                except Exception as e:
                    st.error(f"Error: {str(e)}")
        
        # Mostrar reporte si existe
        if st.session_state.get('reporte_actual'):
            reporte = st.session_state['reporte_actual']
            proyecto = st.session_state['proyecto_reporte']
            mes = st.session_state['mes_reporte']
            anio = st.session_state['anio_reporte']
            p_data = st.session_state.get('p_data', {})
            
            st.success("✅ Auditoría generada")
            
            st.subheader("📊 Vista Previa del Reporte")
            
            # Detalles principales
            st.markdown(f"""
            <div style="background-color:#1e293b; padding:20px; border-radius:10px; border-left:5px solid #60a5fa;">
            <h3>🎯 Estado: {reporte['estado']}</h3>
            <p><b>Nivel de Riesgo:</b> {reporte['nivel']}</p>
            <p><b>Proyecto:</b> {proyecto}</p>
            <p><b>Período:</b> {mes} {anio}</p>
            </div>
            """, unsafe_allow_html=True)
            
            # Métricas en columnas
            col_m1, col_m2, col_m3 = st.columns(3)
            with col_m1:
                st.metric("SAVI Actual", f"{reporte['savi_actual']:.4f}")
            with col_m2:
                st.metric("Temperatura", f"{reporte['temp']:.1f}°C")
            with col_m3:
                st.metric("Variación", f"{reporte['variacion']:.1f}%")
            
            # Datos técnicos
            st.markdown("### 📊 Datos Técnicos")
            col_t1, col_t2, col_t3, col_t4 = st.columns(4)
            with col_t1:
                st.info(f"**SAVI Base**\n{reporte['savi_base']:.4f}")
            with col_t2:
                st.info(f"**NDSI**\n{reporte['ndsi']:.4f}")
            with col_t3:
                st.info(f"**NDWI**\n{reporte['ndwi']:.4f}")
            with col_t4:
                st.info(f"**SWIR**\n{reporte['swir']:.4f}")
            
            st.markdown("---")
            
            # Mensaje Telegram
            st.markdown("### 📨 Mensaje Telegram a Enviar:")
            st.code(reporte['texto_telegram'])
            
            st.markdown("---")
            
            # Botones de acción
            col_acc1, col_acc2, col_acc3 = st.columns(3)
            
            with col_acc1:
                if st.button("📥 Generar PDF"):
                    with st.spinner("Generando PDF..."):
                        try:
                            pdf = generar_pdf_profesional(proyecto, proyectos_dict.get(proyecto, 'MINERIA'), reporte, None)
                            
                            temp_dir = tempfile.gettempdir()
                            pdf_path = os.path.join(temp_dir, f"Auditoria_{proyecto}_{mes}_{anio}.pdf")
                            pdf.output(pdf_path)
                            
                            with open(pdf_path, "rb") as f:
                                st.download_button(
                                    label="📥 Descargar PDF",
                                    data=f.read(),
                                    file_name=f"Auditoria_{proyecto}_{mes}_{anio}.pdf",
                                    mime="application/pdf",
                                    key="download_pdf"
                                )
                            st.success("✅ PDF generado")
                        except Exception as e:
                            st.error(f"Error: {str(e)}")
            
            with col_acc2:
                if st.session_state.get('admin_mode'):
                    if st.button("📤 Enviar a Cliente"):
                        try:
                            pdf = generar_pdf_profesional(proyecto, proyectos_dict.get(proyecto, 'MINERIA'), reporte, None)
                            
                            temp_dir = tempfile.gettempdir()
                            pdf_path = os.path.join(temp_dir, f"Auditoria_{proyecto}_{mes}_{anio}.pdf")
                            pdf.output(pdf_path)
                            
                            with open(pdf_path, "rb") as f:
                                files = {'document': (f"auditoria.pdf", f.read())}
                                response = requests.post(
                                    f"https://api.telegram.org/bot{st.secrets['telegram']['token']}/sendDocument",
                                    data={
                                        "chat_id": p_data.get('telegram_id'),
                                        "caption": f"📊 Auditoría {proyecto} - {mes} {anio}\n\n{reporte['estado']}"
                                    },
                                    files=files,
                                    timeout=30
                                )
                                if response.status_code == 200:
                                    st.success("✅ Reporte enviado al cliente")
                                else:
                                    st.error(f"Error: {response.text}")
                        except Exception as e:
                            st.error(f"Error: {str(e)}")
            
            with col_acc3:
                if st.button("🗑️ Limpiar"):
                    st.session_state['reporte_actual'] = None
                    st.session_state['mostrar_preview'] = False
                    st.rerun()
# === PESTAÑA 3: EXCEL ===
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

# === PESTAÑA CONFIGURACIÓN ===
with tab_config:
    st.title("⚙️ Configuración")
    
    if st.session_state.get('admin_mode'):
        # VISTA ADMIN
        tab_clientes, tab_gestor = st.tabs(["👥 Clientes", "📊 Gestor"])
        
        with tab_clientes:
            st.subheader("📋 Clientes Registrados")
            
            try:
                res = supabase.table("usuarios").select("*").execute()
                if res.data:
                    for idx, cliente in enumerate(res.data):
                        col1, col2, col3, col4, col5, col6 = st.columns([1.8, 1.8, 1.2, 1.2, 1, 0.8])
                        with col1:
                            st.write(f"🏢 {cliente.get('Proyecto', 'N/A')}")
                        with col2:
                            st.write(f"👤 {cliente.get('titular', 'N/A')}")
                        with col3:
                            st.write(f"📌 {cliente.get('Tipo', 'N/A')}")
                        with col4:
                            telegram_id = cliente.get('telegram_id', 'N/A')
                            if isinstance(telegram_id, str) and len(telegram_id) > 10:
                                st.write(f"📱 {telegram_id[:10]}...")
                            else:
                                st.write(f"📱 {telegram_id}")
                        with col5:
                            freq = cliente.get('frecuencia_reportes', 'N/A')
                            st.write(f"📅 {freq}")
                        with col6:
                            if st.button("✏️", key=f"edit_{idx}"):
                                st.session_state[f"edit_cliente_{idx}"] = True
                    
                    st.divider()
                    
                    # MOSTRAR FORMULARIO DE EDICIÓN SI ESTÁ ACTIVADO
                    for idx, cliente in enumerate(res.data):
                        if st.session_state.get(f"edit_cliente_{idx}"):
                            st.subheader(f"✏️ Editando: {cliente['Proyecto']}")
                            
                            with st.form(f"edit_form_{idx}"):
                                col1, col2 = st.columns(2)
                                
                                with col1:
                                    titular = st.text_input("Titular", value=cliente.get('titular', ''))
                                    tipo = st.selectbox("Tipo", ["MINERIA", "GLACIAR", "BOSQUE", "HUMEDAL", "AGRICOLA"], 
                                                       index=["MINERIA", "GLACIAR", "BOSQUE", "HUMEDAL", "AGRICOLA"].index(cliente.get('Tipo', 'MINERIA')), key=f"tipo_{idx}")
                                    telegram_id = st.text_input("Telegram ID", value=str(cliente.get('telegram_id', '')))
                                
                                with col2:
                                    anio_lb = st.number_input("Año Base", value=int(cliente.get('anio_linea_base', 2017)), min_value=2010, max_value=2026, key=f"anio_{idx}")
                                    frecuencia = st.selectbox("Frecuencia de Reportes", ["Diaria", "Semanal"], 
                                                             index=0 if cliente.get('frecuencia_reportes', 'Diaria') == 'Diaria' else 1, key=f"freq_{idx}")
                                    hora_actual = cliente.get('hora_envio', '08:00')
                                    if isinstance(hora_actual, str):
                                        hora_obj = datetime.strptime(hora_actual, '%H:%M').time()
                                    else:
                                        hora_obj = time(8, 0)
                                    hora_envio = st.time_input("⏰ Hora de Envío", value=hora_obj, key=f"hora_{idx}")
                                
                                col_act1, col_act2 = st.columns(2)
                                with col_act1:
                                    if st.form_submit_button("💾 Guardar Cambios", key=f"save_{idx}"):
                                        try:
                                            cliente_update = {
                                                "Proyecto": cliente.get('Proyecto'),
                                                "titular": titular,
                                                "Tipo": tipo,
                                                "telegram_id": telegram_id,
                                                "anio_linea_base": int(anio_lb),
                                                "frecuencia_reportes": frecuencia,
                                                "hora_envio": hora_envio.strftime("%H:%M")
                                            }
                                            supabase.table("usuarios").upsert(cliente_update).execute()
                                            st.success("✅ Cambios guardados")
                                            st.session_state[f"edit_cliente_{idx}"] = False
                                            st.rerun()
                                        except Exception as e:
                                            st.error(f"Error: {str(e)}")
                                
                                with col_act2:
                                    if st.form_submit_button("❌ Cancelar", key=f"cancel_{idx}"):
                                        st.session_state[f"edit_cliente_{idx}"] = False
                                        st.rerun()
            
            except Exception as e:
                st.error(f"Error: {e}")
            
            st.divider()
            st.markdown("### ➕ Nuevo Cliente")
            
            with st.form("form_nuevo_cliente", clear_on_submit=True):
                col1, col2 = st.columns(2)
                
                with col1:
                    titular = st.text_input("Titular")
                    nombre_proyecto = st.text_input("Proyecto")
                    tipo = st.selectbox("Tipo", ["MINERIA", "GLACIAR", "BOSQUE", "HUMEDAL", "AGRICOLA"])
                    anio_lb = st.number_input("Año Base", value=2017, min_value=2010, max_value=2026)
                
                with col2:
                    telegram_id = st.text_input("Telegram ID")
                    password_cliente = st.text_input("Contraseña", type="password")
                    password_confirm = st.text_input("Confirmar", type="password")
                    coords_json = st.text_area("Coordenadas (JSON)", height=80)
                
                col_freq1, col_freq2 = st.columns(2)
                with col_freq1:
                    frecuencia = st.selectbox("Frecuencia de Reportes", ["Diaria", "Semanal"], key="new_freq")
                
                with col_freq2:
                    hora_envio = st.time_input("⏰ Hora de Envío", value=time(8, 0), key="new_hora")
                
                if st.form_submit_button("💾 Guardar"):
                    errores = []
                    
                    if not titular or not nombre_proyecto:
                        errores.append("Titular y Proyecto requeridos")
                    if password_cliente != password_confirm:
                        errores.append("Las contraseñas no coinciden")
                    
                    if errores:
                        for error in errores:
                            st.error(error)
                    else:
                        try:
                            nuevo_cliente = {
                                "titular": titular,
                                "Proyecto": nombre_proyecto,
                                "Tipo": tipo,
                                "anio_linea_base": int(anio_lb),
                                "telegram_id": telegram_id,
                                "Coordenadas": coords_json,
                                "frecuencia_reportes": frecuencia,
                                "hora_envio": hora_envio.strftime("%H:%M"),
                                "password_cliente": hash_password(password_cliente) if password_cliente else ""
                            }
                            supabase.table("usuarios").upsert(nuevo_cliente).execute()
                            st.success(f"✅ {nombre_proyecto} guardado")
                            st.balloons()
                        except Exception as e:
                            st.error(f"Error: {str(e)}")
        
        with tab_gestor:
            st.info("📊 Gestión del sistema")
    
    else:
        # VISTA CLIENTE
        st.subheader(f"Mis Configuraciones - {st.session_state.get('proyecto_cliente')}")
        
        cliente_data = st.session_state.get('cliente_data', {})
        
        with st.form("form_config_cliente"):
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("### 📅 Frecuencia de Reportes")
                frecuencia = st.radio("Selecciona con qué frecuencia deseas recibir reportes:",
                                     ["Diaria", "Semanal"],
                                     index=0 if cliente_data.get('frecuencia_reportes', 'Diaria') == 'Diaria' else 1)
            
            with col2:
                st.markdown("### ⏰ Hora de Envío")
                hora_actual = cliente_data.get('hora_envio', '08:00')
                if isinstance(hora_actual, str):
                    hora_obj = datetime.strptime(hora_actual, '%H:%M').time()
                else:
                    hora_obj = time(8, 0)
                hora_envio = st.time_input("¿A qué hora deseas recibir los reportes?", value=hora_obj)
            
            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                if st.form_submit_button("💾 Guardar Configuración"):
                    try:
                        proyecto = st.session_state.get('proyecto_cliente')
                        update_data = {
                            "Proyecto": proyecto,
                            "frecuencia_reportes": frecuencia,
                            "hora_envio": hora_envio.strftime("%H:%M")
                        }
                        supabase.table("usuarios").upsert(update_data).execute()
                        st.success("✅ Configuración guardada")
                        st.session_state['cliente_data'] = {**cliente_data, 
                                                           "frecuencia_reportes": frecuencia,
                                                           "hora_envio": hora_envio.strftime("%H:%M")}
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error al guardar: {str(e)}")

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
        
        st.subheader("🔧 Problemas Comunes")
        with st.expander("❓ ¿Cómo genero un reporte?"):
            st.write("""
1. Ve a la pestaña **'Vigilancia'**
2. Haz click en **'Ejecutar Reporte'**
3. Espera el análisis satelital (2-3 minutos)
4. Visualiza el velocímetro y métricas
            """)
    
    with col2:
        st.subheader("📚 Documentación")
        st.markdown("""
        ### Recursos Disponibles
        - 📖 Manual del Usuario
        - 🔬 Protocolo Técnico
        - ❓ Preguntas Frecuentes
        """)
        
        st.subheader("🐛 Reportar Problema")
        with st.form("form_soporte"):
            nombre_reporte = st.text_input("Tu nombre")
            email_reporte = st.text_input("Tu email")
            problema = st.text_area("Describe el problema", height=100)
            
            if st.form_submit_button("📬 Enviar Reporte"):
                st.success("✅ Reporte enviado a consultorabiocore@gmail.com")
                st.balloons()

# === PESTAÑA MI HISTORIAL (Solo Cliente) ===
if not st.session_state.get('admin_mode'):
    with tab_historial:
        st.title("📨 Mi Historial de Reportes")
        
        proyecto_cliente = st.session_state.get('proyecto_cliente')
        st.subheader(f"Reportes enviados a {proyecto_cliente}")
        
        try:
            res = supabase.table("historial_reportes").select("*").eq("proyecto", proyecto_cliente).order("created_at", desc=True).execute()
            
            if res.data:
                for idx, reporte in enumerate(res.data):
                    with st.expander(f"📊 {reporte.get('created_at', 'N/A')[:10]} - {reporte.get('proyecto', 'N/A')}"):
                        col_info1, col_info2 = st.columns(2)
                        with col_info1:
                            st.write(f"**SAVI:** {reporte.get('savi', 'N/A')}")
                            st.write(f"**NDSI:** {reporte.get('ndsi', 'N/A')}")
                        with col_info2:
                            st.write(f"**NDWI:** {reporte.get('ndwi', 'N/A')}")
                            st.write(f"**SWIR:** {reporte.get('swir', 'N/A')}")
                        
                        st.write(f"**Estado:** {reporte.get('estado', 'N/A')}")
            else:
                st.info("No hay reportes aún")
        except Exception as e:
            st.error(f"Error: {e}")

# === PESTAÑA GUÍA ===
with tab_guia:
    st.title("📖 Guía Completa del Sistema BioCore Intelligence")
    
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
        """)
    
    with tab_indices:
        st.markdown("""
        ## 📊 Índices Espectrales
        
        ### 🌱 SAVI
        Mide el vigor de la cobertura vegetal
        
        ### ❄️ NDSI
        Detecta presencia de nieve e hielo
        
        ### 💧 NDWI
        Indica presencia de agua y humedad
        """)
    
    with tab_faq:
        st.markdown("""
        ## ❓ Preguntas Frecuentes
        
        **¿Con qué frecuencia recibo reportes?**
        > Según tu configuración: Diaria o Semanal
        
        **¿A qué hora me llegan?**
        > A la hora que especificaste en tu registro
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
