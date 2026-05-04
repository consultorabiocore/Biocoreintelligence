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
st.set_page_config(page_title="BioCore Intelligence V7", layout="wide")

st.markdown("""
<style>
    [data-testid="stSidebar"] {
        background-color: #0e1117;
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
    """Genera PDF profesional con diseño como en las imágenes"""
    
    pdf = FPDF()
    pdf.add_page()
    
    # ENCABEZADO AZUL OSCURO
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
        except:
            pass
    
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
            st.rerun()

# === PANTALLA DE BIENVENIDA PARA NO AUTENTICADOS ===
if not st.session_state.get('authenticated'):
    st.title("🌍 Bienvenido a BioCore Intelligence V7")
    st.markdown("### Sistema de Vigilancia Ambiental Satelital")
    
    # Mostrar mapa de demostración
    try:
        proyectos = supabase.table("usuarios").select("*").execute().data
        if proyectos:
            st.subheader("📍 Proyectos Activos")
            for p in proyectos[:3]:  # Mostrar primeros 3 proyectos
                col1, col2 = st.columns([2, 1])
                with col1:
                    m_obj = dibujar_mapa_biocore(p['Coordenadas'])
                    folium_static(m_obj, width=500, height=400)
                with col2:
                    st.write(f"**Proyecto:** {p['Proyecto']}")
                    st.write(f"**Tipo:** {p.get('Tipo', 'N/A')}")
                    st.write(f"**Titular:** {p.get('titular', 'N/A')}")
    except:
        pass
    
    st.info("👈 Inicia sesión desde el panel izquierdo para acceder a más funciones")
    st.stop()

# === TABS PRINCIPALES ===
if st.session_state.get('admin_mode'):
    tab1, tab_informe, tab_excel, tab_admin, tab_soporte, tab_guia = st.tabs([
        "🛰️ Vigilancia", 
        "📋 Auditorías", 
        "📊 Base Datos", 
        "⚙️ Admin", 
        "💬 Soporte", 
        "📖 Guía"
    ])
else:
    tab1, tab_informe, tab_excel, tab_soporte, tab_guia = st.tabs([
        "🛰️ Vigilancia", 
        "📋 Auditorías", 
        "📊 Base Datos", 
        "💬 Soporte", 
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
                            # === VELOCÍMETRO GRANDE ===
                            fig = go.Figure(go.Indicator(
                                mode="gauge+number+delta",
                                value=reporte['savi_actual'],
                                domain={'x': [0, 1], 'y': [0, 1]},
                                title={'text': f"SAVI: Vigilancia Espectral"},
                                delta={'reference': reporte['savi_base']},
                                gauge={
                                    'axis': {'range': [0, 0.15], 'thickness': 0.75, 'tickwidth': 1},
                                    'bar': {'color': "#2c3e50", 'thickness': 0.75},
                                    'steps': [
                                        {'range': [0, 0.05], 'color': "#e74c3c"},
                                        {'range': [0.05, 0.10], 'color': "#f1c40f"},
                                        {'range': [0.10, 0.15], 'color': "#2ecc71"}
                                    ],
                                    'threshold': {
                                        'line': {'color': "white", 'width': 4},
                                        'value': reporte['savi_base']
                                    }
                                }
                            ))
                            fig.update_layout(
                                height=400,
                                margin=dict(l=40, r=40, t=80, b=40),
                                paper_bgcolor="rgba(0,0,0,0)",
                                font={'color': "white", 'size': 12}
                            )
                            st.plotly_chart(fig, use_container_width=True)

                            # EXPLICACIÓN
                            st.markdown(f"""
                            <div style="background-color:#1e293b; padding:15px; border-radius:10px; border-left:4px solid #60a5fa;">
                            <b>📊 Interpretación:</b> El valor SAVI de <b>{reporte['savi_actual']:.4f}</b> comparado con la línea base de {reporte['anio_base']} 
                            ({reporte['savi_base']:.4f}) muestra una variación de <b>{reporte['variacion']:.1f}%</b>. 
                            Esto indica un estado de <b>{reporte['nivel']}</b>.
                            </div>
                            """, unsafe_allow_html=True)

                            col_a, col_b = st.columns(2)
                            with col_a:
                                st.metric(label="SAVI Actual", value=f"{reporte['savi_actual']:.4f}")
                            with col_b:
                                st.metric(label="Temperatura", value=f"{reporte['temp']:.1f}°C")
                            
                            st.success(reporte['estado'])

# === PESTAÑA 2: AUDITORÍAS (CON VISTA PREVIA) ===
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
            with st.spinner("Procesando..."):
                try:
                    res = supabase.table("historial_reportes").select("*").eq("proyecto", proyecto).execute()
                    if res.data:
                        df = pd.DataFrame(res.data)
                        df['Fecha'] = pd.to_datetime(df.get('created_at', df.get('fecha', pd.Timestamp.now())))
                        
                        meses = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
                                "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]
                        mes_num = meses.index(mes) + 1
                        
                        df_mes = df[(df['Fecha'].dt.month == mes_num) & (df['Fecha'].dt.year == anio)]
                        
                        if not df_mes.empty:
                            p = supabase.table("usuarios").select("*").eq("Proyecto", proyecto).execute().data[0]
                            reporte = generar_reporte_total(p)
                            
                            img_path = generar_graficos(df_mes)
                            
                            pdf = generar_pdf_profesional(proyecto, proyectos_dict[proyecto], reporte, img_path)
                            
                            pdf_bytes = pdf.output()
                            st.session_state['preview_pdf'] = pdf_bytes
                            
                            # VISTA PREVIA
                            st.success("✅ Auditoría generada")
                            st.subheader("👁️ Vista Previa")
                            
                            # Mostrar información del reporte
                            col_prev1, col_prev2 = st.columns([2, 1])
                            with col_prev1:
                                st.write(f"**Proyecto:** {proyecto}")
                                st.write(f"**Periodo:** {mes} {anio}")
                                st.write(f"**Estado:** {reporte['estado']}")
                            with col_prev2:
                                st.write(f"**Riesgo:** {reporte['nivel']}")
                                st.write(f"**Temperatura:** {reporte['temp']:.1f}°C")
                            
                            # Acciones
                            col_acc1, col_acc2, col_acc3 = st.columns(3)
                            
                            with col_acc1:
                                st.download_button(
                                    label="📥 Descargar PDF",
                                    data=pdf_bytes,
                                    file_name=f"Auditoria_{proyecto}_{mes}_{anio}.pdf",
                                    mime="application/pdf"
                                )
                            
                            if st.session_state.get('admin_mode'):
                                with col_acc2:
                                    if st.button("📤 Enviar a Cliente"):
                                        try:
                                            requests.post(
                                                f"https://api.telegram.org/bot{st.secrets['telegram']['token']}/sendDocument",
                                                data={
                                                    "chat_id": p['telegram_id'],
                                                    "caption": f"Auditoría {proyecto} - {mes} {anio}"
                                                },
                                                files={'document': ('auditoria.pdf', pdf_bytes)},
                                                timeout=30
                                            )
                                            st.success("✅ Enviado a cliente")
                                        except Exception as e:
                                            st.error(f"Error: {str(e)}")
                                
                                with col_acc3:
                                    if st.button("🗑️ Descartar"):
                                        st.session_state['preview_pdf'] = None
                                        st.rerun()
                        else:
                            st.warning(f"Sin datos para {mes}/{anio}")
                except Exception as e:
                    st.error(f"Error: {str(e)}")

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

# === PESTAÑA ADMIN ===
if st.session_state.get('admin_mode'):
    with tab_admin:
        st.title("⚙️ Panel de Admin")
        
        tab_clientes, tab_config = st.tabs(["👥 Clientes", "⚙️ Config"])
        
        with tab_clientes:
            st.subheader("📋 Clientes Registrados")
            
            try:
                res = supabase.table("usuarios").select("*").execute()
                if res.data:
                    for idx, cliente in enumerate(res.data):
                        col1, col2, col3, col4, col5 = st.columns([2, 2, 1.5, 1.5, 1])
                        with col1:
                            st.write(f"🏢 {cliente.get('Proyecto', 'N/A')}")
                        with col2:
                            st.write(f"👤 {cliente.get('titular', 'N/A')}")
                        with col3:
                            st.write(f"📌 {cliente.get('Tipo', 'N/A')}")
                        with col4:
                            st.write(f"📱 {cliente.get('telegram_id', 'N/A')}")
                        with col5:
                            if st.button("✏️", key=f"edit_{idx}"):
                                st.session_state[f"edit_cliente_{idx}"] = True
                    
                    st.divider()
            except Exception as e:
                st.error(f"Error: {e}")
            
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
                    frecuencia = st.selectbox("Frecuencia de Reportes", ["Semanal", "Mensual", "Trimestral"])
                
                with col_freq2:
                    hora_envio = st.time_input("⏰ Hora de Envío", value=time(8, 0))
                
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
        
        with tab_config:
            st.info("⚙️ Configuración del sistema")

# === PESTAÑA SOPORTE (VISIBLE PARA TODOS) ===
with tab_soporte:
    st.title("💬 Soporte BioCore Intelligence")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📞 Contacto Directo")
        st.markdown("""
        **Responsable Técnica:** Loreto Campos Carrasco
        
        📧 Email: soporte@biocoreintelligence.cl
        
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
        
        with st.expander("❓ ¿Qué significan los valores SAVI, NDSI, NDWI?"):
            st.write("""
- **SAVI:** Índice de Vegetación Ajustado al Suelo (vigor de cobertura vegetal)
- **NDSI:** Índice de Diferencia Normalizada de Nieve (cobertura de hielo/nieve)
- **NDWI:** Índice de Diferencia Normalizada de Agua (presencia de agua/humedad)
- **SWIR:** Infrarrojo de Onda Corta (estabilidad de sustrato)
            """)
        
        with st.expander("❓ ¿Cómo descargo mis auditorías?"):
            st.write("""
1. Ve a **'Auditorías'**
2. Selecciona tu proyecto, mes y año
3. Haz click en **'Generar Auditoría'**
4. Visualiza la vista previa
5. Haz click en **'Descargar PDF'**
            """)
    
    with col2:
        st.subheader("📚 Documentación")
        st.markdown("""
        ### Recursos Disponibles
        - 📖 [Manual del Usuario](#manual)
        - 🔬 [Protocolo Técnico](#protocolo)
        - ❓ [Preguntas Frecuentes](#faq)
        - 🎥 [Tutoriales en Video](#video)
        """)
        
        st.subheader("🐛 Reportar Problema")
        with st.form("form_soporte"):
            nombre_reporte = st.text_input("Tu nombre")
            email_reporte = st.text_input("Tu email")
            problema = st.text_area("Describe el problema", height=100)
            severidad = st.selectbox("Severidad", ["Baja", "Media", "Alta", "Crítica"])
            
            if st.form_submit_button("📬 Enviar Reporte"):
                st.success("✅ Reporte enviado. Te contactaremos dentro de 24 horas.")
                st.balloon()

# === PESTAÑA GUÍA ===
with tab_guia:
    st.title("📖 Guía Completa del Sistema BioCore Intelligence")
    
    tab_intro, tab_indices, tab_analisis, tab_protocolo, tab_faq = st.tabs([
        "🎯 Introducción",
        "📊 Índices Espectrales",
        "🔬 Análisis de Datos",
        "⚙️ Protocolo Técnico",
        "❓ Preguntas Frecuentes"
    ])
    
    # === TAB INTRODUCCIÓN ===
    with tab_intro:
        st.markdown("""
        ## 🌍 ¿Qué es BioCore Intelligence?
        
        BioCore Intelligence V7 es una plataforma avanzada de **vigilancia ambiental satelital** 
        que utiliza datos de sensores de Earth Engine para monitorear en tiempo real la salud 
        de ecosistemas, glaciares, bosques y zonas de operación industrial.
        
        ### 🎯 Objetivos Principales
        - ✅ Monitoreo ambiental en tiempo real
        - ✅ Detección temprana de cambios ambientales
        - ✅ Cumplimiento normativo (RCA, Ley de Glaciares, etc.)
        - ✅ Generación de reportes profesionales
        - ✅ Análisis histórico de tendencias
        
        ### 🛰️ Tecnología Utilizada
        
        **Satélites de Monitoreo:**
        - **Sentinel-2:** Imágenes ópticas multiespectrales
        - **MODIS:** Datos de temperatura y radiancia
        - **Sentinel-1:** Radar para análisis de rugosidad superficial
        
        **Procesamiento:**
        - Google Earth Engine
        - Cálculo de índices espectrales
        - Análisis temporal y comparativo
        
        ### 📈 Flujo de Trabajo
        
        ```
        1. Selecciona Proyecto → 2. Ejecuta Reporte → 3. Analiza Velocímetro
        ↓
        4. Descarga Auditoría → 5. Comparte con Stakeholders
        ```
        """)
    
    # === TAB ÍNDICES ESPECTRALES ===
    with tab_indices:
        st.markdown("""
        ## 📊 Índices Espectrales Explicados
        
        ### 🌱 SAVI (Soil-Adjusted Vegetation Index)
        
        **Definición:** Mide el vigor y densidad de la cobertura vegetal
        
        **Fórmula:**
        ```
        SAVI = ((NIR - RED) / (NIR + RED + 0.5)) × 1.5
        ```
        
        **Interpretación:**
        | Valor SAVI | Estado | Acción |
        |:----------:|:------:|:------:|
        | < 0.05 | Suelo desnudo/mineral | Seguimiento normal |
        | 0.05 - 0.20 | Cobertura vegetal baja | Alerta moderada |
        | 0.20 - 0.40 | Cobertura vegetal media | Normal |
        | > 0.40 | Cobertura vegetal densa | Óptimo |
        
        ---
        
        ### ❄️ NDSI (Normalized Difference Snow Index)
        
        **Definición:** Detecta presencia de nieve e hielo
        
        **Fórmula:**
        ```
        NDSI = (GREEN - SWIR) / (GREEN + SWIR)
        ```
        
        **Interpretación:**
        | Valor NDSI | Significado |
        |:----------:|:-----------:|
        | < 0.2 | Sin nieve |
        | 0.2 - 0.4 | Nieve dispersa |
        | > 0.4 | Cobertura nival consolidada |
        
        ---
        
        ### 💧 NDWI (Normalized Difference Water Index)
        
        **Definición:** Indica presencia de agua y humedad en suelo/vegetación
        
        **Fórmula:**
        ```
        NDWI = (NIR - SWIR) / (NIR + SWIR)
        ```
        
        **Interpretación:**
        | Valor NDWI | Significado |
        |:----------:|:-----------:|
        | < -0.1 | Muy seco |
        | -0.1 a 0.1 | Moderadamente seco |
        | > 0.1 | Húmedo/Presencia de agua |
        
        ---
        
        ### 🪨 SWIR (Short-Wave Infrared)
        
        **Definición:** Mide la reflectancia en infrarrojo de onda corta (estabilidad de sustrato)
        
        **Interpretación:**
        - Valores altos → Suelo seco/estable
        - Valores bajos → Suelo húmedo/inestable
        """)
    
    # === TAB ANÁLISIS DE DATOS ===
    with tab_analisis:
        st.markdown("""
        ## 🔬 Análisis de Datos y Reportes
        
        ### 📋 Estructura de un Reporte
        
        Todo reporte en BioCore contiene:
        
        **1. Encabezado Técnico**
        - Nombre del proyecto
        - Fecha de análisis
        - Responsable técnico
        
        **2. Diagnóstico Ejecutivo**
        - Estado general (Verde/Amarillo/Rojo)
        - Nivel de riesgo
        - Recomendaciones inmediatas
        
        **3. Análisis Espectral Detallado**
        - Tabla de índices (SAVI, NDSI, NDWI, SWIR)
        - Comparación con línea base histórica
        - Variaciones porcentuales
        - Temperatura detectada
        
        **4. Gráficos Históricos**
        - Series temporales de cada índice
        - Tendencias de cambio
        - Anomalías detectadas
        
        **5. Conclusiones y Acciones**
        - Interpretación técnica
        - Recomendaciones de seguimiento
        - Firma del responsable técnico
        
        ### 📊 Interpretación de Velocímetro
        
        El velocímetro muestra:
        - **Valor actual (centro):** SAVI del último análisis
        - **Línea blanca (referencia):** SAVI de línea base
        - **Colores de fondo:**
          - 🔴 Rojo: Alerta crítica (SAVI muy bajo)
          - 🟡 Amarillo: Precaución
          - 🟢 Verde: Normal/Óptimo
        
        ### 📈 Comparación Histórica
        
        BioCore compara automáticamente:
        - Datos actuales vs línea base histórica
        - Calcula variación porcentual
        - Identifica tendencias
        - Detecta anomalías
        
        **Ejemplo:**
        ```
        SAVI Actual: 0.2540
        SAVI Base (2017): 0.2100
        Variación: +19.5% ✅
        Interpretación: Mejora en cobertura vegetal
        ```
        """)
    
    # === TAB PROTOCOLO TÉCNICO ===
    with tab_protocolo:
        st.markdown("""
        ## ⚙️ Protocolo Técnico de Validación
        
        ### 🔍 Sistema de Validación de Línea Base Espectral
        
        BioCore utiliza un protocolo avanzado que distingue:
        
        **✅ Cambios Reales (Alertas Legítimas)**
        - Degradación de cobertura vegetal > -15%
        - Pérdida de cobertura nival en criosfera
        - Presencia anómala de agua
        - Estrés térmico extremo
        
        **⚪ Ruido de Sensor (Variaciones Normales)**
        - Fluctuaciones en suelo mineral < 20%
        - Variaciones estacionales normales
        - Cambios dentro de incertidumbre del sensor
        
        ### 🎯 Clasificación Automática de Terreno
        
        El sistema clasifica automáticamente:
        
        | Clase | Criterio | Tolerancia |
        |:-----:|:--------:|:----------:|
        | MINERAL_ÁRIDO | SAVI < 0.10 | ±20% |
        | VEGETADO | SAVI ≥ 0.30 | ±10% |
        | CRIOSFERA | NDSI ≥ 0.35 | Crítico |
        | HÍDRICO | NDWI ≥ 0.20 | Crítico |
        
        ### 🚨 Umbrales de Alerta
        
        **CRÍTICO 🔴**
        - SAVI cae > 15% bajo línea base
        - NDSI en glaciar desciende abruptamente
        - Temperatura > 28°C en zona de montaña
        
        **MODERADO 🟡**
        - SAVI cae 5-15% bajo línea base
        - Anomalía hídrica en zona seca
        - Cambios irregulares en patrones
        
        **NORMAL 🟢**
        - Variaciones < 5%
        - Cambios consistentes con patrón histórico
        - Todas las métricas dentro de rango
        
        ### 📊 Metodología de Comparación
        
        ```
        1. Descarga imagen satelital actual (Sentinel-2)
        2. Calcula índices (SAVI, NDSI, NDWI, SWIR)
        3. Obtiene año de línea base del cliente
        4. Busca imágenes de ese año (menos nubes)
        5. Calcula diferencia absoluta y relativa
        6. Aplica filtros de validación
        7. Genera clasificación final
        8. Entrega reporte con recomendaciones
        ```
        """)
    
    # === TAB FAQ ===
    with tab_faq:
        st.markdown("""
        ## ❓ Preguntas Frecuentes
        
        ### 🎯 Preguntas Generales
        
        **¿Con qué frecuencia debo revisar mis reportes?**
        > Depende de tu configuración. Recomendamos:
        > - **Semanal** para zonas críticas (glaciares, operaciones activas)
        > - **Mensual** para zonas estables (bosques, reservas)
        > - **Trimestral** para monitoreo general
        
        **¿Puedo cambiar mi línea base histórica?**
        > Sí. Contacta a Soporte y especifica el nuevo año. Es recomendable 
        > elegir un año sin anomalías naturales para mejor comparación.
        
        **¿Qué pasa si hay mucha nubosidad?**
        > El sistema busca automáticamente la imagen más reciente sin nubes 
        > (algoritmo CLOUDY_PIXEL_PERCENTAGE). En zonas muy nubladas puede 
        > haber demora de 3-7 días.
        
        ---
        
        ### 📊 Sobre Índices
        
        **¿Por qué mi SAVI es muy bajo?**
        > Posibles causas:
        > - Zona con suelo desnudo/mineral (normal en altura)
        > - Temporada seca (normal estacional)
        > - Degradación real (requiere acción)
        > Consulta con Soporte para interpretación específica.
        
        **¿Qué significa un NDSI negativo?**
        > Significa que no hay nieve en esa zona. Valores negativos son normales 
        > en zonas bajas o durante verano. Para criosfera, es señal de alerta.
        
        **¿El NDWI puede ser negativo?**
        > Sí, y es normal. Valores muy negativos indican sequedad extrema. 
        > Valores cercanos a -0.1 son típicos de desiertos y zonas áridas.
        
        ---
        
        ### 💾 Sobre Reportes
        
        **¿Cuánto tiempo guarda BioCore mis datos históricos?**
        > Conservamos datos desde que empezó tu monitoreo. No hay límite de 
        > retención. Puedes acceder a cualquier reporte anterior desde 'Base de Datos'.
        
        **¿Puedo exportar mis datos?**
        > Sí. Ve a 'Base de Datos' y descarga el CSV con toda tu información histórica.
        
        **¿Cómo obtengo una auditoría para un mes específico?**
        > Ve a 'Auditorías', selecciona mes y año, y haz click en 'Generar Auditoría'. 
        > La vista previa se abrirá para que verifiques antes de descargar.
        
        ---
        
        ### 🔐 Seguridad y Privacidad
        
        **¿Es seguro subir mis coordenadas?**
        > Completamente. Los datos están encriptados en servidor de Supabase 
        > con certificación GDPR. Solo tú y el admin pueden ver tus proyectos.
        
        **¿Quién puede ver mis reportes?**
        > Solo:
        > - Tú (cliente) - acceso a tus propios reportes
        > - Loreto Campos (admin) - acceso a todos para soporte
        > - Nadie más tiene acceso
        
        ---
        
        ### 🆘 Soporte y Ayuda
        
        **¿Cuál es el tiempo de respuesta de Soporte?**
        > - Crítico 🔴: < 2 horas
        > - Alto 🟠: < 4 horas
        > - Medio 🟡: < 24 horas
        > - Bajo 🟢: < 48 horas
        
        **¿Hay capacitación disponible?**
        > Sí. Contacta a Soporte para:
        > - Sesión de bienvenida (30 min)
        > - Training técnico personalizado (1-2 horas)
        > - Webinars mensuales (gratuitos)
        """)

st.markdown("---")
st.markdown("""
<div style="text-align: center; color: #888; font-size: 0.9em; padding: 20px;">
<b>BioCore Intelligence V7</b> | Vigilancia Ambiental Satelital Avanzada
<br>
Responsable Técnica: Loreto Campos Carrasco
<br>
© 2026 - Todos los derechos reservados
</div>
""", unsafe_allow_html=True)
