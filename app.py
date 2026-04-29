import streamlit as st
import pandas as pd
import re, json, requests
from st_supabase_connection import SupabaseConnection
import gspread
from google.oauth2.service_account import Credentials
import folium
from streamlit_folium import folium_static

# --- 1. CONEXIÓN A BASE DE DATOS (SUPABASE) ---
# Usamos el conector oficial para asegurar persistencia
try:
    st_supabase = st.connection(
        "supabase",
        type=SupabaseConnection,
        url=st.secrets["connections"]["supabase"]["url"],
        key=st.secrets["connections"]["supabase"]["key"]
    )
except Exception as e:
    st.error("Error de conexión con la base de datos. Verifica los Secrets.")
    st.stop()

# --- 2. CONFIGURACIÓN DE INTERFAZ ---
st.set_page_config(page_title="BioCore Intelligence | SEIA", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #f4f7f9; }
    .stMetric { background-color: white; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    .sidebar .sidebar-content { background-color: #1a3a5a; }
    </style>
    """, unsafe_allow_html=True)

# --- 3. FUNCIONES LÓGICAS ---
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
        # Limpiador de ID de Google Sheets
        sid = sheet_id.split("/d/")[1].split("/")[0] if "/d/" in sheet_id else sheet_id
        sh = client.open_by_key(sid)
        df = pd.DataFrame(sh.worksheet(pestana).get_all_records())
        df.columns = [c.strip().upper() for c in df.columns]
        if 'FECHA' in df.columns:
            df['FECHA'] = pd.to_datetime(df['FECHA'], dayfirst=True)
        return df
    except Exception as e:
        st.error(f"Error de acceso a datos: {e}")
        return pd.DataFrame()

# --- 4. NAVEGACIÓN ---
menu = st.sidebar.radio("MENÚ PRINCIPAL", ["🛡️ Auditoría Ambiental", "⚙️ Gestión de Clientes"])

# --- VISTA: AUDITORÍA ---
if menu == "🛡️ Auditoría Ambiental":
    st.title("🛡️ Dashboard de Vigilancia de Alto Nivel")
    
    # Consulta a Supabase para obtener la lista de clientes
    res = st_supabase.table("proyectos").select("*").execute()
    proyectos = res.data
    
    if proyectos:
        nombres = [p['nombre'] for p in proyectos]
        seleccion = st.selectbox("Seleccione Unidad de Monitoreo:", nombres)
        info = next(p for p in proyectos if p['nombre'] == seleccion)
        
        col_info, col_map = st.columns([1, 1.2])
        
        with col_info:
            st.subheader(f"Ecosistema: {info['tipo']}")
            if st.button("🚀 INICIAR AUDITORÍA SATELITAL"):
                with st.spinner("Procesando índices..."):
                    df = cargar_datos_google(info['sheet_id'], info['pestana'])
                    if not df.empty:
                        idx = "NDSI" if info['tipo'] == "MINERIA" else "NDWI"
                        val_actual = df[idx].iloc[-1]
                        promedio = df[idx].mean()
                        
                        # Alerta
                        estado = "🟢 ESTABLE" if val_actual >= info['umbral'] else "🔴 ALERTA"
                        msg = f"🛰 **BIOCORE INFORME: {info['nombre']}**\nIndicador {idx}: `{val_actual:.3f}`\nEstado: {estado}"
                        enviar_telegram(msg, info['telegram_id'])
                        
                        # Dashboard Visual
                        st.metric(f"Último {idx}", f"{val_actual:.3f}", f"{((val_actual-promedio)/promedio)*100:+.2f}% vs Media")
                        st.line_chart(df.set_index('FECHA')[[idx, 'SAVI']])
                        st.success("Auditoría completada y reportada a Telegram.")
        
        with col_map:
            st.subheader("Ubicación del Polígono")
            if info['coordenadas']:
                m = folium.Map(location=info['coordenadas'][0], zoom_start=13)
                folium.Polygon(locations=info['coordenadas'], color="#1a3a5a", fill=True, fill_opacity=0.4).add_to(m)
                folium_static(m)
    else:
        st.info("No hay proyectos registrados. Vaya a la pestaña de Gestión.")

# --- VISTA: GESTIÓN ---
else:
    st.title("⚙️ Registro de Clientes y Proyectos")
    st.markdown("Añada nuevos polígonos de vigilancia directamente a la base de datos SQL.")
    
    with st.form("registro_supabase", clear_on_submit=True):
        col1, col2 = st.columns(2)
        with col1:
            n = st.text_input("Nombre del Proyecto / Empresa")
            t = st.selectbox("Tipo de Ecosistema", ["MINERIA", "HUMEDAL"])
            sid = st.text_input("ID Google Sheet")
        with col2:
            tid = st.text_input("Chat ID Telegram (Notificación)")
            pes = st.text_input("Nombre de la Pestaña", value="Hoja 1")
            umb = st.number_input("Umbral Crítico de Índice", value=0.35 if t=="MINERIA" else 0.10)
        
        cor = st.text_area("Coordenadas del Polígono (Lat, Lon)")
        
        if st.form_submit_button("💾 Guardar en Base de Datos"):
            # Procesamiento de coordenadas
            nums = re.findall(r"[-+]?\d*\.\d+|[-+]?\d+", cor)
            lista_coords = [[float(nums[i]), float(nums[i+1])] for i in range(0, len(nums), 2) if i+1 < len(nums)]
            
            if n and lista_coords:
                try:
                    st_supabase.table("proyectos").insert({
                        "nombre": n, "tipo": t, "telegram_id": tid, 
                        "sheet_id": sid, "pestana": pes, "umbral": umb, 
                        "coordenadas": lista_coords
                    }).execute()
                    st.success(f"Proyecto {n} guardado exitosamente en Supabase.")
                    st.balloons()
                except Exception as e:
                    st.error(f"Error al guardar: {e}")
            else:
                st.warning("Asegúrese de ingresar el nombre y las coordenadas correctamente.")
