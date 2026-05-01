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
def generar_reporte_total(p):
    # 1. Definición de perfiles (4 espacios de sangría)
    PERFILES = {
        "MINERIA": {"cat": "RCA Minería (F-30)", "ve7": "Estabilidad de taludes.", "clima": "Protocolo extremos."},
        "GLACIAR": {"cat": "RCA Criosfera", "ve7": "Balance de masa.", "clima": "Ley de Glaciares."},
        "BOSQUE": {"cat": "Ley 20.283", "ve7": "Vigilancia regeneración.", "clima": "Prevención incendios."}
    }
    
    tipo = p.get('Tipo', 'MINERIA')
    d = PERFILES.get(tipo, PERFILES["MINERIA"])

    # 2. CARGA DE GEOMETRÍA (Alineado con el código de arriba)
    try:
        raw_geom = p.get('Coordenadas')
        
        if raw_geom is None:
            return f"Error: La columna 'Coordenadas' está vacía para {p.get('Proyecto')}.", 0, 0

        if isinstance(raw_geom, str):
            import json
            try:
                raw_geom = json.loads(raw_geom)
            except:
                raw_geom = eval(raw_geom) 

        if isinstance(raw_geom, list):
            geom = ee.Geometry.Polygon(raw_geom)
        else:
            return "Error: El formato en 'Coordenadas' no es una lista válida.", 0, 0

    except Exception as e:
        return f"Error al procesar Coordenadas: {str(e)}", 0, 0

        # 2. Convertir a Geometría de Earth Engine
        # Si es una lista de listas [[lon, lat], [lon, lat]...]
        if isinstance(raw_geom, list):
            # Verificamos si es una lista simple o anidada
            if isinstance(raw_geom[0], list):
                geom = ee.Geometry.Polygon(raw_geom)
            else:
                # Si por error solo pusieron un punto [lon, lat], creamos un buffer
                geom = ee.Geometry.Point(raw_geom).buffer(1000).bounds()
        else:
            return "Error: El formato en 'Coordenadas' no es una lista válida.", 0, 0

    except Exception as e:
        return f"Error al procesar Coordenadas: {str(e)}", 0, 0
def dibujar_mapa_biocore(coordenadas):
    """
    Crea un mapa centrado en el polígono del proyecto usando Folium.
    """
    try:
        # 1. Procesar coordenadas (por si vienen como texto)
        if isinstance(coordenadas, str):
            import json
            coordenadas = json.loads(coordenadas)
            
        # 2. Calcular el centro del mapa (promedio de lat/lon)
        lons = [c[0] for c in coordenadas]
        lats = [c[1] for c in coordenadas]
        centro = [sum(lats)/len(lats), sum(lons)/len(lons)]
        
        # 3. Crear el mapa base (Satélite)
        m = folium.Map(
            location=centro, 
            zoom_start=13, 
            tiles='https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}',
            attr='Google Satellite'
        )
        
        # 4. Dibujar el polígono del proyecto
        folium.Polygon(
            locations=[[c[1], c[0]] for c in coordenadas], # Folium usa [Lat, Lon]
            color="cyan",
            weight=2,
            fill=True,
            fill_opacity=0.2
        ).add_to(m)
        
        return m
    except Exception as e:
        st.error(f"No se pudo generar el mapa: {e}")
        return folium.Map(location=[-33.45, -70.66], zoom_start=4) # Mapa de emergencia (Chile)

# --- 3. MOTOR DE REPORTE COMPLETO ---
def generar_reporte_total(p):
    # 1. Diagnóstico Inicial (Esto va PRIMERO)
    st.write(f"🔍 Revisando datos de: {p.get('Proyecto')}")
    st.write("Dato en columna 'Coordenadas':", p.get('Coordenadas'))
    print(f"DEBUG: Columnas disponibles: {list(p.keys())}")

    # 2. Definición de perfiles
    PERFILES = {
        "MINERIA": {"cat": "RCA Minería (F-30)", "ve7": "Estabilidad de taludes.", "clima": "Protocolo extremos."},
        "GLACIAR": {"cat": "RCA Criosfera", "ve7": "Balance de masa.", "clima": "Ley de Glaciares."},
        "BOSQUE": {"cat": "Ley 20.283", "ve7": "Vigilancia regeneración.", "clima": "Prevención incendios."}
    }
    
    tipo = p.get('Tipo', 'MINERIA')
    d = PERFILES.get(tipo, PERFILES["MINERIA"])

    # 2. CARGA DE GEOMETRÍA (Ajuste según Supabase)
    # --- B. CARGA DE GEOMETRÍA (Buscador Universal) ---
    try:
        # 1. Buscamos el dato en las columnas más probables
        raw_geom = p.get('geom') or p.get('geometry') or p.get('geojson') or p.get('coords')
        
        if raw_geom is None:
            # Si no encuentra nada, te dirá qué columnas SÍ existen para que corrijas el nombre
            columnas_detectadas = ", ".join(p.keys())
            return f"Error: No hay datos espaciales. Columnas encontradas: [{columnas_detectadas}]", 0, 0

        # 2. Si el dato es un String (texto), lo convertimos a lista/diccionario
        if isinstance(raw_geom, str):
            import json
            raw_geom = json.loads(raw_geom)

        # 3. Identificamos el formato (GeoJSON o Lista simple)
        if isinstance(raw_geom, dict) and 'coordinates' in raw_geom:
            # Formato GeoJSON estándar
            coords = raw_geom['coordinates'][0]
            geom = ee.Geometry.Polygon(coords)
        elif isinstance(raw_geom, list):
            # Formato Lista de Listas [[lon, lat], ...]
            geom = ee.Geometry.Polygon(raw_geom)
        else:
            return f"Error: El formato de geometría en {p['Proyecto']} no es compatible.", 0, 0

    except Exception as e:
        return f"Error crítico al procesar coordenadas: {str(e)}", 0, 0

    # 3. Llamada a Sentinel-2
    s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')\
           .filterBounds(geom)\
           .sort('system:time_start', False)\
           .first()
    
        # --- A. Datos Satelitales (Óptico, Radar, Clima) ---
    s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED').filterBounds(geom).sort('system:time_start', False).first()
    f_rep = datetime.fromtimestamp(s2.get('system:time_start').getInfo()/1000).strftime('%d/%m/%Y')
    
    # 1. Cargar Radar Sentinel-1 (VV) para rugosidad
    s1 = ee.ImageCollection('COPERNICUS/S1_GRD').filterBounds(geom).filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV')).sort('system:time_start', False).first()
    radar_val = s1.select('VV')

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
        # --- E. CONSTRUCCIÓN DEL MENSAJE FINAL ---
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
