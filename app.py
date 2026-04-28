import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import json
import re
import base64
import io
import matplotlib.pyplot as plt
from fpdf import FPDF

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="BioCore Intelligence: Auditoría", layout="wide")

# Inicializar la base de datos en la memoria de la app
if 'clientes_db' not in st.session_state:
    st.session_state.clientes_db = {}

# --- FUNCIÓN DE CONEXIÓN SEGURA AL EXCEL ---
def cargar_datos_excel(sheet_id, pestaña):
    try:
        creds_dict = json.loads(st.secrets["GEE_JSON"])
        SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        CREDS = Credentials.from_service_account_info(creds_dict, scopes=SCOPE)
        client = gspread.authorize(CREDS)
        
        # Limpieza automática del ID por si pegas la URL completa
        id_limpio = sheet_id.split('/d/')[-1].split('/')[0] if '/d/' in sheet_id else sheet_id.strip()
        
        sh = client.open_by_key(id_limpio)
        hoja = sh.worksheet(pestaña.strip())
        df = pd.DataFrame(hoja.get_all_records())
        
        # Normalizar nombres de columnas a MAYÚSCULAS
        df.columns = [str(c).strip().upper() for c in df.columns]
        return df
    except Exception as e:
        st.error(f"Error de conexión: {e}")
        return pd.DataFrame()

# --- MENÚ LATERAL (RESTAURADO) ---
menu = st.sidebar.radio("Navegación", ["🛡️ Auditoría", "⚙️ Gestión de Proyectos"])

# --- SECCIÓN 1: AUDITORÍA ---
if menu == "🛡️ Auditoría":
    st.header("BioCore Intelligence: Panel de Control")
    
    if not st.session_state.clientes_db:
        st.info("No hay proyectos registrados. Ve a la pestaña 'Gestión de Proyectos' para configurar uno.")
    else:
        proyecto_nombre = st.selectbox("Seleccione Proyecto Activo:", list(st.session_state.clientes_db.keys()))
        info = st.session_state.clientes_db[proyecto_nombre]
        
        if st.button("🔄 ACTUALIZAR DATOS Y GENERAR GRÁFICOS"):
            with st.spinner("Sincronizando con el satélite vía Excel..."):
                df = cargar_datos_excel(info['sheet_id'], info['pestaña'])
                
                if not df.empty:
                    st.success(f"Se encontraron {len(df)} registros para {proyecto_nombre}.")
                    
                    # Mostrar tabla de datos
                    with st.expander("Ver tabla de datos crudos"):
                        st.dataframe(df)
                    
                    # Gráfico de Índices (MNDWI, NDSI si existe)
                    st.subheader("Evolución de Índices Críticos")
                    columnas_grafico = [col for col in ['MNDWI', 'NDSI', 'SAVI'] if col in df.columns]
                    if columnas_grafico:
                        st.line_chart(df.set_index(df.columns[0])[columnas_grafico])
                else:
                    st.warning("El Excel está conectado pero la hoja parece estar vacía.")

# --- SECCIÓN 2: GESTIÓN (RESTAURADA) ---
else:
    st.header("⚙️ Configuración de Proyectos")
    
    with st.form("registro_nuevo"):
        st.subheader("Registrar Nueva Faena")
        nombre = st.text_input("Nombre del Proyecto", value="Pascua Lama")
        s_id = st.text_input("ID del Google Sheet (Cópialo de tu URL)")
        pest = st.text_input("Nombre de la Pestaña", value="Hoja 1")
        coords_input = st.text_area("Pegue Coordenadas del Polígono (Lat, Lon)")
        
        if st.form_submit_button("Guardar Proyecto"):
            # Limpiador de coordenadas automático
            nums = re.findall(r"[-+]?\d*\.\d+|[-+]?\d+", coords_input)
            coords_finales = [[float(nums[i]), float(nums[i+1])] for i in range(0, len(nums), 2) if i+1 < len(nums)]
            
            if coords_finales and len(s_id) > 10:
                st.session_state.clientes_db[nombre] = {
                    "sheet_id": s_id.strip(),
                    "pestaña": pest.strip(),
                    "coords": coords_finales
                }
                st.success(f"Proyecto '{nombre}' guardado correctamente.")
            else:
                st.error("Por favor, verifica el ID del Sheet y el formato de las coordenadas.")

    # Historial visible
    if st.session_state.clientes_db:
        st.subheader("Historial de Proyectos Configurados")
        st.write(st.session_state.clientes_db)
