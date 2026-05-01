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

# --- 2. LÓGICA DE REVISIÓN ---
def aprobar_informe(id_registro):
    """Cambia el estado del informe a 'APROBADO' para que el cliente lo vea."""
    supabase.table("historial_reportes").update({"validado_por_admin": True}).eq("id", id_registro).execute()
    st.success(f"Informe #{id_registro} aprobado y enviado al historial del cliente.")

# --- 3. INTERFAZ ---
tab1, tab2 = st.tabs(["🚀 Vigilancia Activa", "📊 Centro de Revisión y Descarga"])

with tab1:
    proyectos = supabase.table("usuarios").select("*").execute().data
    for p in proyectos:
        st.markdown(f"### 📍 Proyecto: {p['Proyecto']}")
        col_map, col_ops = st.columns([2.5, 1])
        
        with col_map:
            # Mapa directo (usando la función dibujar_mapa_biocore definida anteriormente)
            m_obj = dibujar_mapa_biocore(p['Coordenadas'])
            folium_static(m_obj, width=800, height=450)
            
        with col_ops:
            if st.button("🚀 Generar Nuevo Informe", key=f"gen_{p['Proyecto']}", use_container_width=True):
                with st.spinner("Calculando índices..."):
                    # Aquí llamarías a generar_reporte_total(p)
                    # IMPORTANTE: Al insertar en Supabase, el campo 'validado_por_admin' debe ser False
                    st.info("Informe generado en borrador. Ve a la Pestaña 2 para revisarlo.")

with tab2:
    st.subheader("📋 Gestión de Informes")
    
    # 1. VISTA DE ADMINISTRADOR (TÚ)
    st.markdown("#### 🛠 Zona de Revisión (Solo BioCore)")
    try:
        # Traemos todos los informes pendientes de validación
        pendientes = supabase.table("historial_reportes").select("*").eq("validado_por_admin", False).execute().data
        
        if pendientes:
            for report in pendientes:
                with st.expander(f"📝 Revisar: {report['proyecto']} - {report['created_at'][:10]}"):
                    st.write(f"**SAVI:** {report['savi']} | **Variación:** {report['variacion_porcentual']}%")
                    st.write(f"**Diagnóstico sugerido:** {report['motivo_alerta']}")
                    
                    c1, c2 = st.columns(2)
                    with c1:
                        if st.button("✅ Aprobar y Enviar", key=f"app_{report['id']}"):
                            aprobar_informe(report['id'])
                            st.rerun()
                    with c2:
                        if st.button("🗑️ Descartar", key=f"del_{report['id']}", type="secondary"):
                            supabase.table("historial_reportes").delete().eq("id", report['id']).execute()
                            st.rerun()
        else:
            st.write("No hay informes pendientes de revisión.")
    except:
        st.info("Configura la columna 'validado_por_admin' (boolean) en Supabase.")

    st.divider()

    # 2. VISTA DEL CLIENTE (SOLO DESCARGA)
    st.markdown("#### 📥 Historial para el Cliente")
    # El cliente SOLO ve los que ya fueron aprobados por ti
    aprobados = supabase.table("historial_reportes").select("*").eq("validado_por_admin", True).execute().data
    
    if aprobados:
        df_cliente = pd.DataFrame(aprobados)
        # Mostramos una tabla limpia
        st.dataframe(df_cliente[['created_at', 'proyecto', 'savi', 'variacion_porcentual', 'estado']])
        
        # Botón de descarga solo para lo aprobado
        csv = df_cliente.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Descargar Reporte Consolidado (Excel/CSV)",
            data=csv,
            file_name=f"BioCore_Reporte_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            use_container_width=True
        )
    else:
        st.warning("Aún no hay informes aprobados disponibles para descarga.")
