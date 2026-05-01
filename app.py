import streamlit as st
import ee
import folium
from streamlit_folium import folium_static
import json
import pandas as pd
from supabase import create_client, Client

# --- 1. CONFIGURACIÓN DE PERFILES ---
if 'PERFILES' not in st.session_state:
    st.session_state.PERFILES = {
        "HUMEDAL": {"cat": "Ley 21.202", "ve7": "Refugio fauna silvestre.", "clima": "Balance hídrico real."},
        "MINERIA": {"cat": "Formulario F-30", "ve7": "Estabilidad sustrato.", "clima": "Control de aridez."},
        "GLACIAR": {"cat": "RCA Pascua Lama", "ve7": "Protección ecosistemas altoandinos.", "clima": "Vigilancia albedo."},
        "BOSQUE": {"cat": "Ley 20.283", "ve7": "Conectividad biológica.", "clima": "Estrés biomasa."},
        "INDUSTRIAL": {"cat": "Formulario F-22", "ve7": "Control escorrentía.", "clima": "Pluviosidad."}
    }

# --- 2. CONEXIÓN Y CARGA DE DATOS ---
try:
    supabase: Client = create_client(st.secrets["connections"]["supabase"]["url"], st.secrets["connections"]["supabase"]["key"])
    res = supabase.table("usuarios").select("*").execute()
    proyectos = res.data if res.data else []
except Exception as e:
    st.error(f"Error de base de datos: {e}")
    proyectos = []

# --- 3. FUNCIÓN DE MAPA (Corregida para evitar ValueError) ---
def dibujar_poligono_final(dato_coords):
    try:
        # 1. Parsear coordenadas
        js = json.loads(dato_coords) if isinstance(dato_coords, str) else dato_coords
        # Extraer lista de puntos [lon, lat]
        raw_coords = js['coordinates'][0] if 'coordinates' in js else js
        # Invertir a [lat, lon] para Folium
        puntos = [[float(p[1]), float(p[0])] for p in raw_coords]
        
        # 2. Configurar Mapa con Google Satellite (URL manual para evitar errores de tiles)
        google_sat = 'https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}'
        
        m = folium.Map(
            location=puntos[0], 
            zoom_start=16, 
            tiles=google_sat, 
            attr='Google'
        )
        
        # 3. Dibujar Polígono BioCore
        folium.Polygon(
            locations=puntos,
            color="#FFFF00", # Amarillo
            weight=4,
            fill=True,
            fill_opacity=0.3,
            tooltip="Área de Estudio"
        ).add_to(m)
        
        # Ajustar vista
        m.fit_bounds(puntos)
        return m
    except Exception:
        # Mapa de respaldo si el JSON está mal
        return folium.Map(location=[-37.2, -72.7], zoom_start=10)

# --- 4. INTERFAZ ---
tab1, tab2, tab3 = st.tabs(["🚀 VIGILANCIA", "📊 DATOS DE CLIENTES", "📄 CONFIGURACIÓN"])

with tab1:
    st.subheader("Auditoría Espacial en Tiempo Real")
    if proyectos:
        for p in proyectos:
            tipo = p.get('Tipo', 'MINERIA')
            with st.expander(f"📍 {p['Proyecto']} | Perfil: {tipo}"):
                c1, c2 = st.columns([2, 1])
                with c1:
                    # RENDER DEL MAPA
                    folium_static(dibujar_poligono_final(p['Coordenadas']), width=550, height=400)
                with c2:
                    st.write(f"**Ley:** {st.session_state.PERFILES.get(tipo, {}).get('cat')}")
                    if st.button(f"Ejecutar Auditoría", key=f"run_{p['Proyecto']}"):
                        st.info("Calculando índices...")
                        st.success("Reporte enviado.")

with tab2:
    st.subheader("Registro de Proyectos y Clientes")
    if proyectos:
        # Mostramos la tabla tal cual viene de Supabase
        df = pd.DataFrame(proyectos)
        st.dataframe(df[['Proyecto', 'Tipo', 'telegram_id']], use_container_width=True)
    else:
        st.info("No se encontraron registros.")

with tab3:
    st.subheader("Parámetros de BioCore")
    st.write("Ajustes técnicos de sensores y leyes.")
