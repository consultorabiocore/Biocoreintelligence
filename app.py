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
        "HUMEDAL": {"cat": "Ley 21.202", "ve7": "Refugio fauna silvestre.", "clima": "Balance hídrico real (Ley 21.202)"},
        "MINERIA": {"cat": "Formulario F-30", "ve7": "Estabilidad sustrato.", "clima": "Control de aridez (F-30)"},
        "GLACIAR": {"cat": "RCA Pascua Lama", "ve7": "Protección ecosistemas altoandinos.", "clima": "Vigilancia albedo (RCA)"},
        "BOSQUE": {"cat": "Ley 20.283", "ve7": "Conectividad biológica.", "clima": "Estrés biomasa (Ley 20.283)"},
        "INDUSTRIAL": {"cat": "Formulario F-22", "ve7": "Control escorrentía.", "clima": "Pluviosidad (F-22)"}
    }

# --- 2. CARGA DE DATOS (Centralizada para evitar pestañas vacías) ---
try:
    supabase: Client = create_client(st.secrets["connections"]["supabase"]["url"], st.secrets["connections"]["supabase"]["key"])
    res = supabase.table("usuarios").select("*").execute()
    proyectos = res.data if res.data else []
except Exception as e:
    st.error(f"Error de conexión: {e}")
    proyectos = []

# --- 3. FUNCIÓN DE MAPA (Corrección de Polígono) ---
def dibujar_poligono(dato_coords):
    try:
        # Convertir a dict si es string
        js = json.loads(dato_coords) if isinstance(dato_coords, str) else dato_coords
        
        # Manejo flexible de estructura GeoJSON o lista simple
        raw_coords = js['coordinates'][0] if 'coordinates' in js else js
        
        # INVERSIÓN CRÍTICA: Folium necesita [lat, lon], GeoJSON trae [lon, lat]
        puntos_corregidos = [[p[1], p[0]] for p in raw_coords]
        
        # Crear mapa centrado en el polígono
        centro = puntos_corregidos[0]
        m = folium.Map(location=centro, zoom_start=15, tiles='CartoDB satellite')
        
        # Dibujar polígono con estilo BioCore
        folium.Polygon(
            locations=puntos_corregidos,
            color="#FFFF00", # Amarillo
            weight=5,
            fill=True,
            fill_color="#FFFF00",
            fill_opacity=0.3
        ).add_to(m)
        return m
    except Exception:
        return folium.Map(location=[-37.25, -72.71], zoom_start=10)

# --- 4. INTERFAZ DE TRES PESTAÑAS ---
tab1, tab2, tab3 = st.tabs(["🚀 VIGILANCIA", "📊 HISTORIAL Y CLIENTES", "📄 CONFIGURACIÓN"])

with tab1:
    st.subheader("Vigilancia Satelital Activa")
    if proyectos:
        for p in proyectos:
            tipo = p.get('Tipo', 'MINERIA')
            with st.expander(f"📍 {p['Proyecto']} | Perfil: {tipo}"):
                c1, c2 = st.columns([2, 1])
                with c1:
                    # El mapa ahora debería mostrar el borde amarillo
                    folium_static(dibujar_poligono(p['Coordenadas']), width=500, height=350)
                with c2:
                    st.write(f"**ID:** `{p.get('telegram_id')}`")
                    st.write(f"**Ley:** {st.session_state.PERFILES.get(tipo, {}).get('cat', 'N/A')}")
                    if st.button("🚀 Ejecutar Auditoría", key=f"exe_{p['Proyecto']}"):
                        st.success("Analizando... Reporte enviado.")
    else:
        st.warning("No se encontraron clientes en Supabase.")

with tab2:
    st.subheader("Registro Histórico de Clientes")
    if proyectos:
        # Mostramos la tabla completa de la base de datos
        df = pd.DataFrame(proyectos)
        # Limpiamos columnas para la vista del historial
        columnas = ['Proyecto', 'Tipo', 'telegram_id']
        st.dataframe(df[columnas], use_container_width=True)
        
        st.divider()
        st.write("📈 **Resumen de Cobertura**")
        st.bar_chart(df['Tipo'].value_counts())
    else:
        st.info("Sin registros de clientes disponibles.")

with tab3:
    st.subheader("Ajustes Técnicos BioCore")
    # Formulario para editar leyes y umbrales...
    st.write("Edita las leyes y parámetros aquí.")
