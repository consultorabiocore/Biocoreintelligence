import streamlit as st
import ee
import json
import pandas as pd
from google.oauth2 import service_account

# --- 1. VERIFICACIÓN DE SECRETOS (PRIMER PASO) ---
st.title("🛰️ BioCore Intelligence Console")

def check_secrets():
    if "EARTH_ENGINE_JSON" not in st.secrets:
        st.error("❌ ERROR: No se encontró la clave 'EARTH_ENGINE_JSON' en los Secrets de Streamlit.")
        st.info("Ve a Settings > Secrets y pega tu JSON ahí.")
        return False
    return True

# --- 2. INICIALIZACIÓN DE MOTOR ---
if check_secrets():
    try:
        # Intentamos cargar las credenciales
        creds_dict = json.loads(st.secrets["EARTH_ENGINE_JSON"])
        creds = service_account.Credentials.from_service_account_info(
            creds_dict, 
            scopes=['https://www.googleapis.com/auth/earthengine', 'https://www.googleapis.com/auth/spreadsheets']
        )
        
        # Inicializamos GEE
        if not ee.data._credentials:
            ee.Initialize(creds)
        
        st.success("✅ Conexión con Satélites Establecida")
        
        # --- AQUÍ VA EL RESTO DE TU CÓDIGO ---
        # Solo se mostrará si lo de arriba funciona
        
        opcion = st.selectbox("Seleccione Proyecto:", ["Pascua Lama", "Laguna Señoraza"])
        st.write(f"Has seleccionado: {opcion}")
        
    except json.JSONDecodeError:
        st.error("❌ ERROR: El formato del JSON en los Secrets es incorrecto. Asegúrate de que tenga llaves { }.")
    except Exception as e:
        st.error(f"❌ ERROR CRÍTICO AL INICIAR: {e}")
        st.warning("Verifica que la API de Earth Engine esté activada en tu consola de Google Cloud.")
