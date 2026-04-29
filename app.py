import streamlit as st
import pandas as pd
import re, json, requests
from st_supabase_connection import SupabaseConnection
import gspread
from google.oauth2.service_account import Credentials
import folium
from streamlit_folium import folium_static

# --- 1. CONEXIÓN Y LIMPIEZA DE CACHÉ ---
# Forzamos la limpieza para evitar errores de conexión persistentes
st.cache_resource.clear()

try:
    st_supabase = st.connection(
        "supabase",
        type=SupabaseConnection,
        url=st.secrets["connections"]["supabase"]["url"],
        key=st.secrets["connections"]["supabase"]["key"]
    )
except Exception as e:
    st.error("❌ Error de conexión con Supabase. Revisa la URL y Key en Secrets.")
    st.stop()

# --- 2. CONFIGURACIÓN VISUAL ---
st.set_page_config(page_title="BioCore Intelligence | Auditoría Profesional", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stMetric { background-color: white; padding: 15px; border-radius: 10px; border: 1px solid #e0e0e0; }
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; background-color: #1a3a5a; color: white; }
    </style>
    """, unsafe_allow_html=True)

# --- 3. FUNCIONES CORE ---
def enviar_telegram(mensaje, chat_id):
    try:
        token = st.secrets["telegram"]["token"]
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        requests.post(url, json={"chat_id": chat_id, "text": mensaje, "parse_mode": "Markdown"}, timeout=10)
    except:
        st.warning("No se pudo enviar la alerta a Telegram.")

def cargar_google_sheets(sheet_id, pestana):
    try:
        creds_info = json.loads(st.secrets["gee"]["json"])
        creds = Credentials.from_service_account_info(creds_info, scopes=[
            "https://spreadsheets.google.com/feeds", 
            "https://www.googleapis.com/auth/drive"
        ])
        client = gspread.authorize(creds)
        
        # Limpiar ID de la URL si es necesario
        sid = sheet_id.split("/d/")[1].split("/")[0] if "/d/" in sheet_id else sheet_id
        
        sh = client.open_by_key(sid)
        df = pd.DataFrame(sh.worksheet(pestana).get_all_records())
        df.columns = [c.strip().upper() for c in df.columns]
        
        if 'FECHA' in df.columns:
            df['FECHA'] = pd.to_datetime(df['FECHA'], dayfirst=True)
        return df
    except Exception as e:
        st.error(f"Error accediendo a Google Sheets: {e}")
        return pd.DataFrame()

# --- 4. NAVEGACIÓN ---
menu = st.sidebar.radio("SISTEMA DE VIGILANCIA", ["🛡️ Auditoría", "⚙️ Gestión de Clientes"])

# --- VISTA 1: AUDITORÍA ---
if menu == "🛡️ Auditoría":
    st.title("🛡️ Dashboard de Vigilancia Ambiental")
    
    # Recuperar datos de Supabase
    res = st_supabase.table("proyectos").select("*").execute()
    proyectos = res.data
    
    if proyectos:
        nombres = [p['nombre'] for p in proyectos]
        seleccion = st.selectbox("Seleccione Unidad de Monitoreo:", nombres)
        info = next(p for p in proyectos if p['nombre'] == seleccion)
        
        col1, col2 = st.columns([1, 1.2])
        
        with col1:
            st.info(f"**Cliente:** {info['nombre']} | **Tipo:** {info['tipo']}")
            if st.button("🚀 INICIAR MONITOREO"):
                with st.spinner("Conectando con satélites..."):
                    df = cargar_google_sheets(info['sheet_id'], info['pestana'])
                    if not df.empty:
                        idx = "NDSI" if info['tipo'] == "MINERIA" else "NDWI"
                        val_act = df[idx].iloc[-1]
                        promedio = df[idx].mean()
                        
                        # Lógica de Alerta
                        estado = "🟢 ESTABLE" if val_act >= info['umbral'] else "🔴 ALERTA"
                        msg = f"🛰 **BIOCORE INFORME: {info['nombre']}**\nIndicador {idx}: `{val_act:.3f}`\nEstado: {estado}"
                        enviar_telegram(msg, info['telegram_id'])
                        
                        # Métricas
                        st.metric(f"Índice {idx}", f"{val_act:.3f}", f"{((val_act-promedio)/promedio)*100:+.1f}%")
                        st.line_chart(df.set_index('FECHA')[[idx, 'SAVI']])
                        st.success("Auditoría enviada con éxito.")
        
        with col2:
            if info['coordenadas']:
                st.subheader("Mapa de Área Protegida")
                m = folium.Map(location=info['coordenadas'][0], zoom_start=13)
                folium.Polygon(locations=info['coordenadas'], color="#1a3a5a", fill=True, fill_opacity=0.4).add_to(m)
                folium_static(m)
    else:
        st.warning("Base de datos vacía. Registre un cliente en 'Gestión'.")

# --- VISTA 2: GESTIÓN ---
else:
    st.title("⚙️ Registro de Unidades BioCore")
    with st.form("registro_supabase", clear_on_submit=True):
        col_a, col_b = st.columns(2)
        with col_a:
            n = st.text_input("Nombre del Proyecto")
            t = st.selectbox("Ecosistema", ["MINERIA", "HUMEDAL"])
            sid = st.text_input("ID Planilla Google")
        with col_b:
            tid = st.text_input("Telegram ID Cliente")
            pes = st.text_input("Pestaña Sheet", value="Hoja 1")
            umb = st.number_input("Umbral de Alerta", value=0.35 if t=="MINERIA" else 0.10)
        
        cor = st.text_area("Coordenadas (Lat, Lon)")
        
        if st.form_submit_button("💾 Guardar en Supabase"):
            nums = re.findall(r"[-+]?\d*\.\d+|[-+]?\d+", cor)
            coords = [[float(nums[i]), float(nums[i+1])] for i in range(0, len(nums), 2) if i+1 < len(nums)]
            
            if n and coords:
                try:
                    st_supabase.table("proyectos").insert({
                        "nombre": n, "tipo": t, "telegram_id": tid, 
                        "sheet_id": sid, "pestana": pes, 
                        "coordenadas": coords, "umbral": umb
                    }).execute()
                    st.success(f"✅ Proyecto {n} registrado permanentemente.")
                    st.balloons()
                except Exception as e:
                    st.error(f"Error SQL: {e}")
            else:
                st.error("Faltan datos obligatorios.")
