import streamlit as st
import json
import ee
import requests
import pandas as pd
from datetime import datetime
from supabase import create_client, Client
from googleapiclient.discovery import build
from google.oauth2 import service_account

# --- 1. CONFIGURACIÓN E INICIO ---
st.set_page_config(page_title="BioCore Intelligence V5", layout="wide", page_icon="🛰️")

def check_password():
    if "password_correct" not in st.session_state:
        st.title("🛰️ BioCore V5 - Acceso")
        u = st.text_input("Usuario").lower().strip()
        p = st.text_input("Contraseña", type="password").strip()
        if st.button("Entrar"):
            if u == st.secrets["auth"]["user"].lower().strip() and p == str(st.secrets["auth"]["password"]).strip():
                st.session_state["password_correct"] = True
                st.rerun()
            else:
                st.error("Credenciales incorrectas")
        return False
    return True

if check_password():
    # --- 2. CONEXIONES ---
    try:
        supabase: Client = create_client(st.secrets["connections"]["supabase"]["url"], st.secrets["connections"]["supabase"]["key"])
        creds_info = json.loads(st.secrets["gee"]["json"])
        if not ee.data.is_initialized():
            ee.Initialize(ee.ServiceAccountCredentials(creds_info['client_email'], key_data=creds_info['private_key']))
    except Exception as e:
        st.error(f"Error de conexión: {e}")
        st.stop()

    # --- 3. PESTAÑAS DE LA APP ---
    tab1, tab2 = st.tabs(["🌍 Monitoreo en Tiempo Real", "➕ Registro de Nuevos Clientes"])

    # --- PESTAÑA DE REGISTRO (GESTIÓN DE USUARIOS) ---
    with tab2:
        st.header("📝 Ingreso de Clientes al Ecosistema BioCore")
        st.info("Completa este formulario para que el satélite comience a rastrear el nuevo polígono.")
        
        with st.form("form_registro", clear_on_submit=True):
            col1, col2 = st.columns(2)
            nombre_proy = col1.text_input("Nombre del Proyecto / Cliente")
            tipo_proy = col2.selectbox("Tipo de Monitoreo", ["HUMEDAL", "MINERIA"])
            
            coords_raw = st.text_area("Coordenadas (Pega el JSON de puntos aquí)")
            
            col3, col4 = st.columns(2)
            telegram_id = col3.text_input("ID de Telegram (para alertas al celular)")
            sheet_id = col4.text_input("ID de Google Sheet (para base de datos)")
            
            es_glaciar = st.checkbox("¿Requiere monitoreo de criósfera (Glaciares/Nieve)?")
            
            btn_guardar = st.form_submit_button("💾 REGISTRAR CLIENTE")

            if btn_guardar:
                try:
                    # Lógica de auto-cierre de polígono
                    puntos = json.loads(coords_raw)
                    if puntos[0] != puntos[-1]:
                        puntos.append(puntos[0])
                    
                    data_nuevo = {
                        "Proyecto": nombre_proy,
                        "Tipo": tipo_proy,
                        "Coordenadas": json.dumps(puntos),
                        "telegram_id": telegram_id,
                        "sheet_id": sheet_id,
                        "glaciar": es_glaciar
                    }
                    
                    supabase.table("usuarios").insert(data_nuevo).execute()
                    st.success(f"¡{nombre_proy} ha sido integrado correctamente!")
                    st.balloons()
                except Exception as e:
                    st.error(f"Error al registrar: {e}. Revisa el formato de las coordenadas.")

    # --- PESTAÑA DE MONITOREO (VISUALIZACIÓN Y REPORTES) ---
    with tab1:
        st.header("🛰️ Estado Actual de Proyectos")
        
        # Leemos los usuarios que acabas de ingresar desde la App
        res = supabase.table("usuarios").select("*").execute()
        proyectos_activos = res.data
        
        if not proyectos_activos:
            st.warning("No hay clientes registrados aún. Ve a la pestaña de Registro.")
        else:
            for p in proyectos_activos:
                with st.expander(f"📍 {p['Proyecto']} - {p['Tipo']}"):
                    # Aquí va toda tu lógica de índices (SAVI, NDWI, etc.)
                    # El botón de "Enviar Reporte" usará el p['telegram_id'] que ingresaste arriba
                    st.write(f"ID Alertas: `{p['telegram_id']}`")
                    st.write(f"Base de Datos: `{p['sheet_id']}`")
                    
                    if st.button(f"📲 Procesar y Enviar a {p['Proyecto']}"):
                        # (Aquí va la lógica de requests.post a Telegram que ya tenemos)
                        st.success("Reporte enviado al ID de Telegram configurado.")

    with st.sidebar:
        st.image("https://via.placeholder.com/150?text=BioCore", width=100) # O tu logo
        st.write(f"Directora: Loreto Campos")
