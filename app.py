import streamlit as st
import pandas as pd
import re
from st_supabase_connection import SupabaseConnection
import folium
from streamlit_folium import folium_static

# --- CONEXIÓN ---
st_supabase = st.connection("supabase", type=SupabaseConnection)

st.set_page_config(page_title="BioCore Intelligence", layout="wide")

menu = st.sidebar.radio("SISTEMA", ["🛡️ Auditoría", "⚙️ Gestión"])

# --- VISTA DE AUDITORÍA ---
if menu == "🛡️ Auditoría":
    st.title("🛡️ Panel de Vigilancia")
    
    # Consultar clientes de Supabase
    res = st_supabase.table("proyectos").select("*").execute()
    proyectos = res.data
    
    if proyectos:
        nombres = [p['nombre'] for p in proyectos]
        sel = st.selectbox("Seleccione Proyecto:", nombres)
        info = next(p for p in proyectos if p['nombre'] == sel)
        
        st.success(f"Proyecto seleccionado: {info['nombre']}")
        
        # Mapa usando las coordenadas de la DB
        if info['coordenadas']:
            m = folium.Map(location=info['coordenadas'][0], zoom_start=13)
            folium.Polygon(locations=info['coordenadas'], color="#1a3a5a", fill=True).add_to(m)
            folium_static(m)
    else:
        st.info("Aún no hay proyectos registrados en Supabase.")

# --- VISTA DE GESTIÓN (REGISTRO) ---
else:
    st.title("⚙️ Registro de Clientes")
    with st.form("registro_supabase", clear_on_submit=True):
        n = st.text_input("Nombre del Proyecto (Empresa)")
        t = st.selectbox("Ecosistema", ["MINERIA", "HUMEDAL"])
        tid = st.text_input("ID Telegram Cliente")
        sid = st.text_input("Google Sheet ID")
        cor = st.text_area("Coordenadas (Copia y pega desde Google Earth)")
        
        if st.form_submit_button("💾 Guardar en Base de Datos"):
            # Limpieza de coordenadas
            nums = re.findall(r"[-+]?\d*\.\d+|[-+]?\d+", cor)
            coords = [[float(nums[i]), float(nums[i+1])] for i in range(0, len(nums), 2) if i+1 < len(nums)]
            
            if n and coords:
                # INSERTAR EN SUPABASE
                st_supabase.table("proyectos").insert({
                    "nombre": n, 
                    "tipo": t, 
                    "telegram_id": tid, 
                    "sheet_id": sid, 
                    "coordenadas": coords,
                    "umbral": 0.35 if t == "MINERIA" else 0.10
                }).execute()
                st.success(f"¡Proyecto {n} guardado con éxito en la nube!")
                st.balloons()
