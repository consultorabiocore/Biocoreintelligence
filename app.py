import streamlit as st
import ee
import folium
from streamlit_folium import folium_static
import json
import pandas as pd
from supabase import create_client, Client

# --- 1. CONFIGURACIÓN DE PERFILES (Asegura que VE-7 y Clima sean correctos) ---
if 'PERFILES' not in st.session_state:
    st.session_state.PERFILES = {
        "HUMEDAL": {"cat": "Ley 21.202", "ve7": "Refugio fauna silvestre.", "clima": "Balance hídrico real (Ley 21.202)"},
        "MINERIA": {"cat": "Formulario F-30", "ve7": "Estabilidad sustrato.", "clima": "Control de aridez (F-30)"},
        "GLACIAR": {"cat": "RCA Pascua Lama", "ve7": "Protección ecosistemas altoandinos.", "clima": "Vigilancia albedo (RCA)"},
        "BOSQUE": {"cat": "Ley 20.283", "ve7": "Conectividad biológica.", "clima": "Estrés biomasa (Ley 20.283)"},
        "INDUSTRIAL": {"cat": "Formulario F-22", "ve7": "Control escorrentía.", "clima": "Pluviosidad (F-22)"}
    }

# --- 2. CARGA DE DATOS DESDE SUPABASE ---
try:
    supabase: Client = create_client(st.secrets["connections"]["supabase"]["url"], st.secrets["connections"]["supabase"]["key"])
    res = supabase.table("usuarios").select("*").execute()
    proyectos = res.data
except Exception as e:
    st.error(f"Error de base de datos: {e}")
    proyectos = []

# --- 3. FUNCIÓN DE MAPA CORREGIDA (Para ver el polígono) ---
def dibujar_poligono(coords_json):
    try:
        # El GeoJSON suele venir como string o dict; nos aseguramos de que sea dict
        data = json.loads(coords_json) if isinstance(coords_json, str) else coords_json
        
        # Extraemos coordenadas: [ [ [lon, lat], [lon, lat] ... ] ]
        # Folium usa [lat, lon], así que invertimos el orden
        puntos = [(p[1], p[0]) for p in data['coordinates'][0]]
        
        # Centramos el mapa en el primer punto
        m = folium.Map(location=puntos[0], zoom_start=15, tiles='CartoDB satellite')
        
        # Dibujamos el polígono con bordes visibles
        folium.Polygon(
            locations=puntos,
            color="#FFFF00", # Amarillo BioCore
            weight=4,
            fill=True,
            fill_color="#FFFF00",
            fill_opacity=0.3
        ).add_to(m)
        return m
    except Exception as e:
        return folium.Map(location=[-37.2, -72.7], zoom_start=10)

# --- 4. INTERFAZ ---
tab1, tab2, tab3 = st.tabs(["🚀 VIGILANCIA", "📊 HISTORIAL CLIENTES", "📄 CONFIGURACIÓN"])

with tab1:
    st.subheader("Panel de Control Espacial")
    if proyectos:
        for p in proyectos:
            # Mostramos el Tipo de Proyecto que tú llenas en Supabase
            tipo_display = p.get('Tipo', 'No definido')
            with st.expander(f"📍 {p['Proyecto']} | Tipo: {tipo_display}"):
                col_m, col_b = st.columns([2, 1])
                
                with col_m:
                    # Aquí se renderiza el polígono
                    folium_static(dibujar_poligono(p['Coordenadas']), width=500, height=350)
                
                with col_b:
                    st.write(f"**Cliente:** {p.get('Proyecto')}")
                    st.write(f"**Categoría:** {tipo_display}")
                    if st.button("Ejecutar Auditoría", key=f"btn_{p['Proyecto']}"):
                        st.info("Procesando en GEE y enviando a Telegram...")
    else:
        st.warning("No hay proyectos en la base de datos.")

with tab2:
    st.subheader("Base de Datos de Clientes")
    if proyectos:
        # Convertimos a DataFrame para que se vea como una tabla limpia
        df = pd.DataFrame(proyectos)
        # Seleccionamos solo las columnas importantes
        cols_mostrar = ['Proyecto', 'Tipo', 'telegram_id']
        st.table(df[cols_mostrar]) 
    else:
        st.info("No hay registros históricos aún.")

with tab3:
    st.subheader("Ajustes de Perfiles")
    # (Código de configuración de umbrales...)
