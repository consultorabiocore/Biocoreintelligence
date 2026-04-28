import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
import json
import pandas as pd

def obtener_datos_final(sheet_id, pestaña):
    try:
        # 1. Forzar la carga limpia de credenciales
        creds_info = json.loads(st.secrets["GEE_JSON"])
        SCOPE = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive",
            "https://www.googleapis.com/auth/spreadsheets" # Permiso adicional
        ]
        
        # 2. Crear credenciales
        CREDS = Credentials.from_service_account_info(creds_info, scopes=SCOPE)
        client = gspread.authorize(CREDS)
        
        # 3. Limpiar ID del Sheet por si tiene la URL completa
        id_real = sheet_id.split('/d/')[-1].split('/')[0] if '/d/' in sheet_id else sheet_id.strip()
        
        # 4. Abrir y leer
        sh = client.open_by_key(id_real)
        hoja = sh.worksheet(pestaña.strip())
        registros = hoja.get_all_records()
        
        if not registros:
            st.warning("⚠️ El archivo se abrió, pero la pestaña no tiene datos debajo de los encabezados.")
            return pd.DataFrame()
            
        return pd.DataFrame(registros)

    except gspread.exceptions.APIError as e:
        st.error(f"❌ Error de API de Google: {e}")
        st.info("Revisa si la 'Google Sheets API' está habilitada en tu Google Cloud Console.")
    except Exception as e:
        st.error(f"❌ Error de conexión persistente: {str(e)}")
    return pd.DataFrame()
