import streamlit as st
import pandas as pd
import re, json, requests
from st_supabase_connection import SupabaseConnection
import gspread
from google.oauth2.service_account import Credentials
import folium
from streamlit_folium import folium_static

# --- 1. CONFIGURACIÓN INICIAL ---
st.set_page_config(page_title="BioCore Intelligence | SEIA", layout="wide")
st.cache_resource.clear()

# --- 2. CONEXIÓN A BASE DE DATOS (SUPABASE) ---
try:
    s_url = st.secrets["connections"]["supabase"]["url"].strip()
    s_key = st.secrets["connections"]["supabase"]["key"].strip()

    st_supabase = st.connection(
        "supabase",
        type=SupabaseConnection,
        url=s_url,
        key=s_key
    )
except Exception as e:
    st.error("❌ Error de conexión con Supabase. Revisa tus Secrets.")
    st.stop()

# --- 3. FUNCIONES DE APOYO ---
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
        sid = sheet_id.split("/d/")[1].split("/")[0] if "/d/" in sheet_id else sheet_id
        sh = client.open_by_key(sid)
        df = pd.DataFrame(sh.worksheet(pestana).get_all_records())
        
        # --- LIMPIEZA DE DATOS (EVITA EL ERROR DE TYPEERROR) ---
        df.columns = [c.strip().upper() for c in df.columns]
        
        # Forzamos conversión a número en columnas críticas
        for col in ['NDSI', 'NDWI', 'SAVI']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # Eliminamos filas donde los índices sean nulos
        df = df.dropna(subset=['NDSI', 'NDWI'], how='all')
        
        if 'FECHA' in df.columns:
            df['FECHA'] = pd.to_datetime(df['FECHA'], dayfirst=True)
        return df
    except Exception as e:
        st.error(f"Error leyendo Google Sheets: {e}")
        return pd.DataFrame()

# --- 4. INTERFAZ Y NAVEGACIÓN ---
menu = st.sidebar.radio("SISTEMA BIOCORE", ["🛡️ Auditoría", "⚙️ Gestión de Clientes"])

if menu == "🛡️ Auditoría":
    st.title("🛡️ Dashboard de Vigilancia Ambiental")
    
    try:
        res = st_supabase.table("proyectos").select("*").execute()
        proyectos = res.data
    except:
        proyectos = []

    if proyectos:
        nombres = [p['nombre'] for p in proyectos]
        sel = st.selectbox("Seleccione Unidad de Monitoreo:", nombres)
        info = next(p for p in proyectos if p['nombre'] == sel)
        
        c1, c2 = st.columns([1, 1.2])
        with c1:
            st.info(f"**Ecosistema:** {info['tipo']}")
            if st.button("🚀 EJECUTAR MONITOREO"):
                with st.spinner("Procesando datos..."):
                    df = cargar_datos_google(info['sheet_id'], info['pestana'])
                    
                    if not df.empty:
                        idx = "NDSI" if info['tipo'] == "MINERIA" else "NDWI"
                        
                        # Verificamos que la columna exista y tenga números
                        if idx in df.columns and not df[idx].isnull().all():
                            val_act = df[idx].iloc[-1]
                            promedio = df[idx].mean() # Ahora seguro porque limpiamos el DF antes
                            
                            estado = "🟢 ESTABLE" if val_act >= info['umbral'] else "🔴 ALERTA"
                            enviar_telegram(f"🛰 **BIOCORE: {info['nombre']}**\n{idx}: `{val_act:.3f}`\n{estado}", info['telegram_id'])
                            
                            st.metric(f"Último {idx}", f"{val_act:.3f}", f"{((val_act-promedio)/promedio)*100:+.1f}%")
                            st.line_chart(df.set_index('FECHA')[[idx, 'SAVI']])
                        else:
                            st.error(f"La columna {idx} no tiene datos numéricos válidos.")
        with c2:
            if info['coordenadas']:
                m = folium.Map(location=info['coordenadas'][0], zoom_start=13)
                folium.Polygon(locations=info['coordenadas'], color="#1a3a5a", fill=True).add_to(m)
                folium_static(m)
    else:
        st.warning("No hay proyectos. Regístralos en la pestaña de Gestión.")

else:
    st.title("⚙️ Registro de Unidades")
    with st.form("reg_form", clear_on_submit=True):
        col_a, col_b = st.columns(2)
        with col_a:
            n = st.text_input("Nombre del Proyecto")
            t = st.selectbox("Ecosistema", ["MINERIA", "HUMEDAL"])
            sid = st.text_input("Google Sheet ID")
        with col_b:
            tid = st.text_input("Telegram ID")
            pes = st.text_input("Pestaña", value="Hoja 1")
            umb = st.number_input("Umbral Alerta", value=0.35 if t=="MINERIA" else 0.10)
        
        cor = st.text_area("Coordenadas (Lat, Lon)")
        
        if st.form_submit_button("💾 Guardar"):
            nums = re.findall(r"[-+]?\d*\.\d+|[-+]?\d+", cor)
            coords = [[float(nums[i]), float(nums[i+1])] for i in range(0, len(nums), 2) if i+1 < len(nums)]
            if n and coords:
                st_supabase.table("proyectos").insert({
                    "nombre": n, "tipo": t, "telegram_id": tid, 
                    "sheet_id": sid, "pestana": pes, "umbral": umb, "coordenadas": coords
                }).execute()
                st.success("Guardado.")
