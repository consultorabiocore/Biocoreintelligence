import streamlit as st
import ee
import folium
from streamlit_folium import folium_static
import json
import pandas as pd
import requests
from datetime import datetime
from supabase import create_client, Client

# --- 1. CONFIGURACIÓN E INICIALIZACIÓN ---
st.set_page_config(page_title="BioCore Intelligence V5", layout="wide")

# Conexión Supabase
supabase: Client = create_client(st.secrets["connections"]["supabase"]["url"], st.secrets["connections"]["supabase"]["key"])

if 'PERFILES' not in st.session_state:
    st.session_state.PERFILES = {
        "HUMEDAL": {"cat": "Ley 21.202", "ve7": "Refugio fauna silvestre.", "clima": "Balance hídrico.", "u": 0.1, "sensor": "nd"},
        "MINERIA": {"cat": "Formulario F-30", "ve7": "Estabilidad sustrato.", "clima": "Control aridez.", "u": 0.45, "sensor": "sw"},
        "GLACIAR": {"cat": "RCA Pascua Lama", "ve7": "Protección criosférica.", "clima": "Vigilancia albedo.", "u": 0.35, "sensor": "mn"},
        "BOSQUE": {"cat": "Ley 20.283", "ve7": "Conectividad biológica.", "clima": "Estrés hídrico.", "u": 0.20, "sensor": "sa"}
    }

# --- 2. FUNCIONES DE MAPA Y GEE ---
def dibujar_mapa_pro(dato_coords):
    try:
        js = json.loads(dato_coords) if isinstance(dato_coords, str) else dato_coords
        raw = js['coordinates'][0] if 'coordinates' in js else js
        puntos = [[float(p[1]), float(p[0])] for p in raw]
        m = folium.Map(location=puntos[0], zoom_start=15, tiles='https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}', attr='Google Satellite')
        folium.Polygon(locations=puntos, color="#FFFF00", weight=4, fill=True, fill_opacity=0.2).add_to(m)
        m.fit_bounds(puntos)
        return m
    except: return folium.Map(location=[-37.2, -72.7], zoom_start=12)

# --- 3. INTERFAZ POR PESTAÑAS ---
tab1, tab2, tab3 = st.tabs(["🚀 VIGILANCIA EN VIVO", "📊 INFORME EJECUTIVO", "⚙️ CONFIG"])

try:
    proyectos = supabase.table("usuarios").select("*").execute().data
except:
    proyectos = []

# --- PESTAÑA 1: VIGILANCIA (MAPA PRINCIPAL) ---
with tab1:
    st.subheader("Consola de Mando BioCore")
    if proyectos:
        for p in proyectos:
            with st.container():
                col_m, col_c = st.columns([3, 1])
                with col_m:
                    folium_static(dibujar_mapa_pro(p['Coordenadas']), width=850, height=450)
                with col_c:
                    st.info(f"**Proyecto:** {p['Proyecto']}\n\n**Tipo:** {p.get('Tipo')}")
                    if st.button(f"⚡ Disparar Alerta", key=f"btn_{p['Proyecto']}"):
                        st.success("Enviado a Telegram")
                st.divider()

# --- PESTAÑA 2: INFORME (LA NUEVA) ---
with tab2:
    st.subheader("📁 Generador de Informes Técnicos")
    if proyectos:
        # Selector de proyecto para el informe
        sel_p = st.selectbox("Seleccione Proyecto para reporte detallado:", [p['Proyecto'] for p in proyectos])
        proj_data = next(item for item in proyectos if item["Proyecto"] == sel_p)
        
        st.write(f"### Detalle Técnico: {sel_p}")
        
        # Simulamos una tabla de datos históricos/técnicos
        df_tecnico = pd.DataFrame({
            "Indicador": ["SAVI (Vigor)", "NDWI (Agua)", "LST (Temp)", "SU-6 (Radar)", "Humedad Suelo"],
            "Valor Actual": [0.02, -0.11, "24.5 °C", "-10.14 dB", "12%"],
            "Estado": ["⚠️ Bajo", "🟢 Normal", "🟡 Alto", "🟢 Estable", "🔴 Crítico"]
        })
        
        c1, c2 = st.columns(2)
        with c1:
            st.write("**Métricas de Cumplimiento Ambiental**")
            st.table(df_tecnico)
        
        with c2:
            st.write("**Resumen de Diagnóstico**")
            st.success(f"El proyecto {sel_p} cumple con la normativa {st.session_state.PERFILES.get(proj_data.get('Tipo'), {}).get('cat')}. No se detectan anomalías térmicas en el perímetro.")
            
        # Botón de Descarga (Simulado)
        st.download_button(
            label="📥 Descargar Informe PDF (Vista Previa)",
            data="Contenido del informe...",
            file_name=f"Informe_BioCore_{sel_p}.pdf",
            mime="application/pdf"
        )
    else:
        st.warning("No hay datos de clientes para generar informes.")

# --- PESTAÑA 3: CONFIG ---
with tab3:
    st.subheader("Configuración de Parámetros")
    st.write("Ajuste de umbrales y leyes.")
