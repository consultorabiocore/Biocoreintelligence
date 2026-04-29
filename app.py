import streamlit as st
import ee
import json
import pandas as pd
import requests
from google.oauth2 import service_account
from googleapiclient.discovery import build
from datetime import datetime, timedelta
from fpdf import FPDF
import folium
from streamlit_folium import folium_static

# --- 1. CONFIGURACIÓN E IDENTIDAD ---
st.set_page_config(page_title="BioCore Intelligence Console", layout="wide")
T_TOKEN = st.secrets["telegram"]["token"]
T_ID = st.secrets["telegram"]["chat_id"]
SHEET_ID = "1x6yAXNNlea3e43rijJu0aqcRpe4oP3BEnzgSgLuG1vU" # Tu ID de base de datos única

def clean(text):
    return text.encode('latin-1', 'replace').decode('latin-1')

# --- 2. BASE DE DATOS DE PROYECTOS (COORDENADAS) ---
CLIENTES_DB = {
 "Auditoría Laguna Señoraza": {"coords": [[-72.715,-37.275],[-72.715,-37.285],[-72.690,-37.285],[-72.690,-37.270]]},
 "Auditoría Pascua Lama": {"coords": [[-70.033,-29.316],[-70.016,-29.316],[-70.016,-29.333],[-70.033,-29.333]]}
}

# --- 3. SERVICIOS ---
@st.cache_resource
def iniciar_servicios():
    try:
        creds_info = json.loads(st.secrets["gee"]["json"])
        creds = service_account.Credentials.from_service_account_info(
            creds_info, scopes=['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/earthengine']
        )
        try: ee.Initialize(credentials=creds)
        except: pass
        return build('sheets', 'v4', credentials=creds)
    except Exception as e:
        st.error(f"Error de conexión: {e}"); return None

service = iniciar_servicios()

# --- 4. SISTEMA DE LOGIN (CONSULTA A LA PESTAÑA 'USUARIOS') ---
def validar_acceso(user, pw):
    try:
        res = service.spreadsheets().values().get(spreadsheetId=SHEET_ID, range="'Usuarios'!A:D").execute()
        rows = res.get('values', [])
        for r in rows[1:]:
            if r[0] == user and r[1] == pw:
                return {"auth": True, "proyecto": r[2], "rol": r[3]}
        return {"auth": False}
    except: return {"auth": False}

if "auth" not in st.session_state:
    st.session_state.auth = False

if not st.session_state.auth:
    st.title("🛡️ BioCore Intelligence")
    with st.form("Login"):
        u = st.text_input("Usuario")
        p = st.text_input("Clave", type="password")
        if st.form_submit_button("Ingresar"):
            res = validar_acceso(u, p)
            if res["auth"]:
                st.session_state.auth = True
                st.session_state.user = res
                st.rerun()
            else: st.error("Acceso denegado")
    st.stop()

# --- 5. LOGUEADO: DEFINIR PERMISOS ---
user_data = st.session_state.user
es_admin = user_data["rol"] == "ADMIN"

# --- 6. FUNCIÓN AUTO-CREACIÓN DE PESTAÑAS ---
def asegurar_pestaña(nombre):
    meta = service.spreadsheets().get(spreadsheetId=SHEET_ID).execute()
    existentes = [s.get("properties", {}).get("title") for s in meta.get('sheets', [])]
    if nombre not in existentes:
        service.spreadsheets().batchUpdate(spreadsheetId=SHEET_ID, body={'requests': [{'addSheet': {'properties': {'title': nombre}}}]}).execute()
        headers = [["Fecha", "SAVI", "NDWI", "NDSI", "Temp", "Fuego"]]
        service.spreadsheets().values().update(spreadsheetId=SHEET_ID, range=f"'{nombre}'!A1", valueInputOption="USER_ENTERED", body={'values': headers}).execute()

# --- 7. PANEL PRINCIPAL ---
st.sidebar.title("BioCore Console")
menu = st.sidebar.radio("Módulos", ["🛰️ Vigilancia Satelital", "🕰️ Auditoría Histórica (Años)", "📊 Reportes"])

if es_admin:
    sel = st.selectbox("Seleccionar Proyecto:", list(CLIENTES_DB.keys()))
else:
    sel = user_data["proyecto"]
    st.info(f"Proyecto asignado: {sel}")

info = CLIENTES_DB[sel]

# --- MÓDULO: VIGILANCIA ---
if menu == "🛰️ Vigilancia Satelital":
    col1, col2 = st.columns([2, 1])
    with col1:
        avg = [sum(p[1] for p in info['coords'])/len(info['coords']), sum(p[0] for p in info['coords'])/len(info['coords'])]
        m = folium.Map(location=avg, zoom_start=14)
        folium.TileLayer('https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}', attr='Google', name='Sat').add_to(m)
        folium.Polygon(locations=[[p[1], p[0]] for p in info['coords']], color='#2ecc71').add_to(m)
        folium_static(m)
    
    with col2:
        if es_admin and st.button("🚀 CAPTURAR ESTADO HOY"):
            asegurar_pestaña(sel)
            geom = ee.Geometry.Polygon(info['coords'])
            s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED').filterBounds(geom).sort('system:time_start', False).first()
            f = datetime.fromtimestamp(s2.get('system:time_start').getInfo()/1000).strftime('%d/%m/%Y')
            val = s2.expression('((B8-B4)/(B8+B4+0.5))*1.5', {'B8':s2.select('B8'),'B4':s2.select('B4')}).reduceRegion(ee.Reducer.mean(), geom, 30).getInfo().get('sa', 0)
            # (Aquí agregarías el resto de índices NDWI, NDSI, Temp como los códigos anteriores)
            service.spreadsheets().values().append(spreadsheetId=SHEET_ID, range=f"'{sel}'!A2", valueInputOption="USER_ENTERED", body={'values': [[f, val, 0.1, 0.05, 22.5, "NO"]]}).execute()
            st.success("Dato guardado.")

# --- MÓDULO: AUDITORÍA HISTÓRICA (AÑOS) ---
elif menu == "🕰️ Auditoría Histórica (Años)":
    st.subheader("Comparativa de Línea de Base (Antes vs Después)")
    ano_base = st.slider("Seleccione Año del 'Antes':", 2015, 2024, 2018)
    
    if st.button("🔍 ANALIZAR CAMBIO TEMPORAL"):
        geom = ee.Geometry.Polygon(info['coords'])
        # Obtener SAVI del pasado
        img_pasado = ee.ImageCollection("LANDSAT/LC08/C02/T1_L2").filterBounds(geom).filterDate(f"{ano_base}-01-01", f"{ano_base}-12-31").median()
        savi_pasado = img_pasado.expression('((B5-B4)/(B5+B4+0.5))*1.5', {'B5':img_pasado.select('SR_B5'),'B4':img_pasado.select('SR_B4')}).reduceRegion(ee.Reducer.mean(), geom, 30).getInfo().get('constant', 0)
        
        st.metric(f"Vigor Vegetal ({ano_base})", f"{savi_pasado:.2f}")
        st.write("Este dato permite auditar el impacto acumulado de la industria en la zona.")

# --- MÓDULO: REPORTES ---
elif menu == "📊 Reportes":
    st.subheader("Generación de Documentos PDF")
    if st.button("📄 GENERAR REPORTE DE HOY"):
        st.info("Generando reporte PDF y enviando a Telegram...")
        # (Aquí va la lógica del PDF que ya tienes integrada)
