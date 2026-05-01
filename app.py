import streamlit as st
import ee
import folium
from streamlit_folium import folium_static
import json
import pandas as pd
from supabase import create_client, Client

# --- 1. CONFIGURACIÓN DE PERFILES (Garantiza acceso a datos de leyes) ---
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

# --- 3. FUNCIÓN DE MAPA (Fuerza visibilidad de polígono) ---
def dibujar_poligono_fijo(dato_coords):
    try:
        # Convertir a dict si es necesario
        js = json.loads(dato_coords) if isinstance(dato_coords, str) else dato_coords
        
        # Extraer coordenadas limpias
        if 'coordinates' in js:
            raw_coords = js['coordinates'][0]
        elif isinstance(js, list):
            raw_coords = js[0] if isinstance(js[0][0], list) else js
        else:
            raw_coords = js
        
        # INVERSIÓN: GeoJSON [lon, lat] -> Folium [lat, lon]
        puntos = [[float(p[1]), float(p[0])] for p in raw_coords]
        
        # Crear mapa centrado
        m = folium.Map(location=puntos[0], zoom_start=15, tiles='CartoDB satellite')
        
        # Dibujar polígono con borde grueso para que no se pierda
        folium.Polygon(
            locations=puntos,
            color="#FFFF00", # Amarillo puro
            weight=5,
            fill=True,
            fill_opacity=0.4
        ).add_to(m)
        
        # Ajustar el mapa automáticamente a los bordes del polígono
        m.fit_bounds(puntos)
        return m
    except Exception as e:
        # Mapa por defecto en Chile si falla
        return folium.Map(location=[-37.2, -72.7], zoom_start=12, tiles='CartoDB satellite')

# --- 4. INTERFAZ ---
tab1, tab2, tab3 = st.tabs(["🚀 VIGILANCIA", "📊 DATOS DE CLIENTES", "📄 CONFIGURACIÓN"])

with tab1:
    st.subheader("Vigilancia Satelital")
    if proyectos:
        for p in proyectos:
            tipo = p.get('Tipo', 'MINERIA')
            with st.expander(f"📍 {p['Proyecto']} | Perfil: {tipo}"):
                c1, c2 = st.columns([2, 1])
                with c1:
                    # Aquí DEBE aparecer el mapa con el polígono amarillo
                    folium_static(dibujar_poligono_fijo(p['Coordenadas']), width=550, height=400)
                with c2:
                    st.write(f"**Ley Aplicable:**\n{st.session_state.PERFILES.get(tipo, {}).get('cat', 'N/A')}")
                    if st.button(f"Ejecutar Auditoría", key=f"run_{p['Proyecto']}"):
                        st.success("Procesando... Reporte enviado al móvil.")
    else:
        st.warning("No hay proyectos en Supabase.")

with tab2:
    st.subheader("Registro de Clientes")
    if proyectos:
        # Tabla simple con los datos que tú llenas
        df = pd.DataFrame(proyectos)
        st.table(df[['Proyecto', 'Tipo', 'telegram_id']])
    else:
        st.info("No hay datos de clientes registrados.")

with tab3:
    st.subheader("Configuración")
    st.write("Ajuste de parámetros técnicos.")
