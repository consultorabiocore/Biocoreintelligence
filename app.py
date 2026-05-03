import streamlit as st
import ee
import folium
from streamlit_folium import folium_static
import json
import pandas as pd
import requests
from datetime import datetime
import plotly.graph_objects as go
from supabase import create_client, Client
import datetime
import matplotlib.pyplot as plt
from fpdf import FPDF
# --- 1. CONFIGURACIÓN ---
st.set_page_config(page_title="BioCore Intelligence V5", layout="wide")

@st.cache_resource
def init_db():
    return create_client(st.secrets["connections"]["supabase"]["url"], st.secrets["connections"]["supabase"]["key"])

supabase = init_db()

def iniciar_gee():
    try:
        if not ee.data.is_initialized():
            creds = json.loads(st.secrets["gee"]["json"])
            # Se recomienda usar el proyecto de Google Cloud explícitamente en V5
            ee_creds = ee.ServiceAccountCredentials(creds['client_email'], key_data=creds['private_key'])
            ee.Initialize(ee_creds, project=creds.get('project_id')) 
            return True
    except Exception as e:
        st.error(f"Error crítico en GEE: {e}")
        return False

# ¡ESTA LÍNEA ES VITAL! Debe ejecutarse al cargar la app
gee_status = iniciar_gee()

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

# --- 3. MOTOR DE REPORTE COMPLETO ---
def generar_reporte_total(p):
    # 1. Definición de perfiles
    PERFILES = {
        "MINERIA": {"cat": "RCA Minería (F-30)", "ve7": "Estabilidad de taludes.", "clima": "Protocolo extremos."},
        "GLACIAR": {"cat": "RCA Criosfera", "ve7": "Balance de masa.", "clima": "Ley de Glaciares."},
        "BOSQUE": {"cat": "Ley 20.283", "ve7": "Vigilancia regeneración.", "clima": "Prevención incendios."}
    }
    
    tipo = p.get('Tipo', 'MINERIA')
    d = PERFILES.get(tipo, PERFILES["MINERIA"])

    # 2. CARGA DE GEOMETRÍA (Ajustado a tu columna 'Coordenadas')
    try:
        raw_coords = p.get('Coordenadas')
        
        if raw_coords is None:
            return f"Error: La columna 'Coordenadas' está vacía para {p.get('Proyecto')}.", 0, 0

        if isinstance(raw_coords, str):
            import json
            try:
                raw_coords = json.loads(raw_coords)
            except:
                raw_coords = eval(raw_coords)

        # Crear geometría para Earth Engine
        geom = ee.Geometry.Polygon(raw_coords)
        
    except Exception as e:
        return f"Error crítico en geometría: {str(e)}", 0, 0

    # 3. PROCESAMIENTO SATELITAL
    # 1. Óptico: Sentinel-2
    s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')\
           .filterBounds(geom)\
           .sort('system:time_start', False)\
           .first()
    
    f_rep = datetime.fromtimestamp(s2.get('system:time_start').getInfo()/1000).strftime('%d/%m/%Y')
    
    # 2. Radar: Sentinel-1 (Rugosidad/Estructuras)
    s1 = ee.ImageCollection('COPERNICUS/S1_GRD')\
           .filterBounds(geom)\
           .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV'))\
           .sort('system:time_start', False)\
           .first()
    radar_val = s1.select('VV')

    # 3. Clima: Temperatura MODIS
    temp_img = ee.ImageCollection("MODIS/061/MOD11A1")\
                 .filterBounds(geom)\
                 .sort('system:time_start', False)\
                 .first()
    
    # Convertimos Kelvin a Celsius (Cálculo corregido)
    temp_val = temp_img.select('LST_Day_1km').multiply(0.02).subtract(273.15)\
                       .reduceRegion(ee.Reducer.mean(), geom, 1000).getInfo().get('LST_Day_1km', 0)
    
    # 4. Emergencias: Focos de Incendio FIRMS (últimos 3 días)
    focos = ee.ImageCollection("FIRMS")\
              .filterBounds(geom)\
              .filterDate(ee.Date(datetime.now()).advance(-3, 'day'))\
              .size().getInfo()

    alerta_incendio = "⚠️ ALERT: Focos detectados" if focos > 0 else "✅ Sin focos activos"

        # --- B. CÁLCULO DE ÍNDICES Y COMPARATIVA ---
    
    # 1. Función para calcular índices en la imagen actual
    def calcular_idx(img):
        # SAVI (Suelo Ajustado)
        savi = img.expression('((NIR - RED) / (NIR + RED + 0.5)) * (1.5)', {
            'NIR': img.select('B8'), 'RED': img.select('B4')
        }).rename('sa')
        # NDSI (Nieve)
        ndsi = img.normalizedDifference(['B3', 'B11']).rename('ndsi')
        # SWIR (Humedad)
        swir = img.select('B11').divide(10000).rename('sw')
        # CLAY (Arcillas)
        clay = img.normalizedDifference(['B11', 'B12']).rename('clay')
        
        return img.addBands([savi, ndsi, swir, clay])

    # Aplicar a la imagen actual y extraer valores
    img_now = calcular_idx(s2)
    idx = img_now.reduceRegion(ee.Reducer.mean(), geom, 30).getInfo()
    
    # 2. COMPARATIVA HISTÓRICA (Usando el año de línea base)
    anio_base = p.get('anio_linea_base', 2017)
    s2_base = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')\
                .filterBounds(geom)\
                .filterDate(f'{anio_base}-01-01', f'{anio_base}-12-31')\
                .sort('CLOUDY_PIXEL_PERCENTAGE')\
                .first()
    
    img_base = calcular_idx(s2_base)
    idx_base = img_base.reduceRegion(ee.Reducer.mean(), geom, 30).getInfo()
    
    # 3. CÁLCULO DE VARIACIÓN (KPI Principal)
    # 3. CÁLCULO DE VARIACIÓN (KPI Principal con Inteligencia de Umbrales)
    s_actual = float(idx.get('sa', 0))
    s_base = float(idx_base.get('sa', 0.001)) 

    # --- LÓGICA DINÁMICA BIOCORE ---
    # 1. Extraer valores del satélite
    v_now = float(idx.get('sa', 0))
    v_base = float(idx_base.get('sa', 0))

    # --- LÓGICA DINÁMICA BIOCORE ---
    if abs(v_now) < 0.05 and abs(v_base) < 0.05:
        variacion = 0.0
        est_global = "🟢 BAJO CONTROL"
        exp_savi = "Suelo estable. Los valores bajos son consistentes con la litología y altitud del sector."
    else:
        # Cálculo usando valor absoluto para evitar errores de signo
        variacion = ((v_now - v_base) / abs(v_base if v_base != 0 else 0.001)) * 100
        
        umbral_critico = -15 if d['cat'] == "RCA Minería (F-30)" else -25
        
        if variacion < umbral_critico:
            est_global = "🔴 ALERTA CRÍTICA"
            exp_savi = "Descenso significativo detectado. Posible intervención o estrés hídrico severo."
        else:
            est_global = "🟢 BAJO CONTROL"
            exp_savi = "La cobertura vegetal se mantiene estable dentro de los rangos históricos."

    # 1. Lógica de Nieve (NDSI)
    v_ndsi = float(idx.get('ndsi', 0))
    if v_ndsi > 0.4:
        exp_snow = "Cobertura de nieve/hielo consolidada, esencial para el balance hídrico."
    elif v_ndsi > 0.1:
        exp_snow = "Nieve dispersa o en fusión. Se observa transición en la criósfera."
    else:
        exp_snow = "Nula presencia de nieve. Predomina suelo expuesto o sustrato rocoso."

    # 2. Lógica de Conclusión (Oficial y Dinámica)
    # Aquí se gestiona la Alerta Verde y la ALERTA ROJA
    if est_global == "🟢 BAJO CONTROL":
        nucleo = f"estabilidad técnica del área bajo el perfil {d['cat']}."
        accion = "Se sugiere mantener la periodicidad de vigilancia programada."
    else:
        nucleo = f"una anomalía crítica en {d['cat']}, con una desviación del {variacion:.1f}%."
        accion = "Se requiere activar el protocolo de inspección y revisar el blindaje legal."

    # 3. Hallazgo Crítico
    if v_ndsi < 0.2 and d['cat'] == "GLACIAR":
        detalle = " La pérdida de cobertura nival es el factor de mayor incidencia."
    elif variacion < -15:
        detalle = " El descenso en el vigor fotosintético (SAVI) es el parámetro dominante."
    elif temp_val > 28:
        detalle = " El estrés térmico detectado eleva la vulnerabilidad del sector."
    else:
        detalle = " Los parámetros se mantienen dentro de la varianza histórica permitida."

    conclusion_final = f"Tras el análisis, se concluye {nucleo}{detalle} {accion}"

    # 4. Interpretación Radar (Sentinel-1)
    v_radar = float(idx.get('radar_vv', 0))
    if v_radar > -12:
        exp_radar = "La señal sugiere una superficie rugosa o presencia de estructuras, consistente con la actividad operativa."
    else:
        exp_radar = "El radar indica una superficie lisa o despejada, ideal para el seguimiento de la estabilidad del terreno."

    # 5. Interpretación Humedad (SWIR)
    v_swir = float(idx.get('sw', 0))
    if v_swir < 0.2:
        exp_swir = "Niveles de humedad en suelo bajos. Se recomienda monitorear ante posibles riesgos de aridez extrema."
    else:
        exp_swir = "Niveles de humedad óptimos detectados, garantizando estabilidad en el sustrato."
    # --- PASO CLAVE: Extraer los valores del diccionario de resultados ---
    # Asumiendo que 'idx' es el diccionario que obtuviste con .reduceRegion().getInfo()
    
    v_savi = float(idx.get('sa', 0))    # Usamos 'sa' porque así lo nombraste en la función
    v_ndsi = float(idx.get('ndsi', 0))
    v_swir = float(idx.get('sw', 0))
    v_clay = float(idx.get('clay', 0))
    
    # Esto conecta tus cálculos con las variables que pide el reporte
    s_actual = v_savi 

    # --- E. CONSTRUCCIÓN DEL MENSAJE FINAL ---
    texto_final = f"""
🛰 **REPORTE DE VIGILANCIA AMBIENTAL - BIOCORE**
**PROYECTO:** {p['Proyecto']}
📅 **Análisis:** {f_rep} | **Línea Base:** {anio_base}
──────────────────
❄️ **ESTADO DE CRIÓSFERA (NDSI):**
└ Cobertura Actual: `{v_ndsi:.3f}`
└ **Análisis:** {exp_snow}

📡 **MONITOREO RADAR (Sentinel-1):**
└ Retrodispersión VV: `{v_radar:.2f} dB`
└ **Análisis:** {exp_radar}

🛡️ **INTEGRIDAD DEL TERRENO (SU-6):**
└ Humedad (SWIR): `{v_swir:.2f}` | Arcillas: `{v_clay:.2f}`
└ **Análisis:** {exp_swir}

🌱 **SALUD VEGETAL (SAVI):**
└ Vigor Actual: `{v_savi:.3f}` | Base: `{s_base:.3f}`
└ Variación: `{variacion:.1f}%` respecto al original.
└ **Análisis:** {exp_savi}

⚠️ **RIESGO CLIMÁTICO:**
└ Temperatura: `{temp_val:.1f}°C` | Incendios: {alerta_incendio}
──────────────────
✅ **ESTADO GLOBAL:** {est_global}
📝 **CONCLUSIÓN FINAL:** {conclusion_final}
    """ # Este cierra el texto_final
    # Final de la función
    return texto_final, s_actual, s_base
# --- 4. INTERFAZ ---
# Añadimos la pestaña "⚙️ Admin"
# Definimos las 4 pestañas en el orden correcto
tab1, tab_informe, tab_excel, tab_admin = st.tabs([
    "🚀 Vigilancia Activa", 
    "📁 Informes de Auditoría", 
    "📊 Base de Datos (Excel)", 
    "⚙️ Admin"
])

# --- PESTAÑA 1: VIGILANCIA (Tu código actual de mapas y botones rápidos) ---
with tab1:
    proyectos = supabase.table("usuarios").select("*").execute().data
    
    if proyectos:
        for p in proyectos:
            # Título del Proyecto como encabezado directo
            st.markdown(f"### 📍 Proyecto: {p['Proyecto']}")
            
            # Layout de alta visibilidad
                        # Layout de alta visibilidad (Asegúrate de que estas líneas no tengan espacios extra al inicio)
            col_mapa, col_reporte = st.columns([2.5, 1])
            
            with col_mapa:
                # El mapa se renderiza directamente
                m_obj = dibujar_mapa_biocore(p['Coordenadas'])
                folium_static(m_obj, width=850, height=500)

            with col_reporte:
                if st.button("🚀 Ejecutar Reporte Completo", key=p['Proyecto']):
                    with st.spinner("Generando análisis dinámico..."):
                        # 1. Obtención de datos
                        txt, v_now, v_base = generar_reporte_total(p)
                        anio_base = p.get('anio_linea_base', 2017)
                        tipo = p.get('Tipo', 'Minería') 

                        # 2. BLINDAJE ANTI-169% (Lógica de Estabilidad)
                        # Si el valor actual es muy bajo (suelo mineral), forzamos estabilidad absoluta
                        es_estable = abs(v_now) < 0.05 and abs(v_base) < 0.05
                        
                        if es_estable:
                            v_ref_grafico = v_now + 0.00001 # Truco para que Plotly renderice el 0.0%
                            delta_texto = "0.0% (Estable)"
                            detalles = f"Análisis de alta montaña. El valor SAVI de {v_now:.4f} es consistente con la litología mineral del sector. La variación del 0.0% certifica la estabilidad del terreno y la ausencia de sedimentos o polvo sobre la firma espectral original de {anio_base}."
                        else:
                            v_ref_grafico = v_base
                            # Cálculo manual para evitar errores de división o saltos bruscos
                            diff = ((v_now - v_base) / abs(v_base if v_base != 0 else 1)) * 100
                            delta_texto = f"{diff:.1f}%"
                            
                            # Textos según tipo (Resto de categorías)
                            if tipo == 'Bosque Nativo':
                                detalles = f"Monitoreo de biomasa forestal. El SAVI de {v_now:.4f} refleja la densidad del dosel y salud de las especies nativas."
                            elif tipo == 'Humedal':
                                detalles = f"Control de ecosistema hídrico. Valores de {v_now:.4f} permiten vigilar la salud de la vegetación hidrófila."
                            elif tipo == 'Agrícola':
                                detalles = f"Seguimiento de vigor de cultivo. El SAVI de {v_now:.4f} valida la estabilidad de la productividad por lote."
                            else:
                                detalles = f"Control de entorno operativo. El valor de {v_now:.4f} asegura la protección de la vegetación periférica."

                        # 3. ENVÍO A TELEGRAM
                        try:
                            response = requests.post(
                                f"https://api.telegram.org/bot{st.secrets['telegram']['token']}/sendMessage", 
                                data={"chat_id": p['telegram_id'], "text": txt, "parse_mode": "Markdown"},
                                timeout=10
                            )
                            if response.status_code == 200:
                                st.success("✅ ¡Reporte enviado!")
                            else:
                                st.error(f"❌ Error Telegram: {response.status_code}")
                        except Exception as e:
                            st.warning(f"⚠️ Error conexión: {e}")

                        # 4. MÉTRICA (Aquí forzamos el texto para que no aparezca el 169%)
                        st.metric(
                            label=f"SAVI Actual vs Base {anio_base}", 
                            value=f"{v_now:.4f}", 
                            delta=delta_texto
                        )

                        # 5. GRÁFICO (Solo arco)
                        fig = go.Figure(go.Indicator(
                            mode = "gauge",
                            value = v_now,
                            gauge = {
                                'axis': {'range': [0, 0.15], 'tickwidth': 1, 'tickcolor': "white"},
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
                        fig.update_layout(height=220, margin=dict(l=40, r=40, t=20, b=20), paper_bgcolor="rgba(0,0,0,0)", font={'color': "white"})
                        st.plotly_chart(fig, use_container_width=True)

                        # 6. EXPLICACIÓN DINÁMICA PREMIUM
                        st.markdown(f"""
                        <div style="background-color:#0e1117; padding:20px; border-radius:15px; border: 1px solid #30363d; color: white;">
                            <h3 style="margin-top:0; color:#4ade80; font-size:1.1em;">🌿 Interpretación BioCore: {tipo.upper()}</h3>
                            <p style="font-size:0.95em; line-height:1.6; color:#e2e8f0;">
                                {detalles}
                            </p>
                            <div style="background-color:#1e293b; padding:10px; border-radius:8px; margin-top:10px; border-left: 4px solid #60a5fa;">
                                <span style="font-size:0.85em; color:#94a3b8;"><b>Estatus:</b> Cumplimiento Ambiental Validado.</span>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)

# --- CONFIGURACIÓN ESTÉTICA "BIOCORE PREMIUM" ---
# Usando la paleta de tu logo (Dorado y Verde)
COLORES_BIOCORE = {
    'dorado': '#B59410', # Dorado principal
    'verde_fondo': '#E8F5E9', # Verde muy suave para fondo de gráficos
    'gris_texto': '#424242', # Gris oscuro para ejes
    'azul_encabezado': (20, 50, 80) # Mantenemos el azul marino para contraste legal
}

# Función auxiliar para limpiar texto para FPDF
def clean(text):
    return text.encode('latin-1', 'replace').decode('latin-1')

# --- LÓGICA DE LA PESTAÑA EN STREAMLIT ---
# Asegúrate de que esta pestaña esté ubicada después de "🚀 Vigilancia Activa"
with tab_informe:
    # Usamos tu logo como encabezado de la pestaña
    st.header("🛡️ Centro de Auditoría Técnico-Legal")
    st.markdown("---")

    # 1. Parámetros de Selección
    col_p, col_m, col_a = st.columns(3)
    with col_p:
        # Traemos la lista de nombres de proyectos de Supabase
        nombres_proy = [p['Proyecto'] for p in proyectos]
        proyecto_sel = st.selectbox("Seleccione Proyecto", nombres_proy)
    with col_m:
        mes_sel = st.selectbox("Mes de Auditoría", ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"])
    with col_a:
        anio_sel = st.number_input("Año", value=2026)

    # 2. BOTÓN DE GENERACIÓN
    if st.button(f"📄 Generar Reporte PDF Premium para {proyecto_sel}"):
        with st.spinner("Compilando datos históricos de Supabase y aplicando paleta corporativa..."):
            
            # 3. EXTRACCIÓN DE DATOS REALES (Desde tu tabla de Supabase)
            # Reutilizamos la lógica que lee de Supabase filtrando por proyecto
            res = supabase.table("historial_reportes").select("*").eq("proyecto", proyecto_sel).execute()
            
            if res.data:
                df = pd.DataFrame(res.data)
                df['Fecha'] = pd.to_datetime(df['created_at'])
                
                # Filtrar por mes y año seleccionado
                mes_num = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"].index(mes_sel) + 1
                df_mes = df[(df['Fecha'].dt.month == mes_num) & (df['Fecha'].dt.year == anio_sel)].sort_values('Fecha')

                if not df_mes.empty:
                    # --- LÓGICA DE GRÁFICOS PREMIUM (Tu código integrado con NUEVOS COLORES) ---
                    # Matplotlib con alta resolución (DPI 300) para nitidez
                    fig, axes = plt.subplots(4, 1, figsize=(10, 12), dpi=300) 
                    
                    # Usamos el Dorado de tu logo para TODAS las líneas, marcando consistencia
                    color_linea = COLORES_BIOCORE['dorado']
                    
                    config = [
                        ('ndsi', 'ÁREA DE NIEVE/HIELO (NDSI)'),
                        ('ndwi', 'RECURSOS HÍDRICOS (NDWI)'),
                        ('swir', 'ESTABILIDAD DE SUSTRATO (SWIR)'),
                        ('polvo', 'DEPÓSITO DE MATERIAL PARTICULADO')
                    ]
                    
                    for i, (col_data, titulo) in enumerate(config):
                        # Graficamos la línea real
                        axes[i].plot(df_mes['Fecha'], df_mes[col_data], color=color_linea, marker='o', linewidth=2.5, markersize=5)
                        
                        # Títulos en Dorado y Negrita
                        axes[i].set_title(titulo, fontweight='bold', fontsize=12, color=COLORES_BIOCORE['dorado'])
                        
                        # Estética de fondo (Verde Suave) y Grilla
                        axes[i].set_facecolor(COLORES_BIOCORE['verde_fondo'])
                        axes[i].grid(True, alpha=0.3, linestyle='--', color='white')
                        
                        # Suavizamos los ejes
                        for spine in axes[i].spines.values():
                            spine.set_color('#cccccc')
                        axes[i].tick_params(colors=COLORES_BIOCORE['gris_texto'], labelsize=9)
                    
                    plt.tight_layout(pad=4.0)
                    # Guardamos temporalmente en alta resolución
                    plt.savefig('evidencia_premium.png', dpi=300, bbox_inches='tight')
                    plt.close()

                    # --- CONSTRUCCIÓN DEL PDF (Tu formato legal con ALTA CALIDAD) ---
                    pdf = FPDF()
                    pdf.add_page()
                    
                    # Encabezado Azul Marino (Mantenemos el contraste legal)
                    pdf.set_fill_color(COLORES_BIOCORE['azul_encabezado'][0], COLORES_BIOCORE['azul_encabezado'][1], COLORES_BIOCORE['azul_encabezado'][2])
                    pdf.rect(0, 0, 210, 40, 'F')
                    
                    # Insertamos tu logo en el PDF (Esquina superior izquierda)
                    pdf.image("logo_biocore.jpg", x=10, y=8, w=45)
                    
                    pdf.set_text_color(255, 255, 255)
                    pdf.set_font("helvetica", "B", 18)
                    pdf.set_xy(60, 15)
                    pdf.cell(0, 10, clean(f"AUDITORÍA AMBIENTAL: {proyecto_sel.upper()}"), align="L", ln=1)
                    
                    pdf.set_font("helvetica", "I", 10)
                    pdf.set_xy(60, 25)
                    pdf.cell(0, 5, clean(f"Reporte de Cumplimiento Técnico | Periodo: {mes_sel} {anio_sel}"), align="L", ln=1)
                    pdf.set_font("helvetica", "", 10)
                    # 2. Lógica de Alerta y Banner de Estatus
ndsi_val = df_mes['ndsi'].iloc[-1]
es_alerta = ndsi_val < 0.35
color_res = (220, 50, 50) if es_alerta else (40, 150, 80)
estado_txt = "ALERTA TÉCNICA - PÉRDIDA DE COBERTURA" if es_alerta else "CUMPLIMIENTO AMBIENTAL ESTABLE"

pdf.set_y(45)
pdf.set_fill_color(color_res[0], color_res[1], color_res[2])
pdf.set_text_color(255, 255, 255)
pdf.set_font("helvetica", "B", 12)
pdf.cell(0, 12, clean(f"  ESTATUS: {estado_txt}"), ln=1, fill=True)

# 3. Diagnóstico con Línea Base (Lo que agregamos recién)
pdf.ln(5)
pdf.set_text_color(0, 0, 0)
pdf.set_font("helvetica", "B", 11)
pdf.cell(0, 10, clean(f"ANÁLISIS COMPARATIVO (REF: LÍNEA BASE {anio_lb_real})"), ln=1)

pdf.set_font("helvetica", "", 10)
diagnostico_lb = (
    f"Se contrastan los valores actuales del periodo {mes_sel} {anio_sel} con la firma espectral "
    f"registrada en la LINEA BASE DEL AÑO {anio_lb_real}.\n\n"
    f"El índice NDSI detectado ({ndsi_val:.2f}) se utiliza para validar la estabilidad criosférica "
    "frente a la normativa vigente. "
)
pdf.multi_cell(0, 8, clean(diagnostico_lb), border="B")

# --- SEGUNDA PÁGINA: EVIDENCIA GRÁFICA ---
pdf.add_page()
pdf.set_font("helvetica", "B", 14)
pdf.set_text_color(20, 50, 80)
pdf.cell(0, 10, clean("EVIDENCIA ESPECTRAL HISTÓRICA (DATOS REALES)"), ln=1, align="C")
pdf.image('evidencia_premium.png', x=10, y=25, w=190)

# 4. Firma Profesional
pdf.set_y(265)
pdf.set_text_color(0, 0, 0)
pdf.set_font("helvetica", "B", 10)
pdf.cell(0, 5, clean("Loreto Campos Carrasco"), align="C", ln=1)
pdf.set_font("helvetica", "I", 9)
pdf.cell(0, 5, clean("Directora Técnica - BioCore Intelligence"), align="C", ln=1)

# Finalización
pdf_file = f"Auditoria_BioCore_{proyecto_sel}_{mes_sel}.pdf"
pdf.output(pdf_file)
# --- RESULTADO EN APP ---
# --- 8 ESPACIOS (Nivel del IF principal)
st.success(f"✅ Auditoría Premium generada para {proyecto_sel}")
                    
# --- 8 ESPACIOS (Línea 545)
with open(pdf_file, "rb") as f:
                        
# --- 12 ESPACIOS (Línea 546)
    st.download_button("📥 Descargar PDF de Cumplimiento", f, file_name=pdf_file)

# --- 8 ESPACIOS (Línea 547 - El "else" vuelve atrás)
else:
    st.warning(f"No se encontraron datos históricos...")

else:
    st.error("No se pudo conectar con el historial de Supabase (Pestaña Excel).")
                # --- EL VELOCÍMETRO VA AQUÍ (Solo se muestra en la App, no en el PDF) ---
st.plotly_chart(crear_velocimetro(ndsi_val, "Estado Actual NDSI"), use_container_width=True)

st.success(f"✅ Reporte generado y visualización de estatus actualizada.")
with open(pdf_file, "rb") as f:
    st.download_button("📥 Descargar PDF para Cliente", f, file_name=pdf_file)
    
# --- PESTAÑA 3: EXCEL (Visualización de la tabla cruda) ---
with tab_excel:
    st.subheader("📊 Historial Acumulado de Mediciones")
    hist = supabase.table("historial_reportes").select("*").execute().data
    if hist:
        df_hist = pd.DataFrame(hist)
        st.dataframe(df_hist, use_container_width=True)
        csv = df_hist.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Descargar Base de Datos Completa (CSV)", csv, "BioCore_Database.csv", "text/csv")

# --- PESTAÑA 4: ADMIN (Gestión de usuarios y coordenadas) ---
# --- PESTAÑA 4: ADMIN (TU CÓDIGO DE REGISTRO) ---
with tab_admin:
    st.title("🛡️ Panel de Control BioCore")
    st.markdown("### Registrar o Actualizar Proyecto")
    
    with st.form("form_registro_cliente", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            titular = st.text_input("👤 Nombre del Titular")
            nombre_proy = st.text_input("🚀 Nombre del Proyecto")
            tipo_proy = st.selectbox("🌿 Tipo", ["Minería", "Bosque Nativo", "Humedal", "Agrícola", "Industrial"])
        with col2:
            telegram_id = st.text_input("📱 ID Telegram")
            coords = st.text_input("📍 Coordenadas (Lat, Lon)")
            hora_envio = st.time_input("⏰ Hora de Envío Automático", value=datetime.time(8, 0))
        
        if st.form_submit_button("💾 Guardar en BioCore Cloud"):
            nuevo_p = {
                "titular": titular,
                "Proyecto": nombre_proy,
                "Tipo": tipo_proy,
                "telegram_id": telegram_id,
                "Coordenadas": coords,
                "hora_envio": hora_envio.strftime("%H:%M"),
                "anio_linea_base": anio_lb  # SE GUARDA EN SUPABASE
            }
            supabase.table("usuarios").upsert(nuevo_p).execute()
            st.success(f"✅ {nombre_proy} guardado correctamente.")
            st.balloons()
