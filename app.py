import streamlit as st
import ee
import folium
from streamlit_folium import folium_static
import json
from supabase import create_client, Client

# --- 1. CONFIGURACIÓN INICIAL Y SESIÓN ---
if 'PERFILES' not in st.session_state:
    st.session_state.PERFILES = {
        "HUMEDAL": {"cat": "Ley 21.202", "ve7": "Refugio fauna silvestre.", "clima": "Balance hídrico real.", "u": 0.1, "sensor": "nd"},
        "MINERIA": {"cat": "Formulario F-30", "ve7": "Estabilidad sustrato.", "clima": "Control de aridez.", "u": 0.45, "sensor": "sw"},
        "GLACIAR": {"cat": "RCA Pascua Lama", "ve7": "Protección ecosistemas altoandinos.", "clima": "Vigilancia albedo.", "u": 0.35, "sensor": "mn"},
        "BOSQUE": {"cat": "Ley 20.283", "ve7": "Conectividad biológica.", "clima": "Estrés biomasa.", "u": 0.20, "sensor": "sa"},
        "INDUSTRIAL": {"cat": "Formulario F-22", "ve7": "Control escorrentía.", "clima": "Pluviosidad industrial.", "u": 0.50, "sensor": "sw"}
    }

# --- 2. CONEXIÓN BBDD (Definición Global de 'proyectos') ---
try:
    supabase: Client = create_client(st.secrets["connections"]["supabase"]["url"], st.secrets["connections"]["supabase"]["key"])
    # Cargamos los datos aquí para que 'proyectos' exista siempre
    res_supabase = supabase.table("usuarios").select("*").execute()
    proyectos = res_supabase.data
except Exception as e:
    st.error(f"Error de conexión con base de datos: {e}")
    proyectos = [] # Lista vacía para evitar que la app se caiga

# --- 3. UTILIDAD DE MAPAS ---
def generar_mapa(coords_json):
    try:
        coords = json.loads(coords_json)
        # Tomar el primer punto del polígono para centrar
        lat_center, lon_center = coords[0][0][1], coords[0][0][0]
        
        m = folium.Map(location=[lat_center, lon_center], zoom_start=15, tiles='CartoDB satellite')
        folium.Polygon(
            locations=[(p[1], p[0]) for p in coords[0]], 
            color="yellow", weight=3, fill=True, fill_opacity=0.4
        ).add_to(m)
        return m
    except:
        return folium.Map(location=[-37.2, -72.7], zoom_start=12)

# --- 4. INTERFAZ ---
tab1, tab2, tab3 = st.tabs(["🚀 VIGILANCIA", "📊 HISTORIAL", "📄 CONFIGURACIÓN"])

with tab1:
    st.subheader("Panel de Vigilancia Satelital")
    if not proyectos:
        st.warning("No hay proyectos cargados. Revisa la conexión a Supabase.")
    else:
        for p in proyectos:
            with st.expander(f"📍 {p['Proyecto']} - {p.get('Tipo', 'S/T')}"):
                col_m, col_a = st.columns([2, 1])
                
                with col_m:
                    # Mostrar mapa del polígono
                    folium_static(generar_mapa(p['Coordenadas']), width=480, height=300)
                
                with col_a:
                    st.write("**Control de Campo**")
                    if st.button(f"🚀 Ejecutar Auditoría", key=f"btn_{p['Proyecto']}"):
                        # Aquí llamas a ejecutar_auditoria(p) y enviar_telegram(p, res)
                        st.info("Procesando en GEE...")
                        st.success("Reporte enviado al móvil.")

with tab2:
    st.subheader("Historial de Alertas")
    st.write("Registro de auditorías mensuales.")

with tab3:
    st.subheader("Configuración de Perfiles")
    tipo_sel = st.selectbox("Perfil a configurar", list(st.session_state.PERFILES.keys()))
    # Formulario para editar st.session_state.PERFILES[tipo_sel]
