import streamlit as st
import json
import ee
import requests
from datetime import datetime
from googleapiclient.discovery import build
from google.oauth2 import service_account

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="BioCore V5 Lite")
T_TOKEN = st.secrets["telegram"]["token"]
T_ID = st.secrets["telegram"]["chat_id"]
UMBRAL = 0.4

CLIENTES = {
    "Laguna Señoraza (Laja)": {
        "coords": [[-72.715,-37.275],[-72.715,-37.285],[-72.690,-37.285],[-72.690,-37.270]], 
        "tipo": "HUMEDAL", "sheet_id": "1x6yAXNNlea3e43rijJu0aqcRpe4oP3BEnzgSgLuG1vU", "pestaña": "Humedales"
    },
    "Pascua Lama (Cordillera)": {
        "coords": [[-70.033,-29.316],[-70.016,-29.316],[-70.016,-29.333],[-70.033,-29.333]], 
        "tipo": "GLACIAR", "sheet_id": "1UTrDs939rPlVIR1OTIwbJ6rM3FazgjX43YnJdue-Dmc", "pestaña": "Mineria"
    }
}

st.title("🛰️ BioCore V5 - Monitor Directo")

# 1. BOTÓN DE EJECUCIÓN
if st.button("🚀 INICIAR ESCANEO FORZADO"):
    try:
        # Autenticación GEE
        creds_info = json.loads(st.secrets["gee"]["json"])
        creds = service_account.Credentials.from_service_account_info(creds_info, 
                scopes=['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/earthengine'])
        
        if not ee.data._credentials:
            ee.Initialize(creds)
        
        sheets = build('sheets', 'v4', credentials=creds)

        for nombre, info in CLIENTES.items():
            st.write(f"🔍 Analizando {nombre}...")
            p = ee.Geometry.Polygon(info['coords'])
            
            # Captura de datos
            s2 = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED').filterBounds(p).sort('system:time_start', False).first()
            f_rep = datetime.fromtimestamp(s2.get('system:time_start').getInfo()/1000).strftime('%d/%m/%Y')
            
            idx = s2.expression('((B8-B4)/(B8+B4+0.5))*1.5', {'B8':s2.select('B8'),'B4':s2.select('B4')}).rename('sa')\
                .addBands(s2.normalizedDifference(['B3','B8']).rename('nd'))\
                .reduceRegion(ee.Reducer.mean(), p, 30).getInfo()

            estado = "🟢 NORMAL"
            if idx['nd'] < UMBRAL: estado = "🔴 ALERTA"

            # 2. RENDERIZADO INMEDIATO (Sin columnas ni contenedores)
            st.success(f"**{nombre}**")
            st.code(f"Fecha: {f_rep} | Estado: {estado}\nSAVI: {idx['sa']:.3f} | ND: {idx['nd']:.3f}")

            # Sincronización
            fila = [[f_rep, idx['sa'], idx['nd'], estado]]
            sheets.spreadsheets().values().append(spreadsheetId=info['sheet_id'], range=f"{info['pestaña']}!A2", valueInputOption="USER_ENTERED", body={'values': fila}).execute()
            
            # Telegram
            requests.post(f"https://api.telegram.org/bot{T_TOKEN}/sendMessage", 
                         data={"chat_id": T_ID, "text": f"✅ {nombre}: {estado} ({f_rep})"})

        st.balloons()

    except Exception as e:
        st.error(f"Error detectado: {str(e)}")
else:
    st.info("App lista. Si el botón no responde, refresca la página.")
