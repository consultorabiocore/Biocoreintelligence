import streamlit as st
import json
import ee
import requests
import pandas as pd
from datetime import datetime, timedelta
from supabase import create_client, Client
from googleapiclient.discovery import build
from google.oauth2 import service_account
from streamlit_folium import folium_static
import folium

# --- 1. CONFIGURACIÓN DE PÁGINA ---
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
    # --- 2. CONEXIONES A SERVICIOS ---
    try:
        # Supabase
        supabase: Client = create_client(
            st.secrets["connections"]["supabase"]["url"], 
            st.secrets["connections"]["supabase"]["key"]
        )

        # Google Earth Engine & Sheets
        creds_info = json.loads(st.secrets["gee"]["json"])
        gee_creds = ee.ServiceAccountCredentials(creds_info['client_email'], key_data=creds_info['private_key'])
        if not ee.data.is_initialized():
            ee.Initialize(gee_creds)
        
        sheets_service = build('sheets', 'v4', credentials=service_account.Credentials.from_service_account_info(
            creds_info, scopes=['https://www.googleapis.com/auth/spreadsheets']
        ))
    except Exception as e:
        st.error(f"Error de conexión crítica: {e}")
        st.stop()

    # --- 3. FUNCIONES CORE ---
    def enviar_telegram(m):
        url = f"https://api.telegram.org/bot{st.secrets['telegram']['token']}/sendMessage"
        requests.post(url, data={"chat_id": st.secrets['telegram']['chat_id'], "text": m, "parse_mode": "Markdown"})

    @st.cache_data(ttl=600)
    def obtener_proyectos():
        res = supabase.table("usuarios").select("*").execute()
        return res.data

    # --- 4. INTERFAZ ---
    st.title("🛰️ BioCore V5: Vigilancia Ambiental Especializada")
    tab1, tab2, tab3 = st.tabs(["🌍 Monitoreo y Diagnóstico", "📊 Tendencias Históricas", "🌡️ Riesgo Climático"])

    with st.sidebar:
        st.header("🛰️ Panel de Control")
        btn_ejecutar = st.button("🚀 PROCESAR Y ENVIAR REPORTES", use_container_width=True)
        if st.button("Cerrar Sesión"):
            st.session_state.clear()
            st.rerun()

    proyectos = obtener_proyectos()

    # --- 5. BUCLE DE PROCESAMIENTO TÉCNICO ---
    for proy in proyectos:
        nombre = proy.get('Proyecto', 'Sin Nombre')
        tipo = proy.get('Tipo', 'HUMEDAL') # HUMEDAL o MINERIA
        glaciar = proy.get('glaciar', False)
        sheet_id = proy.get('sheet_id')
        pestana = proy.get('pestana', 'Hoja 1')
        
        coords = json.loads(proy['Coordenadas'])
        poly = ee.Geometry.Polygon(coords)

        # Extracción de Sensores
        s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED').filterBounds(poly).sort('system:time_start', False).first()
        f_rep = datetime.fromtimestamp(s2.get('system:time_start').getInfo()/1000).strftime('%d/%m/%Y')
        
        s1 = ee.ImageCollection('COPERNICUS/S1_GRD').filterBounds(poly).filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV')).sort('system:time_start', False).first()
        sar_val = s1.reduceRegion(ee.Reducer.mean(), poly, 30).getInfo().get('VV', 0)

        # Cálculo de Índices BioCore
        idx = s2.expression({
            'sa': '((B8-B4)/(B8+B4+0.5))*1.5',         # SAVI
            'nd': '(B3-B8)/(B3+B8)',                  # NDWI
            'mn': '(B3-B11)/(B3+B11)',                # NDSI
            'sw': 'B11 / 10000',                      # SWIR
            'clay': 'B11 / B12'                       # Clay Ratio
        }, {
            'B8': s2.select('B8'), 'B4': s2.select('B4'),
            'B3': s2.select('B3'), 'B11': s2.select('B11'), 'B12': s2.select('B12')
        }).reduceRegion(ee.Reducer.mean(), poly, 30).getInfo()

        sa, nd, mn, sw, clay = idx['sa'], idx['nd'], idx['mn'], idx['sw'], idx['clay']
        
        # GEDI y TerraClimate
        try:
            gedi = ee.ImageCollection("LARSE/GEDI/L2A_002").filterBounds(poly).sort('system:time_start', False).first()
            alt = gedi.reduceRegion(ee.Reducer.mean(), poly, 30).getInfo().get('rh98', 1.2)
        except: alt = 1.2
        
        clim = ee.ImageCollection("IDAHO_EPSCOR/TERRACLIMATE").filterBounds(poly).sort('system:time_start', False).first()
        clim_data = clim.reduceRegion(ee.Reducer.mean(), poly, 4638).getInfo()
        defic = abs(float(clim_data.get('pr', 0)) - 100)
        temp = clim_data.get('tmmx', 0) * 0.1

        # --- LÓGICA DE DIAGNÓSTICO ---
        estado_global = "🟢 BAJO CONTROL"
        cat_tipo = "Humedal Urbano / Cuerpo de Agua" if tipo == "HUMEDAL" else "Área Minera / Depósito de Estériles"
        
        if tipo == "HUMEDAL":
            est_su, exp_su = "🛡️ HIDROESTABLE", f"SWIR ({sw:.2f}): Saturación de sustrato óptima."
            if nd < 0.1: 
                estado_global = "🔴 ALERTA TÉCNICA"; diagnostico = "Estrés hídrico crítico detectado."
            else: diagnostico = "Parámetros dentro de la norma legal."
        else:
            est_su = "🛡️ ESTABLE" if sw < 0.45 else "⚠️ REMOCIÓN"
            exp_su = f"SWIR ({sw:.2f}): Reflectancia mineral estable."
            if glaciar and mn < 0.35:
                estado_global = "🔴 ALERTA TÉCNICA"; diagnostico = f"Pérdida de cobertura criosférica (NDSI: {mn:.2f})."
            elif sw > 0.45:
                estado_global = "🔴 ALERTA TÉCNICA"; diagnostico = "Posible movimiento de material no autorizado."
            else: diagnostico = "Sin indicios de intervención antrópica."

        # --- VISUALIZACIÓN ---
        with tab1:
            st.subheader(f"📍 {nombre}")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("SAVI (Vigor)", f"{sa:.2f}")
            c2.metric("Radar (VV)", f"{sar_val:.1f} dB")
            c3.metric("SWIR (Sustrato)", f"{sw:.2f}")
            c4.metric("Estado", estado_global)
            st.write(f"**Diagnóstico:** {diagnostico}")

        with tab2:
            st.subheader(f"Historial Satelital: {nombre}")
            st.line_chart(pd.DataFrame([sa, nd, mn], index=["SAVI", "NDWI", "NDSI"]))

        with tab3:
            st.write(f"**Temperatura:** {temp:.1f}°C | **Déficit Hídrico:** {defic:.1f} mm")

        # --- REPORTES Y SYNC ---
        if btn_ejecutar:
            # Sync Google Sheets
            fila = [[f_rep, sa, nd, mn, sw, clay, defic]]
            sheets_service.spreadsheets().values().append(
                spreadsheetId=sheet_id, range=f"{pestana}!A2", 
                valueInputOption="USER_ENTERED", body={'values': fila}
            ).execute()

            # Reporte Telegram
            reporte = (
                f"🛰 **BIOCORE V5 - REPORTE TÉCNICO**\n"
                f"**PROYECTO: {nombre}**\n"
                f"📅 **Análisis:** {f_rep}\n"
                f"──────────────────\n"
                f"🛡️ **ESTATUS:** {est_su}\n"
                f"🌱 **Vigor (SAVI):** `{sa:.2f}`\n"
                f"📏 **Humedad/Nieve:** `{mn:.2f}`\n"
                f"⚠️ **GLOBAL:** {estado_global}\n"
                f"📝 **Diagnóstico:** {diagnostico}"
            )
            enviar_telegram(reporte)

    with tab1:
        st.divider()
        m = folium.Map(location=[-33.0, -71.0], zoom_start=6)
        for p in proyectos:
            folium.Polygon(locations=[[c[1], c[0]] for c in json.loads(p['Coordenadas'])], popup=p['Proyecto'], color='cyan').add_to(m)
        folium_static(m)

    if btn_ejecutar:
        st.success("Procesamiento completado. Datos sincronizados y reportes enviados.")
        st.balloons()
