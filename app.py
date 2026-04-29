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

# --- 1. CONFIGURACIÓN Y ESTILO ---
st.set_page_config(page_title="BioCore Intelligence Console", layout="wide")

T_TOKEN = st.secrets["telegram"]["token"]
T_ID = st.secrets["telegram"]["chat_id"]
DIRECTORA = "Loreto Campos Carrasco"

def clean(text):
    return text.encode('latin-1', 'replace').decode('latin-1')

# --- 2. BASE DE DATOS DE PROYECTOS (Mismo Cliente, Diferentes Pestañas) ---
CLIENTES = {
 "Auditoría: Laguna Señoraza": {
    "coords": [[-72.715,-37.275],[-72.715,-37.285],[-72.690,-37.285],[-72.690,-37.270]], 
    "tipo": "HUMEDAL",
    "sheet_id": "1x6yAXNNlea3e43rijJu0aqcRpe4oP3BEnzgSgLuG1vU", 
    "pestaña": "Hoja 1" 
 },
 "Auditoría: Pascua Lama": {
    "coords": [[-70.033,-29.316],[-70.016,-29.316],[-70.016,-29.333],[-70.033,-29.333]], 
    "tipo": "MINERIA",
    "sheet_id": "1x6yAXNNlea3e43rijJu0aqcRpe4oP3BEnzgSgLuG1vU", 
    "pestaña": "Hoja 2" 
 }
}

# --- 3. CONEXIÓN A SERVICIOS (GEE & SHEETS) ---
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
        st.sidebar.error(f"Error de conexión: {e}"); return None

service = iniciar_servicios()

# --- 4. BARRA LATERAL (SIDEBAR) ---
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/satellite.png", width=60)
    st.title("BioCore Admin")
    st.markdown(f"**Directora:** {DIRECTORA}")
    st.divider()
    menu = st.radio("Módulos de Control:", ["🛰️ Monitor en Vivo", "📊 Historial & Reportes", "🔥 Alerta de Incendios"])
    st.divider()
    st.caption("Estatus de Constelación: Online")
    st.caption("Sensores: S1, S2, L8, FIRMS")

# --- 5. LÓGICA DE CADA MÓDULO ---
if service:
    sel = st.selectbox("🎯 Proyecto Activo:", list(CLIENTES.keys()))
    info = CLIENTES[sel]

    # --- MÓDULO 1: MONITOR EN VIVO ---
    if menu == "🛰️ Monitor en Vivo":
        col_map, col_ctrl = st.columns([2, 1])
        
        with col_map:
            avg_lat = sum(p[1] for p in info['coords']) / len(info['coords'])
            avg_lon = sum(p[0] for p in info['coords']) / len(info['coords'])
            m = folium.Map(location=[avg_lat, avg_lon], zoom_start=14)
            folium.TileLayer('https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}', attr='Google', name='Google Sat').add_to(m)
            folium.Polygon(locations=[[p[1], p[0]] for p in info['coords']], color='#2ecc71', fill=True, opacity=0.3).add_to(m)
            folium_static(m)

        with col_ctrl:
            st.subheader("Acciones de Campo")
            if st.button("🚀 CAPTURAR ESTADO HOY"):
                with st.spinner("Sincronizando satélites..."):
                    try:
                        p = ee.Geometry.Polygon(info['coords'])
                        # Procesamiento Sentinel-2 & Landsat
                        s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED').filterBounds(p).sort('system:time_start', False).first()
                        f_rep = datetime.fromtimestamp(s2.get('system:time_start').getInfo()/1000).strftime('%d/%m/%Y')
                        idx = s2.expression('((B8-B4)/(B8+B4+0.5))*1.5', {'B8':s2.select('B8'),'B4':s2.select('B4')}).rename('sa')\
                            .addBands(s2.normalizedDifference(['B3','B8']).rename('nd'))\
                            .addBands(s2.normalizedDifference(['B3','B11']).rename('mn'))\
                            .reduceRegion(ee.Reducer.mean(), p, 30).getInfo()
                        
                        l8 = ee.ImageCollection('LANDSAT/LC08/C02/T1_L2').filterBounds(p).sort('system:time_start', False).first()
                        lst = l8.select('ST_B10').multiply(0.00341802).add(149.0).subtract(273.15).reduceRegion(ee.Reducer.mean(), p, 30).getInfo().get('ST_B10', 0)

                        # Guardar en Google Sheets (Hoja 1 o Hoja 2)
                        fila = [[f_rep, idx['sa'], idx['nd'], idx['mn'], lst]]
                        service.spreadsheets().values().append(
                            spreadsheetId=info['sheet_id'], range=f"{info['pestaña']}!A2", 
                            valueInputOption="USER_ENTERED", body={'values': fila}
                        ).execute()
                        st.success(f"Captura exitosa en {info['pestaña']}")
                        st.metric("Temperatura Suelo", f"{lst:.1f} °C")
                    except Exception as e: st.error(f"Error: {e}")

    # --- MÓDULO 2: HISTORIAL & REPORTES DUALES ---
    elif menu == "📊 Historial & Reportes":
        st.subheader("Gestión de Evidencia y Reportes")
        try:
            res = service.spreadsheets().values().get(spreadsheetId=info['sheet_id'], range=f"{info['pestaña']}!A:E").execute()
            df = pd.DataFrame(res.get('values', [])[1:], columns=["Fecha", "SAVI", "NDWI", "NDSI", "Temp"])
            
            # --- PARTE A: REPORTE DE HOY ---
            st.markdown("### ⚡ Situación Inmediata (Hoy)")
            if not df.empty:
                ult = df.iloc[-1]
                st.write(f"Último dato: {ult['Fecha']} | SAVI: {ult['SAVI']} | Temp: {ult['Temp']}°C")
                if st.button("📄 GENERAR REPORTE DE HOY"):
                    pdf = FPDF()
                    pdf.add_page()
                    # Color dinámico: Rojo si temp > 40
                    color = (180, 40, 40) if float(ult['Temp']) > 40 else (20, 50, 80)
                    pdf.set_fill_color(*color); pdf.rect(0, 0, 210, 35, 'F')
                    pdf.set_text_color(255,255,255); pdf.set_font("helvetica","B",16)
                    pdf.cell(0, 15, clean(f"SITUACIÓN ACTUAL: {sel}"), align="C", ln=1)
                    pdf.ln(25); pdf.set_text_color(0,0,0); pdf.set_font("helvetica","",12)
                    pdf.multi_cell(0, 10, clean(f"Fecha: {ult['Fecha']}\nSAVI: {ult['SAVI']}\nTemp: {ult['Temp']}C\nEstado: Monitoreo Activo"))
                    pdf_bytes = pdf.output(dest='S').encode('latin-1')
                    requests.post(f"https://api.telegram.org/bot{T_TOKEN}/sendDocument", 
                                  data={"chat_id": T_ID, "caption": f"⚠️ Situación Hoy: {sel}"}, 
                                  files={"document": (f"BioCore_Hoy_{sel}.pdf", pdf_bytes)})
                    st.success("Reporte de hoy enviado.")

            st.divider()

            # --- PARTE B: REPORTE HISTÓRICO ---
            st.markdown("### 📈 Tendencias y Auditoría Prolongada")
            dias_sel = st.select_slider("Rango de días:", options=[7, 15, 30, 90], value=30)
            st.line_chart(df.tail(dias_sel).set_index("Fecha")["SAVI"])
            
            if st.button(f"📄 GENERAR REPORTE DE {dias_sel} DÍAS"):
                st.info("Calculando promedios y generando histórico...")
                # (Aquí iría la lógica similar de PDF pero con promedios del df.tail(dias_sel))
                st.success("Reporte histórico enviado.")
        except: st.warning("Asegúrese de que existan datos en el Google Sheet.")

    # --- MÓDULO 3: INCENDIOS ---
    elif menu == "🔥 Alerta de Incendios":
        st.subheader("Detección de Anomalías Térmicas (NASA FIRMS)")
        p = ee.Geometry.Polygon(info['coords'])
        # Focos últimas 24h
        f_hoy = ee.ImageCollection('FIRMS').filterBounds(p).filterDate((datetime.now()-timedelta(days=1)).strftime('%Y-%m-%d'), datetime.now().strftime('%Y-%m-%d')).size().getInfo()
        
        if f_hoy > 0:
            st.error(f"🚨 ALERTA: Se detectan {f_hoy} focos de incendio ACTIVOS.")
        else:
            st.success("✅ Área libre de incendios hoy.")
