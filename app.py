import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import json
import base64
from fpdf import FPDF
import io

# --- FUNCIÓN DE CARGA ULTRA-ROBUSTA ---
def cargar_datos_con_diagnostico(sheet_id, pestaña):
    try:
        creds_dict = json.loads(st.secrets["GEE_JSON"])
        SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        CREDS = Credentials.from_service_account_info(creds_dict, scopes=SCOPE)
        client = gspread.authorize(CREDS)
        
        sh = client.open_by_key(sheet_id)
        hoja = sh.worksheet(pestaña)
        registros = hoja.get_all_records()
        
        if not registros:
            st.error(f"La pestaña '{pestaña}' está vacía o no tiene encabezados válidos.")
            return pd.DataFrame()
            
        df = pd.DataFrame(registros)
        # Limpieza de columnas: quita espacios y convierte a mayúsculas para evitar errores de tipeo
        df.columns = [str(c).strip() for c in df.columns]
        
        # DIAGNÓSTICO EN PANTALLA
        with st.expander("🔍 Ver Diagnóstico de Datos"):
            st.write(f"Filas leídas: {len(df)}")
            st.write("Columnas encontradas:", list(df.columns))
            st.write("Primeras 3 filas:", df.head(3))

        # Intento de conversión de fecha flexible
        if 'Fecha' in df.columns:
            # Intenta varios formatos comunes (D/M/Y, Y-M-D)
            df['Fecha'] = pd.to_datetime(df['Fecha'], errors='coerce')
            filas_antes = len(df)
            df = df.dropna(subset=['Fecha'])
            if len(df) < filas_antes:
                st.warning(f"Se descartaron {filas_antes - len(df)} filas por fechas inválidas.")
        else:
            st.error("No existe la columna 'Fecha'. Verifica que la primera fila del Excel tenga ese nombre.")
            return pd.DataFrame()
            
        # Convertir índices a números forzadamente
        indices = ["SAVI", "NDSI", "NDWI", "SWIR", "Deficit"]
        for col in indices:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
                
        return df.sort_values('Fecha')

    except Exception as e:
        st.error(f"Error técnico: {str(e)}")
        return pd.DataFrame()

# --- LÓGICA DE ACTIVACIÓN ---
if st.button("🚀 EJECUTAR ANÁLISIS Y GENERAR INFORME"):
    info = st.session_state.clientes_db[p_sel]
    
    with st.spinner("Escaneando Google Sheet..."):
        df_final = cargar_datos_con_diagnostico(info['sheet_id'], info['pestaña'])
        
        if not df_final.empty:
            st.success(f"¡Éxito! {len(df_final)} registros listos.")
            # Aquí generas el PDF como en las versiones anteriores
            # pdf_data = generar_pdf(df_final, p_sel)
            # ... descarga ...
        else:
            st.warning("El análisis no pudo comenzar. Revisa el 'Diagnóstico de Datos' arriba.")
