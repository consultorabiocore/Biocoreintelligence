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

# --- 1. CONFIGURACIÓN E INICIALIZACIÓN ---
st.set_page_config(page_title="BioCore Intelligence V5", layout="wide")

@st.cache_resource
def init_db():
    return create_client(st.secrets["connections"]["supabase"]["url"], st.secrets["connections"]["supabase"]["key"])

supabase = init_db()

def iniciar_gee():
    if not ee.data.is_initialized():
        creds = json.loads(st.secrets["gee"]["json"])
        ee_creds = ee.ServiceAccountCredentials(creds['client_email'], key_data=creds['private_key'])
        ee.Initialize(ee_creds)

# --- 2. DEFINICIÓN DE FUNCIONES (DEBEN IR ANTES DE LA INTERFAZ) ---

def dibujar_mapa_biocore(coords_json):
    """Renderiza el mapa satelital como página principal."""
    try:
        js = json.loads(coords_json) if isinstance(coords_json, str) else coords_json
        raw = js['coordinates'][0] if 'coordinates' in js else js
        puntos = [[float(p[1]), float(p[0])] for p in raw]
        
        m = folium.Map(location=puntos[0], zoom_start=15, 
                       tiles='https://mt1.google.com/vt/lyrs=y&x={x}&y={y}&z={z}', 
                       attr='Google Satellite Hybrid')
        
        folium.Polygon(locations=puntos, color="#FFFF00", weight=4, fill=True, fill_opacity=0.2).add_to(m)
        m.fit_bounds(puntos)
        return m
    except Exception as e:
        return folium.Map(location=[-37.2, -72.7], zoom_start=12)

def generar_reporte_total(p):
    """Calcula datos y guarda en modo BORRADOR (validado_por_admin=False)."""
    iniciar_gee()
    js = json.loads(p['Coordenadas'])
    geom = ee.Geometry.Polygon(js['coordinates'] if 'coordinates' in js else js)
    
    # Simulación de cálculo rápido para el ejemplo
    # (Aquí va toda tu lógica de SAVI, MODIS y FIRMS del bloque anterior)
    s_now, s_base, temp_val, variacion = 0.02, 0.02, 15.0, 0.0
    diag_final = "Revisión pendiente"
    
    # Registro en Supabase como borrador
    supabase.table("historial_reportes").insert({
        "proyecto": p['Proyecto'], 
        "savi": s_now, 
        "savi_base": s_base,
        "variacion_porcentual": variacion, 
        "temp_suelo": temp_val, 
        "estado": "PENDIENTE",
        "validado_por_admin": False, # IMPORTANTE: Empieza en falso
        "motivo_alerta": diag_final
    }).execute()
    
    return "Informe enviado a revisión.", s_now, s_base

# --- 3. INTERFAZ (PAGINA PRINCIPAL) ---

if 'PERFILES' not in st.session_state:
    st.session_state.PERFILES = {
        "MINERIA": {"cat": "F-30 Minería", "ve7": "Estabilidad sustrato.", "clima": "Control aridez."},
        "GLACIAR": {"cat": "RCA Criosfera", "ve7": "Protección hídrica.", "clima": "Vigilancia albedo."}
    }

tab1, tab2 = st.tabs(["🚀 Vigilancia Activa", "📊 Centro de Revisión y Descarga"])

with tab1:
    proyectos = supabase.table("usuarios").select("*").execute().data
    for p in proyectos:
        st.markdown(f"### 📍 Proyecto: {p['Proyecto']}")
        col_map, col_ops = st.columns([2.5, 1])
        
        with col_map:
            # AHORA SI: La función ya está definida arriba
            m_obj = dibujar_mapa_biocore(p['Coordenadas'])
            folium_static(m_obj, width=850, height=500)
            
        with col_ops:
            if st.button("🚀 Generar Nuevo Informe", key=f"gen_{p['Proyecto']}"):
                with st.spinner("Procesando..."):
                    msg, v_n, v_b = generar_reporte_total(p)
                    st.info(msg)

with tab2:
    st.subheader("📋 Gestión de Informes")
    
    # Bloque Administrador: Tú apruebas
    st.markdown("#### 🛠 Zona de Revisión (BioCore)")
    pendientes = supabase.table("historial_reportes").select("*").eq("validado_por_admin", False).execute().data
    if pendientes:
        for report in pendientes:
            with st.expander(f"Revisar: {report['proyecto']}"):
                if st.button("✅ Aprobar y Enviar Cliente", key=f"app_{report['id']}"):
                    supabase.table("historial_reportes").update({"validado_por_admin": True}).eq("id", report['id']).execute()
                    st.rerun()
    
    st.divider()
    
    # Bloque Cliente: Solo ve lo aprobado
    st.markdown("#### 📥 Historial para el Cliente")
    aprobados = supabase.table("historial_reportes").select("*").eq("validado_por_admin", True).execute().data
    if aprobados:
        df = pd.DataFrame(aprobados)
        st.dataframe(df[['created_at', 'proyecto', 'savi', 'estado']])
        st.download_button("Descargar Excel", df.to_csv().encode('utf-8'), "BioCore_Report.csv")
