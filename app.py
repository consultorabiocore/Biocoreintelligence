import streamlit as st
import json
import pandas as pd
import matplotlib.pyplot as plt
import gspread
import folium
from google.oauth2.service_account import Credentials
from streamlit_folium import st_folium

# --- 1. CONFIGURACIÓN E INICIALIZACIÓN ---
st.set_page_config(page_title="BioCore Intelligence", layout="wide", page_icon="🌿")

def conectar_google():
    try:
        creds_dict = json.loads(st.secrets["GEE_JSON"])
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"Error de conexión: {e}")
        return None

gc = conectar_google()

# --- 2. BASE DE DATOS DE PROYECTOS ---
# Aquí gestionas tus clientes. Solo cambia los IDs cuando tengas carpetas nuevas.
CLIENTES_DB = {
    "Laguna Señoraza (Laja)": {
        "id": "1x6yAXNNlea3e43rijJu0aqcRpe4oP3BEnzgSgLuG1vU",
        "hoja": "Hoja 1", # Ajusta si el nombre de la pestaña cambia
        "coords": [-37.2713, -72.7095]
    },
    "Pascua Lama (Cordillera)": {
        "id": "1UTrDs939rPlVIR1OTIwbJ6rM3FazgjX43YnJdue-Dmc",
        "hoja": "Hoja 1",
        "coords": [-29.32, -70.02]
    }
}

# --- 3. INTERFAZ (SIDEBAR) ---
with st.sidebar:
    st.title("🌿 BioCore Admin")
    opcion = st.radio("Navegación:", ["📊 Panel de Auditoría", "⚙️ Configuración"])
    st.markdown("---")
    st.caption("BioCore Intelligence © 2026")

# --- MÓDULO: CONFIGURACIÓN ---
if opcion == "⚙️ Configuración":
    st.header("Gestión de Proyectos")
    st.write("Crea tu Excel en Drive y vincula el ID aquí.")
    
    with st.expander("➕ Cómo agregar un cliente nuevo"):
        st.write("""
        1. Crea un Excel en tu Drive personal.
        2. Comparte el Excel con el correo de tu cuenta de servicio como **Editor**.
        3. Copia el ID de la URL y agrégalo al código en `CLIENTES_DB`.
        """)
    
    st.info(f"Correo de la App: `{json.loads(st.secrets['GEE_JSON'])['client_email']}`")

# --- MÓDULO: AUDITORÍA ---
else:
    st.header("Panel de Vigilancia Satelital")
    proyecto_sel = st.selectbox("Seleccione Proyecto:", list(CLIENTES_DB.keys()))
    conf = CLIENTES_DB[proyecto_sel]
    
    # Botón de Sincronización
    if st.button("🔄 Sincronizar Datos Satelitales"):
        try:
            # Abrir el Excel por ID y nombre de pestaña
            sh = gc.open_by_key(conf["id"]).get_worksheet(0)
            data = sh.get_all_records()
            
            if data:
                df = pd.DataFrame(data)
                df['Fecha'] = pd.to_datetime(df['Fecha'], errors='coerce')
                # Limpiar datos numéricos
                for c in ["NDSI", "NDWI", "SWIR", "Polvo", "Deficit"]:
                    if c in df.columns:
                        df[c] = pd.to_numeric(df[c], errors='coerce')
                
                st.session_state[f"df_{proyecto_sel}"] = df
                st.success("¡Datos actualizados!")
            else:
                st.warning("El archivo está conectado pero no tiene datos registrados.")
        except Exception as e:
            st.error(f"No se pudo leer el archivo. ¿Compartiste el Excel con el correo de la App? Error: {e}")

    # Visualización de Resultados
    if f"df_{proyecto_sel}" in st.session_state:
        df_viz = st.session_state[f"df_{proyecto_sel}"]
        
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.subheader("Tendencias de Índices")
            fig, ax = plt.subplots(figsize=(10, 5))
            for idx in ["NDSI", "NDWI", "SWIR"]:
                if idx in df_viz.columns:
                    ax.plot(df_viz['Fecha'], df_viz[idx], marker='o', label=idx, linewidth=2)
            
            ax.set_ylabel("Valor del Índice")
            ax.legend()
            ax.grid(True, linestyle='--', alpha=0.6)
            plt.xticks(rotation=45)
            st.pyplot(fig)
            
        with col2:
            st.subheader("Último Registro")
            if not df_viz.empty:
                ultimo = df_viz.iloc[-1]
                st.metric("NDWI (Agua)", f"{ultimo.get('NDWI', 0):.3f}")
                st.metric("NDSI (Nieve)", f"{ultimo.get('NDSI', 0):.3f}")
                st.metric("SWIR (Humedad)", f"{ultimo.get('SWIR', 0):.3f}")

        st.markdown("---")
        
        # Mapa
        st.subheader("Área de Monitoreo")
        m = folium.Map(location=conf["coords"], zoom_start=14)
        folium.TileLayer('https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}', attr='Google', name='Google Satellite').add_to(m)
        folium.Marker(conf["coords"], popup=proyecto_sel, icon=folium.Icon(color='green', icon='leaf')).add_to(m)
        st_folium(m, width="100%", height=400, key=f"map_{proyecto_sel}")

        # Tabla inferior
        with st.expander("Ver tabla de datos completa"):
            st.dataframe(df_viz.sort_values('Fecha', ascending=False), use_container_width=True)
