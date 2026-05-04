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

# CSS personalizado
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
    """Limpia caracteres especiales para FPDF"""
    return text.encode('latin-1', errors='replace').decode('latin-1')

# === SISTEMA DE AUTENTICACIÓN ===
def hash_password(password):
    """Genera hash SHA256 de contraseña"""
    return hashlib.sha256(password.encode()).hexdigest()

def es_admin(contraseña_admin):
    """Verifica si es el admin"""
    return contraseña_admin == "2861701l"

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
                    df_clean = pd.to_numeric(df[col], errors='coerce').dropna()
                    
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
        
        return img_path
    except Exception as e:
        return None

# === GENERADOR DE REPORTE ---
def generar_reporte_total(p):
    """Genera reporte completo"""
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
    elif variacion < -15:
        estado = "🔴 ALERTA CRÍTICA"
        nivel = "CRÍTICO"
    else:
        estado = "🟡 PRECAUCIÓN"
        nivel = "MODERADO"

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
        'variacion': variacion
    }

# === INICIALIZAR SESSION STATE ===
if 'authenticated' not in st.session_state:
    st.session_state['authenticated'] = False
    st.session_state['admin_mode'] = False
    st.session_state['proyecto_cliente'] = None

# === SIDEBAR CON AUTENTICACIÓN ===
with st.sidebar:
    st.markdown("### 🔐 Autenticación")
    st.markdown("---")
    
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
            st.rerun()

if not st.session_state.get('authenticated'):
    st.warning("⚠️ Debes iniciar sesión para acceder a BioCore Intelligence")
    st.stop()

# === TABS PRINCIPALES ===
tab1, tab_informe, tab_excel, tab_admin, tab_guia = st.tabs([
    "🛰️ Vigilancia", 
    "📋 Auditorías", 
    "📊 Base Datos", 
    "⚙️ Admin", 
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

                            # === VELOCÍMETRO (GAUGE) ===
                            fig = go.Figure(go.Indicator(
                                mode="gauge+number",
                                value=reporte['savi_actual'],
                                domain={'x': [0, 1], 'y': [0, 1]},
                                title={'text': f"SAVI Actual vs {reporte['anio_base']}"},
                                gauge={
                                    'axis': {'range': [0, 0.15]},
                                    'bar': {'color': "#2c3e50"},
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
                            fig.update_layout(height=250, paper_bgcolor="rgba(0,0,0,0)", font={'color': "white"})
                            st.plotly_chart(fig, use_container_width=True)

                            col_a, col_b = st.columns(2)
                            with col_a:
                                st.metric(label="SAVI Actual", value=f"{reporte['savi_actual']:.4f}")
                            with col_b:
                                st.metric(label="Variación", value=f"{reporte['variacion']:.1f}%")
                            
                            st.success(reporte['estado'])
                            st.write(f"**Riesgo:** {reporte['nivel']}")

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
        
        if st.button("📊 Generar PDF Auditoría"):
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
                            
                            pdf = FPDF()
                            pdf.add_page()
                            
                            pdf.set_fill_color(20, 50, 80)
                            pdf.rect(0, 0, 210, 40, 'F')
                            pdf.set_text_color(255, 255, 255)
                            pdf.set_font("helvetica", "B", 16)
                            pdf.cell(0, 20, clean(f"AUDITORÍA {proyecto.upper()}"), align="C", ln=1)
                            
                            pdf.set_font("helvetica", "I", 10)
                            pdf.cell(0, 5, clean("BioCore Intelligence V7"), align="C", ln=1)
                            
                            pdf.ln(10)
                            pdf.set_text_color(0, 0, 0)
                            pdf.set_font("helvetica", "B", 11)
                            pdf.cell(0, 8, clean(f"Estado: {reporte['estado']}"), ln=1)
                            
                            pdf.ln(5)
                            pdf.set_font("helvetica", "", 9)
                            pdf.multi_cell(0, 4, clean(reporte['diagnostico']), border=1)
                            
                            if img_path and os.path.exists(img_path):
                                pdf.add_page()
                                pdf.set_font("helvetica", "B", 12)
                                pdf.cell(0, 10, clean("ANÁLISIS ESPECTRAL"), ln=1)
                                pdf.image(img_path, x=15, y=30, w=180)
                            
                            pdf_file = f"Auditoria_{proyecto}_{mes}_{anio}.pdf"
                            pdf.output(pdf_file)
                            
                            with open(pdf_file, "rb") as f:
                                st.download_button("📥 Descargar PDF", f.read(), pdf_file)
                            
                            st.success("✅ PDF generado")
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

# === PESTAÑA 4: ADMIN ===
with tab_admin:
    if not st.session_state.get('admin_mode'):
        st.error("❌ Solo admins")
    else:
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
                    coords_json = st.text_area("Coordenadas (JSON)", height=100)
                
                hora_envio = st.time_input("Hora Envío", value=time(8, 0))
                
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
                                "hora_envio": hora_envio.strftime("%H:%M"),
                                "password_cliente": hash_password(password_cliente) if password_cliente else ""
                            }
                            supabase.table("usuarios").upsert(nuevo_cliente).execute()
                            st.success(f"✅ {nombre_proyecto} guardado")
                            st.balloons()
                        except Exception as e:
                            st.error(f"Error: {str(e)}")
        
        with tab_config:
            st.info("Configuración del sistema")

# === PESTAÑA 5: GUÍA ===
with tab_guia:
    if not st.session_state.get('admin_mode'):
        st.error("❌ Solo admins")
    else:
        st.title("📖 Guía del Protocolo")
        st.info("Documentación técnica del sistema BioCore Intelligence V7")
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
            st.markdown("""
**Regla 1: Diferencia Absoluta Mínima**
- Si |ΔValue| < 0.05 → Se considera ruido de sensor
- No genera alerta

**Regla 2: Tolerancia en Suelos Minerales**
- Para MINERAL_ARIDO: Variación relativa permitida hasta ±20%
- Refleja la naturaleza ruidosa de estos terrenos

**Regla 3: Detección de Cambios Reales**
- VEGETADO: Degradación si Δ < -15%
- CRIOSFERA: Pérdida nival si NDSI disminuye significativamente
- HIDRICO: Anomalía si NDWI aumenta en zona históricamente seca
            """)
        
        st.markdown("---")
        st.info("📞 Para ajustar parámetros específicos, contacta al equipo de BioCore")
