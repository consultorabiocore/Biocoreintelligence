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
tab1, tab2 = st.tabs(["🚀 Vigilancia Activa", "📊 Excel"])

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
                        # 1. Obtenemos los datos de la función principal
                        txt, v_now, v_base = generar_reporte_total(p)
                        
                        # 2. LIMPIEZA DE DATOS (Filtro Anti-Error Matemático)
                        # Si los valores son muy bajos (roca/alta montaña), forzamos estabilidad
                        if abs(v_now) < 0.05 and abs(v_base) < 0.05:
                            v_delta_ref = v_now  # Al ser iguales, el delta será 0%
                            msg_interpretacion = "Suelo estable. Los valores bajos son consistentes con la litología y altitud del sector."
                        else:
                            v_delta_ref = v_base # Usamos la base real si hay vegetación
                            msg_interpretacion = "La cobertura vegetal se mantiene según los rangos históricos."

                        # 3. Envío a Telegram
                        requests.post(f"https://api.telegram.org/bot{st.secrets['telegram']['token']}/sendMessage", 
                                     data={"chat_id": p['telegram_id'], "text": txt, "parse_mode": "Markdown"})
                        
                        st.success("¡Reporte enviado a Telegram!")

                        # 4. VELOCÍMETRO DE CUMPLIMIENTO AMBIENTAL
                        fig = go.Figure(go.Indicator(
                            mode = "gauge+number+delta",
                            value = v_now,
                            domain = {'x': [0, 1], 'y': [0, 1]},
                            title = {'text': f"Estado vs. Pre-Proyecto ({p.get('anio_linea_base', 2017)})", 'font': {'size': 18}},
                            delta = {
                                'reference': v_delta_ref, 
                                'relative': True, 
                                'valueformat': '.1%', 
                                'increasing': {'color': "#00CC96"}, 
                                'decreasing': {'color': "#EF553B"}
                            },
                            gauge = {
                                'axis': {'range': [0, 0.15], 'tickwidth': 1},
                                'bar': {'color': "black"},
                                'steps': [
                                    {'range': [0, 0.05], 'color': "#FFDDDD"}, # Alerta
                                    {'range': [0.05, 0.10], 'color': "#FFFFDD"}, # Precaución
                                    {'range': [0.10, 0.15], 'color': "#DDFFDD"}  # Óptimo
                                ],
                                'threshold': {
                                    'line': {'color': "red", 'width': 5},
                                    'thickness': 0.8,
                                    'value': v_base 
                                }
                            }
                        ))

                        fig.update_layout(height=350, margin=dict(l=30, r=30, t=50, b=20))
                        st.plotly_chart(fig, use_container_width=True)

                        # 5. EXPLICACIÓN DETALLADA PARA EL CLIENTE
                        st.info(f"""
                        **📊 Guía de Lectura del Indicador:**
                        
                        * **Número Superior ({v_now:.3f}):** Es el nivel de **Vigor Vegetal Actual**. En esta altitud, valores cercanos a 0 representan suelo mineral o roca.
                        * **Número Inferior (Δ%):** Indica cuánto ha cambiado el vigor respecto a la **Línea Base ({p.get('anio_linea_base', 2017)})**. 
                            * Un **0.0%** indica que el terreno se mantiene sin cambios biológicos significativos.
                        * **Línea Roja (🚩):** Es el umbral histórico. Si la aguja está a la derecha de la línea, el proyecto cumple con su compromiso ambiental.
                        
                        **🔍 Diagnóstico:** {msg_interpretacion}
                        """)

with tab2:
    hist = supabase.table("historial_reportes").select("*").execute().data
    if hist:
        df = pd.DataFrame(hist)
        st.dataframe(df)
        st.download_button("Descargar Excel", df.to_csv(index=False).encode('utf-8'), "BioCore_Audit.csv")
