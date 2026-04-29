import streamlit as st
import pandas as pd
import re, json, requests
from st_supabase_connection import SupabaseConnection
import gspread
from google.oauth2.service_account import Credentials
import folium
from streamlit_folium import folium_static

# --- ELIMINAR CACHÉ DE CONEXIONES ANTIGUAS ---
st.cache_resource.clear()

# --- 1. CONEXIÓN DIRECTA Y ROBUSTA ---
try:
    # Definimos la conexión extrayendo manualmente para evitar errores de herencia
    st_supabase = st.connection(
        "supabase",
        type=SupabaseConnection,
        url=st.secrets["connections"]["supabase"]["url"].strip(),
        key=st.secrets["connections"]["supabase"]["key"].strip()
    )
except Exception as e:
    st.error("❌ Error de configuración en los Secrets de Supabase.")
    st.stop()

# --- 2. CONFIGURACIÓN VISUAL ---
st.set_page_config(page_title="BioCore Intelligence | Auditoría Profesional", layout="wide")

# --- 3. FUNCIONES ---
def enviar_telegram(mensaje, chat_id):
    try:
        token = st.secrets["telegram"]["token"]
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        requests.post(url, json={"chat_id": chat_id, "text": mensaje, "parse_mode": "Markdown"}, timeout=10)
    except: pass

def cargar_google_sheets(sheet_id, pestana):
    try:
        creds_info = json.loads(st.secrets["gee"]["json"])
        creds = Credentials.from_service_account_info(creds_info, scopes=[
            "https://spreadsheets.google.com/feeds", 
            "https://www.googleapis.com/auth/drive"
        ])
        client = gspread.authorize(creds)
        sid = sheet_id.split("/d/")[1].split("/")[0] if "/d/" in sheet_id else sheet_id
        sh = client.open_by_key(sid)
        df = pd.DataFrame(sh.worksheet(pestana).get_all_records())
        df.columns = [c.strip().upper() for c in df.columns]
        if 'FECHA' in df.columns: df['FECHA'] = pd.to_datetime(df['FECHA'], dayfirst=True)
        return df
    except Exception as e:
        st.error(f"Error Sheets: {e}")
        return pd.DataFrame()

# --- 4. NAVEGACIÓN ---
menu = st.sidebar.radio("SISTEMA DE VIGILANCIA", ["🛡️ Auditoría", "⚙️ Gestión de Clientes"])

if menu == "🛡️ Auditoría":
    st.title("🛡️ Dashboard de Vigilancia Ambiental")
    
    # Intentar obtener proyectos con manejo de errores de conexión
    try:
        res = st_supabase.table("proyectos").select("*").execute()
        proyectos = res.data
    except Exception as e:
        st.error(f"Error de conexión con la base de datos: {e}")
        st.info("Prueba reiniciando la app desde 'Manage App' -> 'Reboot App'.")
        st.stop()
    
    if proyectos:
        nombres = [p['nombre'] for p in proyectos]
        seleccion = st.selectbox("Seleccione Unidad de Monitoreo:", nombres)
        info = next(p for p in proyectos if p['nombre'] == seleccion)
        
        col1, col2 = st.columns([1, 1.2])
        with col1:
            if st.button("🚀 INICIAR MONITOREO"):
                df = cargar_google_sheets(info['sheet_id'], info['pestana'])
                if not df.empty:
                    idx = "NDSI" if info['tipo'] == "MINERIA" else "NDWI"
                    val_act = df[idx].iloc[-1]
                    promedio = df[idx].mean()
                    estado = "🟢 ESTABLE" if val_act >= info['umbral'] else "🔴 ALERTA"
                    enviar_telegram(f"🛰 **BIOCORE: {info['nombre']}**\n{idx}: `{val_act:.3f}`\n{estado}", info['telegram_id'])
                    st.metric(f"Índice {idx}", f"{val_act:.3f}", f"{((val_act-promedio)/promedio)*100:+.1f}%")
                    st.line_chart(df.set_index('FECHA')[[idx, 'SAVI']])
        with col2:
            if info['coordenadas']:
                m = folium.Map(location=info['coordenadas'][0], zoom_start=13)
                folium.Polygon(locations=info['coordenadas'], color="#1a3a5a", fill=True).add_to(m)
                folium_static(m)
    else:
        st.warning("Base de datos vacía.")

else:
    st.title("⚙️ Registro de Unidades BioCore")
    with st.form("registro", clear_on_submit=True):
        col_a, col_b = st.columns(2)
        with col_a:
            n = st.text_input("Nombre del Proyecto")
            t = st.selectbox("Ecosistema", ["MINERIA", "HUMEDAL"])
            sid = st.text_input("ID Planilla Google")
        with col_b:
            tid = st.text_input("Telegram ID")
            pes = st.text_input("Pestaña", value="Hoja 1")
            umb = st.number_input("Umbral", value=0.35 if t=="MINERIA" else 0.10)
        cor = st.text_area("Coordenadas (Lat, Lon)")
        if st.form_submit_button("💾 Guardar"):
            nums = re.findall(r"[-+]?\d*\.\d+|[-+]?\d+", cor)
            coords = [[float(nums[i]), float(nums[i+1])] for i in range(0, len(nums), 2) if i+1 < len(nums)]
            if n and coords:
                st_supabase.table("proyectos").insert({"nombre": n, "tipo": t, "telegram_id": tid, "sheet_id": sid, "pestana": pes, "coordenadas": coords, "umbral": umb}).execute()
                st.success("Registrado.")
