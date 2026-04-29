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
DIRECTORA = "Loreto Campos Carrasco"

def clean(text):
    return text.encode('latin-1', 'replace').decode('latin-1')

# --- 2. BASE DE DATOS DE PROYECTOS ---
# Importante: El nombre aquí se usará para crear la pestaña en el Excel automáticamente
CLIENTES = {
 "Auditoría Laguna Señoraza": {
    "coords": [[-72.715,-37.275],[-72.715,-37.285],[-72.690,-37.285],[-72.690,-37.270]], 
    "tipo": "HUMEDAL",
    "sheet_id": "1x6yAXNNlea3e43rijJu0aqcRpe4oP3BEnzgSgLuG1vU"
 },
 "Auditoría Pascua Lama": {
    "coords": [[-70.033,-29.316],[-70.016,-29.316],[-70.016,-29.333],[-70.033,-29.333]], 
    "tipo": "MINERIA",
    "sheet_id": "1x6yAXNNlea3e43rijJu0aqcRpe4oP3BEnzgSgLuG1vU"
 }
}

# --- 3. SERVICIOS (GEE & GOOGLE SHEETS) ---
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

# --- 4. FUNCIÓN: GESTIÓN AUTOMÁTICA DE PESTAÑAS ---
def asegurar_pestaña(service, spreadsheet_id, nombre):
    try:
        meta = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
        existentes = [s.get("properties", {}).get("title") for s in meta.get('sheets', [])]
        
        if nombre not in existentes:
            # Crear pestaña con color corporativo
            solicitud = {'requests': [{'addSheet': {'properties': {
                'title': nombre, 
                'tabColor': {'red': 0.1, 'green': 0.4, 'blue': 0.6}
            }}}]}
            service.spreadsheets().batchUpdate(spreadsheetId=spreadsheet_id, body=solicitud).execute()
            # Escribir encabezados
            headers = [["Fecha", "Vigor (SAVI)", "Humedad (NDWI)", "Nieve (NDSI)", "Temperatura C", "Alerta Fuego"]]
            service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id, range=f"'{nombre}'!A1",
                valueInputOption="USER_ENTERED", body={'values': headers}
            ).execute()
            st.toast(f"✨ Base de datos creada para: {nombre}")
    except Exception as e: st.error(f"Error en Sheets: {e}")

# --- 5. BARRA LATERAL ---
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/satellite.png", width=60)
    st.title("BioCore Admin")
    menu = st.radio("Módulos:", ["🛰️ Monitor en Vivo", "📊 Historial & Reportes", "🔥 Incendios"])
    st.divider()
    st.caption(f"Directora: {DIRECTORA}")
    st.caption("Sensores: Sentinel 1/2, Landsat, NASA FIRMS")

# --- 6. LÓGICA PRINCIPAL ---
if service:
    sel = st.selectbox("🎯 Proyecto Activo:", list(CLIENTES.keys()))
    info = CLIENTES[sel]

    if menu == "🛰️ Monitor en Vivo":
        col1, col2 = st.columns([2, 1])
        with col1:
            avg_lat = sum(p[1] for p in info['coords']) / len(info['coords'])
            avg_lon = sum(p[0] for p in info['coords']) / len(info['coords'])
            m = folium.Map(location=[avg_lat, avg_lon], zoom_start=14)
            folium.TileLayer('https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}', attr='Google', name='Google Sat').add_to(m)
            folium.Polygon(locations=[[p[1], p[0]] for p in info['coords']], color='#2ecc71', fill=True, opacity=0.3).add_to(m)
            folium_static(m)

        with col2:
            st.subheader("Captura de Telemetría")
            if st.button("🚀 ESCANEAR AHORA"):
                with st.spinner("Procesando datos multiespectrales..."):
                    asegurar_pestaña(service, info['sheet_id'], sel)
                    try:
                        p = ee.Geometry.Polygon(info['coords'])
                        # Sentinel 2 & Landsat 8
                        s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED').filterBounds(p).sort('system:time_start', False).first()
                        f_rep = datetime.fromtimestamp(s2.get('system:time_start').getInfo()/1000).strftime('%d/%m/%Y')
                        idx = s2.expression('((B8-B4)/(B8+B4+0.5))*1.5', {'B8':s2.select('B8'),'B4':s2.select('B4')}).rename('sa')\
                            .addBands(s2.normalizedDifference(['B3','B8']).rename('nd'))\
                            .addBands(s2.normalizedDifference(['B3','B11']).rename('mn'))\
                            .reduceRegion(ee.Reducer.mean(), p, 30).getInfo()
                        
                        l8 = ee.ImageCollection('LANDSAT/LC08/C02/T1_L2').filterBounds(p).sort('system:time_start', False).first()
                        lst = l8.select('ST_B10').multiply(0.00341802).add(149.0).subtract(273.15).reduceRegion(ee.Reducer.mean(), p, 30).getInfo().get('ST_B10', 0)

                        # Guardar en la pestaña correspondiente
                        fila = [[f_rep, f"{idx['sa']:.2f}", f"{idx['nd']:.2f}", f"{idx['mn']:.2f}", f"{lst:.1f}", "NO"]]
                        service.spreadsheets().values().append(
                            spreadsheetId=info['sheet_id'], range=f"'{sel}'!A2", 
                            valueInputOption="USER_ENTERED", body={'values': fila}
                        ).execute()
                        st.success(f"Captura registrada en pestaña: {sel}")
                        st.metric("Vigor (SAVI)", f"{idx['sa']:.2f}")
                        st.metric("Temperatura", f"{lst:.1f}°C")
                    except Exception as e: st.error(f"Fallo técnico: {e}")

    elif menu == "📊 Historial & Reportes":
        st.subheader("Centro de Reportes BioCore")
        try:
            res = service.spreadsheets().values().get(spreadsheetId=info['sheet_id'], range=f"'{sel}'!A:F").execute()
            df = pd.DataFrame(res.get('values', [])[1:], columns=["Fecha", "SAVI", "NDWI", "NDSI", "Temp", "Fuego"])
            
            # --- REPORTE DE HOY ---
            if not df.empty:
                ult = df.iloc[-1]
                st.info(f"Estado Inmediato: {ult['Fecha']}")
                if st.button("📄 GENERAR INFORME DE HOY"):
                    pdf = FPDF()
                    pdf.add_page()
                    color = (180, 40, 40) if float(ult['Temp']) > 40 else (20, 50, 80)
                    pdf.set_fill_color(*color); pdf.rect(0, 0, 210, 35, 'F')
                    pdf.set_text_color(255,255,255); pdf.set_font("helvetica","B",16)
                    pdf.cell(0, 15, clean(f"SITUACIÓN ACTUAL: {sel}"), align="C", ln=1)
                    pdf.ln(25); pdf.set_text_color(0,0,0); pdf.set_font("helvetica","",12)
                    cuerpo = f"Fecha: {ult['Fecha']}\nVigor: {ult['SAVI']}\nHumedad: {ult['NDWI']}\nTemperatura: {ult['Temp']}C\nAlerta Fuego: {ult['Fuego']}"
                    pdf.multi_cell(0, 10, clean(cuerpo), border=1)
                    pdf_bytes = pdf.output(dest='S').encode('latin-1')
                    requests.post(f"https://api.telegram.org/bot{T_TOKEN}/sendDocument", 
                                  data={"chat_id": T_ID, "caption": f"⚠️ BioCore: {sel}"}, 
                                  files={"document": (f"BioCore_Hoy.pdf", pdf_bytes)})
                    st.success("Enviado a Telegram.")

            st.divider()
            # --- REPORTE HISTÓRICO ---
            dias_sel = st.select_slider("Análisis histórico (días):", options=[7, 15, 30, 90], value=30)
            st.line_chart(df.tail(dias_sel).set_index("Fecha")["SAVI"])
        except: st.warning("Pendiente de primera captura de datos.")

    elif menu == "🔥 Incendios":
        st.subheader("Detección de Anomalías Térmicas NASA FIRMS")
        p = ee.Geometry.Polygon(info['coords'])
        f_24h = ee.ImageCollection('FIRMS').filterBounds(p).filterDate((datetime.now()-timedelta(days=1)).strftime('%Y-%m-%d'), datetime.now().strftime('%Y-%m-%d')).size().getInfo()
        if f_24h > 0: st.error(f"🚨 ALERTA: {f_24h} focos activos hoy."); st.toast("RIESGO DE INCENDIO")
        else: st.success("✅ Área sin anomalías térmicas.")
