import streamlit as st
import json
import ee
import requests
import pandas as pd
from datetime import datetime
from supabase import create_client, Client
from googleapiclient.discovery import build
from google.oauth2 import service_account

# --- 1. CONFIGURACIÓN ---
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

    # --- 3. INTERFAZ ---
    tab1, tab2 = st.tabs(["🌍 Monitoreo de Proyectos", "➕ Registro de Clientes/Usuarios"])

    # --- PESTAÑA 2: REGISTRO DE USUARIOS (Desde la App) ---
    with tab2:
        st.header("📝 Gestión de Usuarios y Proyectos")
        st.markdown("Desde aquí puedes ingresar nuevos clientes sin tocar Supabase.")
        
        with st.form("registro_directo", clear_on_submit=True):
            col1, col2 = st.columns(2)
            n_proy = col1.text_input("Nombre del Cliente/Proyecto")
            t_proy = col2.selectbox("Tipo", ["HUMEDAL", "MINERIA"])
            
            coords_raw = st.text_area("Coordenadas (JSON)", help="Pega aquí los puntos del polígono")
            
            col3, col4 = st.columns(2)
            t_id = col3.text_input("Telegram ID (Alertas)")
            s_id = col4.text_input("Google Sheet ID (Datos)")
            
            es_glaciar = st.checkbox("Monitoreo de Glaciares activo")
            
            if st.form_submit_button("💾 GUARDAR CLIENTE"):
                try:
                    puntos = json.loads(coords_raw)
                    if puntos[0] != puntos[-1]: puntos.append(puntos[0]) # Auto-cierre
                    
                    data = {
                        "Proyecto": n_proy, "Tipo": t_proy, "Coordenadas": json.dumps(puntos),
                        "telegram_id": t_id, "sheet_id": s_id, "glaciar": es_glaciar
                    }
                    supabase.table("usuarios").insert(data).execute()
                    st.success(f"Proyecto {n_proy} guardado exitosamente.")
                    st.balloons()
                except Exception as e:
                    st.error(f"Error: Verifica que la tabla 'usuarios' esté creada en Supabase. Detalles: {e}")

    # --- PESTAÑA 1: MONITOREO (Lectura de Datos) ---
    with tab1:
        st.header("🛰️ Proyectos Activos")
        try:
            # Intentamos leer la tabla
            res = supabase.table("usuarios").select("*").execute()
            proyectos = res.data
            
            if not proyectos:
                st.info("No hay proyectos registrados. Usa la pestaña de 'Registro'.")
            else:
                for p in proyectos:
                    with st.expander(f"📍 {p['Proyecto']} ({p['Tipo']})"):
                        st.write(f"ID Telegram: `{p['telegram_id']}`")
                        # Aquí sigue tu lógica de Earth Engine...
        except Exception as e:
            st.error("⚠️ La tabla 'usuarios' no existe en Supabase o no tienes acceso.")
            st.info("Para arreglar esto, ve al SQL Editor de Supabase y crea la tabla primero.")
            with st.expander("Ver código SQL para crear la tabla"):
                st.code("""
                CREATE TABLE usuarios (
                    id bigint PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
                    "Proyecto" text,
                    "Tipo" text,
                    "Coordenadas" text,
                    "telegram_id" text,
                    "sheet_id" text,
                    "glaciar" boolean DEFAULT false
                );
                """)

    with st.sidebar:
        st.write(f"Sesión: Loreto Campos")
        if st.button("🔄 Refrescar App"):
            st.rerun()
