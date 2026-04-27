import streamlit as st
import ee
import json

def iniciar_gee():
    if "GEE_JSON" in st.secrets:
        try:
            # 1. Cargamos el JSON
            creds_info = json.loads(st.secrets["GEE_JSON"])
            
            # 2. REPARACIÓN DE LLAVE (Anti-InvalidPadding)
            # Extraemos la llave y aseguramos que los saltos de línea sean correctos
            pk = creds_info['private_key']
            
            # Si la llave viene con saltos de línea literales (\n), los convertimos
            if isinstance(pk, str):
                pk = pk.replace("\\n", "\n").strip()
            
            # 3. Autenticación
            credentials = ee.ServiceAccountCredentials(
                creds_info['client_email'],
                key_data=pk
            )
            ee.Initialize(credentials)
        except Exception as e:
            st.error(f"❌ Error de conexión con GEE: {e}")
    else:
        st.error("⚠️ No se encontró el secreto GEE_JSON.")

iniciar_gee()


