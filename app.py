import streamlit as st
import ee
import folium
from streamlit_folium import folium_static
import json

# --- 1. CONFIGURACIÓN DE PERFILES (Debe ir al inicio para evitar NameError) ---
if 'PERFILES' not in st.session_state:
    st.session_state.PERFILES = {
        "HUMEDAL": {"cat": "Ley 21.202", "ve7": "Refugio fauna silvestre.", "clima": "Balance hídrico real.", "u": 0.1, "sensor": "nd"},
        "MINERIA": {"cat": "Formulario F-30", "ve7": "Estabilidad sustrato.", "clima": "Control de aridez.", "u": 0.45, "sensor": "sw"},
        "GLACIAR": {"cat": "RCA Pascua Lama", "ve7": "Protección ecosistemas altoandinos.", "clima": "Vigilancia albedo.", "u": 0.35, "sensor": "mn"},
        "BOSQUE": {"cat": "Ley 20.283", "ve7": "Conectividad biológica.", "clima": "Estrés biomasa.", "u": 0.20, "sensor": "sa"},
        "INDUSTRIAL": {"cat": "Formulario F-22", "ve7": "Control escorrentía.", "clima": "Pluviosidad industrial.", "u": 0.50, "sensor": "sw"}
    }

# --- 2. FUNCIÓN PARA MAPA ---
def generar_mapa(coords_json):
    coords = json.loads(coords_json)
    # Calcular centro para el mapa
    lat_center = coords[0][0][1]
    lon_center = coords[0][0][0]
    
    m = folium.Map(location=[lat_center, lon_center], zoom_start=15, tiles='CartoDB satellite')
    folium.Polygon(locations=[(p[1], p[0]) for p in coords[0]], color="yellow", weight=2, fill=True, fill_opacity=0.2).add_to(m)
    return m

# --- 3. INTERFAZ POR PESTAÑAS ---
tab1, tab2, tab3 = st.tabs(["🚀 VIGILANCIA", "📊 HISTORIAL", "📄 CONFIGURACIÓN"])

with tab1:
    st.subheader("Panel de Control Espacial")
    # Asumimos que 'proyectos' viene de tu consulta a Supabase
    for p in proyectos:
        with st.expander(f"📍 {p['Proyecto']} ({p.get('Tipo')})"):
            col_map, col_info = st.columns([2, 1])
            
            with col_map:
                # Renderizamos el polígono en lugar del texto del reporte
                folium_static(generar_mapa(p['Coordenadas']), width=500, height=300)
            
            with col_info:
                st.write("**Estatus Celular:**")
                if st.button(f"Ejecutar Auditoría", key=f"btn_{p['Proyecto']}"):
                    # Aquí llamas a tu motor de GEE y enviartelegram()
                    st.success("Enviado a Telegram")

with tab2:
    st.subheader("Historial de Alertas")
    # Visualización de logs previos
    st.info("Sincronizando con base de datos de auditorías...")

with tab3:
    st.subheader("Ajustes Técnicos de Perfiles")
    # Usamos st.session_state.PERFILES para que los cambios persistan
    tipo_edit = st.selectbox("Perfil a Editar", list(st.session_state.PERFILES.keys()))
    
    with st.form("edit_perfil"):
        u_val = st.number_input("Umbral Crítico", value=st.session_state.PERFILES[tipo_edit]['u'])
        cat_val = st.text_input("Referencia Legal", value=st.session_state.PERFILES[tipo_edit]['cat'])
        ve7_val = st.text_area("Explicación VE-7", value=st.session_state.PERFILES[tipo_edit]['ve7'])
        
        if st.form_submit_state("Guardar cambios"):
            st.session_state.PERFILES[tipo_edit]['u'] = u_val
            st.session_state.PERFILES[tipo_edit]['cat'] = cat_val
            st.session_state.PERFILES[tipo_edit]['ve7'] = ve7_val
            st.rerun()
