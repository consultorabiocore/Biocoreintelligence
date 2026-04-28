import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import json

# --- 1. CONEXIÓN SOLO AL EXCEL (Esto no falla) ---
def cargar_datos_desde_excel(sheet_id, pestaña):
    try:
        # Usa el JSON de tus Secrets
        creds_dict = json.loads(st.secrets["GEE_JSON"])
        SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        CREDS = Credentials.from_service_account_info(creds_dict, scopes=SCOPE)
        client = gspread.authorize(CREDS)
        
        # Abrir la hoja
        sh = client.open_by_key(sheet_id)
        hoja = sh.worksheet(pestaña)
        df = pd.DataFrame(hoja.get_all_records())
        
        # Limpieza de nombres para que coincidan con tu Excel de Mina
        df.columns = [str(c).strip().upper() for c in df.columns]
        return df
    except Exception as e:
        st.error(f"Error al leer el Excel: {e}")
        return pd.DataFrame()

# --- 2. INTERFAZ DE BIOCORE ---
st.title("🛡️ BioCore Intelligence: Auditoría")

# Simulemos que ya tienes el ID del proyecto registrado
id_pascua_lama = "TU_ID_DE_EXCEL_REAL" 

if st.button("🔄 ACTUALIZAR DESDE SATÉLITE"):
    with st.spinner("Leyendo registros del Excel..."):
        df = cargar_datos_desde_excel(id_pascua_lama, "Hoja 1")
        
        if not df.empty:
            st.success(f"Datos cargados: {len(df)} registros encontrados.")
            st.line_chart(df.set_index('FECHA')[['NDSI', 'MNDWI']])
        else:
            st.warning("El Excel está conectado pero no tiene datos aún.")
