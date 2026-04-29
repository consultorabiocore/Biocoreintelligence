import streamlit as st
import pandas as pd
import re, json, requests
from st_supabase_connection import SupabaseConnection
import gspread
from google.oauth2.service_account import Credentials
import folium
from streamlit_folium import folium_static

# --- LIMPIEZA DE MEMORIA ---
st.cache_resource.clear()

# --- 1. CONEXIÓN A BASE DE DATOS ---
try:
    # Conexión usando la estructura de tus secretos
    st_supabase = st.connection(
        "supabase",
        type=SupabaseConnection,
        url=st.secrets["connections"]["supabase"]["url"].strip(),
        key=st.secrets["connections"]["supabase"]["key"].strip()
    )
except Exception as e:
    st.error(f"❌ Error de conexión: {e}")
    st.stop()

# --- 2. CONFIGURACIÓN VISUAL ---
st.set_page_config(page_title="BioCore Intelligence | SEIA", layout="wide")

# --- 3. FUNCIONES OPERATIVAS ---
def enviar_telegram(mensaje, chat_id):
    try:
        token = st.secrets["telegram"]["token"]
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        requests.post(url, json={"chat_id": chat_id, "text": mensaje, "parse_mode": "Markdown"}, timeout=10)
    except: pass

def cargar_datos_google(sheet_id, pestana):
    try:
        creds_info = json.loads(st.secrets["gee"]["json"])
        creds = Credentials.from_service_account_info(creds_info, scopes=[
            "https://spreadsheets.google.com/feeds", 
            "https://www.googleapis.com/auth/drive"
        ])
        client = gspread.authorize(creds)
        # Limpieza de ID de la URL
        sid = sheet_id.split("/d/")[1].split("/")[0] if "/d/" in sheet_id else sheet_id
        sh = client.open_by_key(sid)
        df = pd.DataFrame(sh.worksheet(pestana).get_all_records())
        df.columns = [c.strip().upper() for c in df.columns]
        if 'FECHA' in df.columns:
            df['FECHA'] = pd.to_datetime(df['FECHA'], dayfirst=True)
        return df
    except Exception as e:
        st.error(f"Error en Google Sheets: {e}")
        return pd.DataFrame()

# --- 4. NAVEGACIÓN ---
menu = st.sidebar.radio("SISTEMA BIOCORE", ["🛡️ Auditoría Ambiental", "⚙️ Gestión de Proyectos"])

# --- VISTA: AUDITORÍA ---
if menu == "🛡️ Auditoría Ambiental":
    st.title("🛡️ Dashboard de Vigilancia")
    
    # Consulta a Supabase
    res = st_supabase.table("proyectos").select("*").execute()
    proyectos = res.data
    
    if proyectos:
        nombres = [p['nombre'] for p in proyectos]
        seleccion = st.selectbox("Seleccione Unidad de Monitoreo:", nombres)
        info = next(p for p in proyectos if p['nombre'] == seleccion)
        
        c1, c2 = st.columns([1, 1.2])
        with c1:
            st.subheader(f"Ecosistema: {info['tipo']}")
            if st.button("🚀 EJECUTAR MONITOREO"):
                with st.spinner("Analizando datos satelitales..."):
                    df = cargar_datos_google(info['sheet_id'], info['pestana'])
                    if not df.empty:
                        idx = "NDSI" if info['tipo'] == "MINERIA" else "NDWI"
                        val_actual = df[idx].iloc[-1]
                        promedio = df[idx].mean()
                        
                        estado = "🟢 ESTABLE" if val_actual >= info['umbral'] else "🔴 ALERTA"
                        msg = f"🛰 **BIOCORE: {info['nombre']}**\nIndicador {idx}: `{val_actual:.3f}`\nEstado: {estado}"
                        enviar_telegram(msg, info['telegram_id'])
                        
                        st.metric(idx, f"{val_actual:.3f}", f"{((val_actual-promedio)/promedio)*100:+.2f}%")
                        st.line_chart(df.set_index('FECHA')[[idx, 'SAVI']])
                        st.success("Informe enviado a Telegram.")
        with c2:
            if info['coordenadas']:
                st.subheader("Mapa del Área")
                m = folium.Map(location=info['coordenadas'][0], zoom_start=13)
                folium.Polygon(locations=info['coordenadas'], color="#1a3a5a", fill=True).add_to(m)
                folium_static(m)
    else:
        st.info("Registre su primer proyecto en la pestaña de Gestión.")

# --- VISTA: GESTIÓN ---
else:
    st.title("⚙️ Registro de Clientes")
    with st.form("registro_form", clear_on_submit=True):
        col_a, col_b = st.columns(2)
        with col_a:
            n = st.text_input("Nombre del Proyecto")
            t = st.selectbox("Ecosistema", ["MINERIA", "HUMEDAL"])
            sid = st.text_input("ID Google Sheet")
        with col_b:
            tid = st.text_input("ID Telegram Cliente")
            pes = st.text_input("Nombre Pestaña", value="Hoja 1")
            umb = st.number_input("Umbral Crítico", value=0.35 if t=="MINERIA" else 0.10)
        
        cor = st.text_area("Coordenadas (Lat, Lon)")
        
        if st.form_submit_button("💾 Sincronizar con Supabase"):
            nums = re.findall(r"[-+]?\d*\.\d+|[-+]?\d+", cor)
            lista_coords = [[float(nums[i]), float(nums[i+1])] for i in range(0, len(nums), 2) if i+1 < len(nums)]
            
            if n and lista_coords:
                st_supabase.table("proyectos").insert({
                    "nombre": n, "tipo": t, "telegram_id": tid, 
                    "sheet_id": sid, "pestana": pes, "umbral": umb, 
                    "coordenadas": lista_coords
                }).execute()
                st.success(f"Proyecto {n} guardado en la nube.")
                st.balloons()
