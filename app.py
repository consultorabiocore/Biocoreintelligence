import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import json

# --- FUNCIÓN DE CONEXIÓN CORREGIDA ---
def obtener_datos_verificados(sheet_id, nombre_pestaña):
    try:
        creds_dict = json.loads(st.secrets["GEE_JSON"])
        SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        CREDS = Credentials.from_service_account_info(creds_dict, scopes=SCOPE)
        client = gspread.authorize(CREDS)
        
        # Abrir el libro
        sh = client.open_by_key(sheet_id)
        
        # Verificar si la pestaña existe
        listado_pestañas = [h.title for h in sh.worksheets()]
        if nombre_pestaña not in listado_pestañas:
            st.error(f"La pestaña '{nombre_pestaña}' no existe. Pestañas encontradas: {listado_pestañas}")
            return pd.DataFrame()

        hoja = sh.worksheet(nombre_pestaña)
        data = hoja.get_all_records()
        
        if not data:
            st.warning(f"La pestaña '{nombre_pestaña}' está vacía.")
            return pd.DataFrame()
            
        df = pd.DataFrame(data)
        
        # Limpiar nombres de columnas (quita espacios extra)
        df.columns = [c.strip() for c in df.columns]
        
        # Validar columna esencial
        if 'Fecha' not in df.columns:
            st.error("No se encontró la columna 'Fecha'. Revise el encabezado de su Excel.")
            return pd.DataFrame()
            
        df['Fecha'] = pd.to_datetime(df['Fecha'], errors='coerce')
        df = df.dropna(subset=['Fecha'])
        
        return df
    except Exception as e:
        st.error(f"Error de conexión: {str(e)}")
        return pd.DataFrame()

# --- DENTRO DE TU LÓGICA DE BOTÓN ---
if st.button("🔄 ANALIZAR Y GENERAR REPORTE"):
    with st.spinner("Accediendo a Google Sheets..."):
        df_data = obtener_datos_verificados(info['sheet_id'], info['pestaña'])
        
        if not df_data.empty:
            # Aquí sigue tu código para generar el PDF
            st.success("Datos cargados correctamente.")
            # generar_pdf(df_data, p_sel)...
        else:
            st.info("Asegúrese de que el ID de la hoja y el nombre de la pestaña coincidan exactamente con su archivo.")
