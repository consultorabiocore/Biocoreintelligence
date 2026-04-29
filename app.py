import streamlit as st
import pandas as pd
import re, json, requests
from st_supabase_connection import SupabaseConnection
import gspread
from google.oauth2.service_account import Credentials
import folium
from streamlit_folium import folium_static

# --- 1. CONEXIÓN A BASE DE DATOS ---
st_supabase = st.connection("supabase", type=SupabaseConnection)

# --- 2. CONFIGURACIÓN VISUAL ---
st.set_page_config(page_title="BioCore Intelligence | SEIA", layout="wide")
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stButton>button { border-radius: 20px; height: 3em; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

# --- 3. FUNCIONES CORE ---
def enviar_telegram(mensaje, chat_id):
    try:
        token = st.secrets["telegram"]["token"]
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        requests.post(url, json={"chat_id": chat_id, "text": mensaje, "parse_mode": "Markdown"})
    except: st.error("Error al conectar con Telegram.")

def cargar_google_sheets(sheet_id, pestaña):
    try:
        creds_info = json.loads(st.secrets["gee"]["json"])
        creds = Credentials.from_service_account_info(creds_info, scopes=["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"])
        client = gspread.authorize(creds)
        # Limpiador de ID por si pegan URL completa
        sid = sheet_id.split("/d/")[1].split("/")[0] if "/d/" in sheet_id else sheet_id
        sh = client.open_by_key(sid)
        df = pd.DataFrame(sh.worksheet(pestaña).get_all_records())
        df.columns = [c.strip().upper() for c in df.columns]
        if 'FECHA' in df.columns: df['FECHA'] = pd.to_datetime(df['FECHA'], dayfirst=True)
        return df
    except Exception as e:
        st.error(f"Error Sheets: {e}")
        return pd.DataFrame()

# --- 4. NAVEGACIÓN ---
menu = st.sidebar.radio("SISTEMA BIOCORE", ["🛡️ Auditoría", "⚙️ Gestión de Clientes"])

if menu == "🛡️ Auditoría":
    st.title("🛡️ Panel de Vigilancia Satelital")
    
    # Consultar clientes desde Supabase
    res = st_supabase.table("proyectos").select("*").execute()
    proyectos = res.data
    
    if proyectos:
        nombres = [p['nombre'] for p in proyectos]
        sel = st.selectbox("Seleccione Unidad de Monitoreo:", nombres)
        info = next(p for p in proyectos if p['nombre'] == sel)
        
        c1, c2 = st.columns([1, 1.2])
        with c1:
            st.subheader("Estado de Faena")
            if st.button("🚀 EJECUTAR MONITOREO"):
                df = cargar_google_sheets(info['sheet_id'], info['pestana'])
                if not df.empty:
                    idx = "NDSI" if info['tipo'] == "MINERIA" else "NDWI"
                    val = df[idx].iloc[-1]
                    prom = df[idx].mean()
                    
                    # Notificación Telegram
                    estado = "🟢 ESTABLE" if val >= info['umbral'] else "🔴 ALERTA"
                    msg = f"🛰 **BIOCORE: {info['nombre']}**\nIndicador: `{idx}`\nValor: `{val:.3f}`\nEstado: {estado}"
                    enviar_telegram(msg, info['telegram_id'])
                    
                    st.metric(idx, f"{val:.3f}", f"{((val-prom)/prom)*100:+.1f}%")
                    st.line_chart(df.set_index('FECHA')[[idx, 'SAVI']])
                    st.success("Reporte enviado a Telegram.")
        
        with c2:
            st.subheader("Geolocalización")
            if info['coordenadas']:
                m = folium.Map(location=info['coordenadas'][0], zoom_start=13)
                folium.Polygon(locations=info['coordenadas'], color="#1a3a5a", fill=True).add_to(m)
                folium_static(m)
    else:
        st.warning("No hay proyectos en la base de datos.")

else:
    st.title("⚙️ Registro de Nuevos Clientes")
    with st.form("registro_supabase", clear_on_submit=True):
        n = st.text_input("Nombre del Proyecto")
        t = st.selectbox("Ecosistema", ["MINERIA", "HUMEDAL"])
        tid = st.text_input("Chat ID Telegram")
        sid = st.text_input("Google Sheet ID")
        pes = st.text_input("Nombre de Pestaña", value="Hoja 1")
        cor = st.text_area("Coordenadas (Lat, Lon)")
        
        if st.form_submit_button("💾 Sincronizar con Supabase"):
            nums = re.findall(r"[-+]?\d*\.\d+|[-+]?\d+", cor)
            coords = [[float(nums[i]), float(nums[i+1])] for i in range(0, len(nums), 2) if i+1 < len(nums)]
            
            if n and coords:
                st_supabase.table("proyectos").insert({
                    "nombre": n, "tipo": t, "telegram_id": tid, "sheet_id": sid, 
                    "pestana": pes, "coordenadas": coords, "umbral": 0.35 if t == "MINERIA" else 0.10
                }).execute()
                st.success(f"Proyecto {n} blindado en la nube.")
                st.balloons()
