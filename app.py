import streamlit as st
import json
import ee
import requests
import pandas as pd
from datetime import datetime
from supabase import create_client, Client
from googleapiclient.discovery import build
from google.oauth2 import service_account
from streamlit_folium import folium_static
import folium

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
        sheets = build('sheets', 'v4', credentials=service_account.Credentials.from_service_account_info(creds_info, scopes=['https://www.googleapis.com/auth/spreadsheets']))
    except Exception as e:
        st.error(f"Error de conexión: {e}")
        st.stop()

    # --- 3. PESTAÑAS ---
    tab1, tab2, tab3 = st.tabs(["🌍 Monitoreo y Diagnóstico", "➕ Registro de Clientes", "🌡️ Clima"])

    # --- PESTAÑA 2: REGISTRO DE CLIENTES ---
    with tab2:
        st.header("📝 Registro de Nuevo Proyecto BioCore")
        with st.form("registro_p"):
            c1, c2 = st.columns(2)
            n_proy = c1.text_input("Nombre del Proyecto")
            t_proy = c2.selectbox("Tipo de Proyecto", ["HUMEDAL", "MINERIA"])
            
            coords_raw = st.text_area("Coordenadas (JSON)")
            
            c3, c4 = st.columns(2)
            s_id = c3.text_input("Google Sheet ID")
            t_id = c4.text_input("Telegram Chat ID", value=st.secrets["telegram"]["chat_id"])
            
            es_glaciar = st.checkbox("¿Contiene áreas de Glaciar/Nieve?")
            
            if st.form_submit_button("💾 Guardar en Base de Datos"):
                try:
                    c_list = json.loads(coords_raw)
                    if c_list[0] != c_list[-1]: c_list.append(c_list[0]) # Auto-cierre
                    
                    supabase.table("usuarios").insert({
                        "Proyecto": n_proy, "Tipo": t_proy, "Coordenadas": json.dumps(c_list),
                        "glaciar": es_glaciar, "sheet_id": s_id, "telegram_id": t_id
                    }).execute()
                    st.success("Proyecto registrado correctamente.")
                except Exception as e: st.error(f"Error: {e}")

    # --- PESTAÑA 1: PROCESAMIENTO Y REPORTES ---
    with tab1:
        res = supabase.table("usuarios").select("*").execute()
        for proy in res.data:
            nombre = proy['Proyecto']
            tipo = proy['Tipo']
            t_id_dest = proy.get('telegram_id', st.secrets["telegram"]["chat_id"])
            poly = ee.Geometry.Polygon(json.loads(proy['Coordenadas']))

            # Sensores e Índices
            s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED').filterBounds(poly).sort('system:time_start', False).first()
            f_rep = datetime.fromtimestamp(s2.get('system:time_start').getInfo()/1000).strftime('%d/%m/%Y')
            
            idx = s2.expression({
                'sa': '((B8-B4)/(B8+B4+0.5))*1.5', 'nd': '(B3-B8)/(B3+B8)', 'sw': 'B11/10000'
            }, {'B8':s2.select('B8'),'B4':s2.select('B4'),'B3':s2.select('B3'),'B11':s2.select('B11')}).reduceRegion(ee.Reducer.mean(), poly, 30).getInfo()

            # Lógica BioCore
            estado = "🟢 CONTROLADO"
            if tipo == "HUMEDAL":
                diag = "Hidroestabilidad normal."
                if idx['nd'] < 0.1: estado, diag = "🔴 ALERTA", "Déficit hídrico en cubeta."
            else:
                diag = "Estabilidad de sustrato."
                if idx['sw'] > 0.45: estado, diag = "🔴 ALERTA", "Remoción de estériles detectada."

            st.subheader(f"📍 {nombre} ({tipo})")
            st.metric("Estado", estado, delta=diag)

            if st.button(f"📲 Enviar Reporte: {nombre}"):
                msg = f"🛰 **BIOCORE V5**\n{nombre}\n📅 {f_rep}\n🌱 SAVI: {idx['sa']:.2f}\n✅ {estado}\n📝 {diag}"
                requests.post(f"https://api.telegram.org/bot{st.secrets['telegram']['token']}/sendMessage", 
                             data={"chat_id": t_id_dest, "text": msg, "parse_mode": "Markdown"})
                st.toast(f"Enviado a ID: {t_id_dest}")
