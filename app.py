import streamlit as st
import pandas as pd
import re, json, requests
from st_supabase_connection import SupabaseConnection
import gspread
from google.oauth2.service_account import Credentials
import folium
from streamlit_folium import folium_static

# --- 1. CONFIGURACIÓN DE PÁGINA (DEBE IR PRIMERO) ---
st.set_page_config(page_title="BioCore Intelligence | SEIA", layout="wide")

# --- 2. LIMPIEZA DE CONEXIONES Y CACHÉ ---
st.cache_resource.clear()

# --- 3. CONEXIÓN A SUPABASE ---
try:
    # Usamos strip() para limpiar cualquier espacio invisible en tus Secrets
    s_url = st.secrets["connections"]["supabase"]["url"].strip()
    s_key = st.secrets["connections"]["supabase"]["key"].strip()

    st_supabase = st.connection(
        "supabase",
        type=SupabaseConnection,
        url=s_url,
        key=s_key
    )
except Exception as e:
    st.error("❌ Error de conexión. Revisa que los Secrets tengan la URL con la 'q'.")
    st.stop()

# --- 4. ESTILOS PERSONALIZADOS ---
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stMetric { background-color: white; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    .stButton>button { background-color: #1a3a5a; color: white; border-radius: 5px; width: 100%; }
    </style>
    """, unsafe_allow_html=True)

# --- 5. FUNCIONES LÓGICAS ---
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
        df.columns = [c.strip().upper() for c in df.columns]
        if 'FECHA' in df.columns:
            df['FECHA'] = pd.to_datetime(df['FECHA'], dayfirst=True)
        return df
    except Exception:
        return pd.DataFrame()

# --- 6. NAVEGACIÓN ---
menu = st.sidebar.radio("SISTEMA DE VIGILANCIA", ["🛡️ Auditoría", "⚙️ Gestión de Clientes"])

# --- VISTA: AUDITORÍA ---
if menu == "🛡️ Auditoría":
    st.title("🛡️ Dashboard de Vigilancia Ambiental")
    
    try:
        res = st_supabase.table("proyectos").select("*").execute()
        proyectos = res.data
    except Exception:
        proyectos = []
        st.warning("⚠️ Esperando datos de la base de datos...")

    if proyectos:
        nombres = [p['nombre'] for p in proyectos]
        sel = st.selectbox("Seleccione Unidad de Monitoreo:", nombres)
        info = next(p for p in proyectos if p['nombre'] == sel)
        
        c1, c2 = st.columns([1, 1.2])
        with c1:
            st.info(f"**Ecosistema:** {info['tipo']}")
            if st.button("🚀 EJECUTAR MONITOREO"):
                with st.spinner("Analizando satélites..."):
                    df = cargar_datos_google(info['sheet_id'], info['pestana'])
                    if not df.empty:
                        idx = "NDSI" if info['tipo'] == "MINERIA" else "NDWI"
                        val_act = df[idx].iloc[-1]
                        promedio = df[idx].mean()
                        
                        estado = "🟢 ESTABLE" if val_act >= info['umbral'] else "🔴 ALERTA"
                        msg = f"🛰 **BIOCORE: {info['nombre']}**\nIndicador {idx}: `{val_act:.3f}`\nEstado: {estado}"
                        enviar_telegram(msg, info['telegram_id'])
                        
                        st.metric(f"Último {idx}", f"{val_act:.3f}", f"{((val_act-promedio)/promedio)*100:+.1f}%")
                        st.line_chart(df.set_index('FECHA')[[idx, 'SAVI']])
                        st.success("Auditoría reportada.")
        with c2:
            if info['coordenadas']:
                m = folium.Map(location=info['coordenadas'][0], zoom_start=13)
                folium.Polygon(locations=info['coordenadas'], color="#1a3a5a", fill=True).add_to(m)
                folium_static(m)
    else:
        st.info("No hay proyectos registrados. Ve a la pestaña de Gestión.")

# --- VISTA: GESTIÓN ---
else:
    st.title("⚙️ Registro de Clientes")
    with st.form("registro_form", clear_on_submit=True):
        col_a, col_b = st.columns(2)
        with col_a:
            n = st.text_input("Nombre del Proyecto")
            t = st.selectbox("Ecosistema", ["MINERIA", "HUMEDAL"])
            sid = st.text_input("Google Sheet ID")
        with col_b:
            tid = st.text_input("Telegram ID Cliente")
            pes = st.text_input("Pestaña Sheet", value="Hoja 1")
            umb = st.number_input("Umbral Crítico", value=0.35 if t=="MINERIA" else 0.10)
        
        cor = st.text_area("Coordenadas (Lat, Lon)")
        
        if st.form_submit_button("💾 Guardar en Base de Datos"):
            nums = re.findall(r"[-+]?\d*\.\d+|[-+]?\d+", cor)
            coords = [[float(nums[i]), float(nums[i+1])] for i in range(0, len(nums), 2) if i+1 < len(nums)]
            
            if n and coords:
                try:
                    st_supabase.table("proyectos").insert({
                        "nombre": n, "tipo": t, "telegram_id": tid, 
                        "sheet_id": sid, "pestana": pes, "umbral": umb, "coordenadas": coords
                    }).execute()
                    st.success(f"✅ Proyecto {n} registrado con éxito.")
                    st.balloons()
                except Exception as e:
                    st.error(f"Error al guardar: {e}")
            else:
                st.error("Por favor, ingresa el nombre y las coordenadas.")
