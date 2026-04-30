import streamlit as st
import json
import ee
import requests
from datetime import datetime
from googleapiclient.discovery import build
from google.oauth2 import service_account
from streamlit_folium import folium_static
import folium

# --- 1. CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="BioCore Intelligence V5", layout="wide")

# --- 2. SEGURIDAD BLINDADA ---
def check_password():
    if "password_correct" not in st.session_state:
        st.title("🔐 Acceso BioCore V5")
        u = st.text_input("Usuario / Correo", key="input_user")
        p = st.text_input("Contraseña", type="password", key="input_pass")
        
        if st.button("Ingresar"):
            try:
                # Verificamos si los secrets existen
                val_user = st.secrets["auth"]["user"]
                val_pass = st.secrets["auth"]["password"]
                
                if u == val_user and p == val_pass:
                    st.session_state["password_correct"] = True
                    st.session_state["usuario_actual"] = u
                    st.rerun()
                else:
                    st.error("❌ Credenciales incorrectas")
            except KeyError:
                st.error("⚠️ Error de Configuración: No se encontraron las credenciales en 'Secrets'.")
                st.info("Debes agregar [auth] user y password en los Secrets de Streamlit Cloud.")
        return False
    return True

if check_password():
    # --- 3. EL RESTO DEL CÓDIGO (GEE, MAPA, ETC.) ---
    T_TOKEN = st.secrets["telegram"]["token"]
    T_ID = st.secrets["telegram"]["chat_id"]
    
    st.success(f"Bienvenida, Directora. Sesión activa: {st.session_state['usuario_actual']}")
    
    # Aquí sigue el diccionario CLIENTES y la lógica de ejecución...
    # (El resto del código que ya tienes se mantiene igual)
