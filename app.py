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
    s_actual = float(idx.get('sa', 0))
    s_base = float(idx_base.get('sa', 0.001)) # Evitar división por cero
    variacion = ((s_actual - s_base) / s_base) * 100
    
    # 4. DETERMINAR ESTADO GLOBAL
    umbral = -15 if d['cat'] == "GLACIAR" else -10
    est_global = "🔴 ALERTA CRÍTICA" if variacion < umbral else "🟢 BAJO CONTROL"

    # --- AHORA VIENEN TUS INTERPRETACIONES (El código que ya tienes) ---
    # if variacion < -15: ...
    # if v_ndsi > 0.4: ...


    # 0. Interpretación SAVI (Vigor Vegetal) - ¡ESTA FALTA EN TU CÓDIGO!
    if variacion < -15:
        exp_savi = "Se observa una disminución significativa en el vigor vegetal, indicando posible intervención o estrés."
    elif variacion > 5:
        exp_savi = "El vigor vegetal muestra una recuperación positiva respecto a la línea base."
    else:
        exp_savi = "La cobertura vegetal se mantiene estable y saludable respecto al registro histórico."

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

    # --- E. CONSTRUCCIÓN DEL MENSAJE FINAL (TELEGRAM) ---
      # --- F. CIERRE Y RETORNO ---
        
        # Aseguramos que v_savi y v_clay existan para el mensaje
        v_savi = s_actual 
        v_clay = float(idx.get('clay', 0))
    texto_final = (
        f"🛰 **REPORTE DE VIGILANCIA AMBIENTAL - BIOCORE**\n"
        f"**PROYECTO:** {p['Proyecto']}\n"
        f"📅 **Análisis:** {f_rep} | **Línea Base:** {anio_base}\n"
        f"──────────────────\n"
        f"❄️ **ESTADO DE CRIÓSFERA (NDSI):**\n"
        f"└ Cobertura Actual: `{v_ndsi:.3f}`\n"
        f"└ **Análisis:** {exp_snow}\n\n"
        f"📡 **MONITOREO RADAR (Sentinel-1):**\n"
        f"└ Retrodispersión VV: `{v_radar:.2f} dB`\n"
        f"└ **Análisis:** {exp_radar}\n\n"
        f"🛡️ **INTEGRIDAD DEL TERRENO (SU-6):**\n"
        f"└ Humedad (SWIR): `{v_swir:.2f}` | Arcillas: `{v_clay:.2f}`\n"
        f"└ **Análisis:** {exp_swir}\n\n"
        f"🌱 **SALUD VEGETAL (SAVI):**\n"
        f"└ Vigor Actual: `{v_savi:.3f}` | Base: `{s_base:.3f}`\n"
        f"└ Variación: `{variacion:.1f}%` respecto al original.\n"
        f"└ **Análisis:** {exp_savi}\n\n"
        f"⚠️ **RIESGO CLIMÁTICO:**\n"
        f"└ Temperatura: `{temp_val:.1f}°C` | Incendios: {alerta_incendio}\n"
        f"──────────────────\n"
        f"✅ **ESTADO GLOBAL:** {est_global}\n"
        f"📝 **CONCLUSIÓN FINAL:** {conclusion_final}"
    )
            # El retorno triple que espera tu interfaz en Streamlit
        return texto_final, s_actual, s_base

    except Exception as e:
        # Un seguro por si algo falla en el procesamiento numérico
        return f"❌ Error en el procesamiento de datos: {str(e)}", 0, 0
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
                        txt, v_now, v_base = generar_reporte_total(p)
                        requests.post(f"https://api.telegram.org/bot{st.secrets['telegram']['token']}/sendMessage", 
                                     data={"chat_id": p['telegram_id'], "text": txt, "parse_mode": "Markdown"})
                        st.success("¡Enviado a Telegram!")
                        # Gráfico comparativo
                        fig = go.Figure(data=[
                            go.Bar(name='Línea Base', x=['Vigor'], y=[v_base]),
                            go.Bar(name='Actual', x=['Vigor'], y=[v_now])
                        ])
                        st.plotly_chart(fig, use_container_width=True)

with tab2:
    hist = supabase.table("historial_reportes").select("*").execute().data
    if hist:
        df = pd.DataFrame(hist)
        st.dataframe(df)
        st.download_button("Descargar Excel", df.to_csv(index=False).encode('utf-8'), "BioCore_Audit.csv")
