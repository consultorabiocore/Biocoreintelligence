import streamlit as st
from supabase import create_client, Client
import os
from datetime import datetime
import pytz

# ============================================================================
# CONFIGURACIÓN
# ============================================================================

# Zona horaria de Chile
TIMEZONE_CHILE = pytz.timezone("America/Santiago")

# Mapeo de días en español a índices (0=Lunes, 6=Domingo)
DIAS_SEMANA = {
    "Lunes": 0,
    "Martes": 1,
    "Miércoles": 2,
    "Jueves": 3,
    "Viernes": 4,
    "Sábado": 5,
    "Domingo": 6,
}

DIAS_SEMANA_REVERSE = {v: k for k, v in DIAS_SEMANA.items()}

# ============================================================================
# INICIALIZACIÓN DE SUPABASE
# ============================================================================

@st.cache_resource
def init_supabase_client() -> Client:
    """Inicializa el cliente de Supabase una sola vez."""
    supabase_url = st.secrets.get("supabase_url") or os.getenv("SUPABASE_URL")
    supabase_key = st.secrets.get("supabase_key") or os.getenv("SUPABASE_KEY")
    
    if not supabase_url or not supabase_key:
        st.error("❌ Falta configurar SUPABASE_URL o SUPABASE_KEY en secrets")
        st.stop()
    
    return create_client(supabase_url, supabase_key)

# ============================================================================
# FUNCIONES DE LOGICA
# ============================================================================

def obtener_reporte_existente(chat_id: str, nombre_empresa: str) -> dict | None:
    """
    Obtiene la configuración actual de un cliente si existe.
    
    Args:
        chat_id: ID del chat de Telegram
        nombre_empresa: Nombre de la empresa
    
    Returns:
        Dict con la configuración o None si no existe
    """
    try:
        supabase = init_supabase_client()
        response = supabase.table("clientes_reportes").select("*").eq(
            "chat_id", int(chat_id)
        ).eq("nombre_empresa", nombre_empresa).single().execute()
        
        return response.data if response.data else None
    except Exception as e:
        st.warning(f"⚠️ No hay configuración anterior (normal en primer acceso): {str(e)}")
        return None

def guardar_reporte(
    nombre_empresa: str,
    chat_id: str,
    frecuencia: str,
    hora_reporte: int,
    dia_semana_texto: str | None = None,
) -> bool:
    """
    Inserta o actualiza la configuración de reportes (UPSERT).
    
    Args:
        nombre_empresa: Nombre de la empresa
        chat_id: ID del chat de Telegram
        frecuencia: 'diario' o 'semanal'
        hora_reporte: Hora en formato 24h (0-23) en zona horaria de Chile
        dia_semana_texto: Día en texto ('Lunes', 'Martes', etc.) - solo para semanal
    
    Returns:
        True si la operación fue exitosa, False en caso contrario
    """
    try:
        # Convertir chat_id a entero
        chat_id_int = int(chat_id)
        
        # Mapear día de la semana si es semanal
        dia_semana_int = None
        if frecuencia == "semanal" and dia_semana_texto:
            dia_semana_int = DIAS_SEMANA.get(dia_semana_texto)
        
        # Convertir frecuencia a minúsculas
        frecuencia_lower = frecuencia.lower()
        
        # Preparar datos para UPSERT
        data = {
            "nombre_empresa": nombre_empresa,
            "chat_id": chat_id_int,
            "frecuencia": frecuencia_lower,
            "hora_reporte": hora_reporte,
            "dia_semana": dia_semana_int,
        }
        
        supabase = init_supabase_client()
        
        # Usar UPSERT (si existe, actualiza; si no, crea)
        response = supabase.table("clientes_reportes").upsert(
            data,
            on_conflict="chat_id,nombre_empresa"
        ).execute()
        
        if response.data:
            return True
        else:
            st.error("❌ Error al guardar los datos. Respuesta vacía de Supabase.")
            return False
    
    except ValueError:
        st.error(f"❌ El Chat ID debe ser un número válido. Recibiste: {chat_id}")
        return False
    except Exception as e:
        st.error(f"❌ Error al guardar la configuración: {str(e)}")
        st.write(f"Detalles técnicos: {e}")
        return False

# ============================================================================
# COMPONENTES DE UI (FORMULARIO)
# ============================================================================

def mostrar_formulario_reportes():
    """
    Muestra el formulario Streamlit para configurar reportes automáticos.
    """
    st.header("🤖 Configurar Reportes Automáticos por Telegram")
    
    st.markdown("""
    ---
    ⏱️ **Nota de Zona Horaria:** Todos los horarios se guardan en **Hora de Chile (UTC-3)**.
    El backend de GitHub Actions consultará esta tabla cada hora para enviar reportes.
    """)
    
    # Crear formulario con st.form
    with st.form("form_reportes_telegram", clear_on_submit=True):
        
        # ===== Campo: Nombre de Empresa =====
        nombre_empresa = st.text_input(
            "📊 Nombre de la Empresa",
            placeholder="Ej: Minera Los Andes",
            help="Nombre único que identifica tu empresa en el sistema"
        )
        
        # ===== Campo: Chat ID de Telegram =====
        col1, col2 = st.columns([3, 1])
        with col1:
            chat_id = st.text_input(
                "💬 Chat ID de Telegram",
                placeholder="Ej: 123456789",
                help="ID numérico de tu conversación privada con el bot"
            )
        
        with col2:
            st.markdown("### ❓ Cómo obtenerlo:")
            with st.expander("Ver instrucciones"):
                st.markdown("""
                **Opción 1: @userinfobot**
                1. Abre Telegram
                2. Busca y abre el bot: `@userinfobot`
                3. Envía cualquier mensaje
                4. El bot responderá tu User ID (cópialo)
                
                **Opción 2: @GetIdsBot**
                1. Busca en Telegram: `@GetIdsBot`
                2. Inicia el bot
                3. Tu ID aparecerá automáticamente
                """)
        
        # ===== Campo: Frecuencia =====
        frecuencia = st.radio(
            "📅 Frecuencia de Reportes",
            options=["Diario", "Semanal"],
            horizontal=True,
            help="¿Con qué frecuencia recibirás los reportes?"
        )
        
        # ===== Campo: Hora del Reporte =====
        hora_reporte = st.slider(
            "🕐 Hora del Reporte (Zona Horaria Chile)",
            min_value=0,
            max_value=23,
            value=9,
            step=1,
            format="%d:00",
            help="Hora en formato 24h (0=00:00, 9=09:00, 23=23:00)"
        )
        
        # ===== Campo Condicional: Día de la Semana =====
        dia_semana_texto = None
        if frecuencia == "Semanal":
            st.markdown("---")
            dia_semana_texto = st.selectbox(
                "📆 Día de la Semana (solo aplica si es Semanal)",
                options=list(DIAS_SEMANA.keys()),
                index=0,
                help="Selecciona el día en que deseas recibir tu reporte"
            )
        
        st.markdown("---")
        
        # ===== Botón Submit =====
        submitted = st.form_submit_button(
            "✅ Guardar Configuración",
            use_container_width=True,
            type="primary"
        )
    
    # Procesar envío del formulario
    if submitted:
        # Validaciones básicas
        if not nombre_empresa or not nombre_empresa.strip():
            st.error("❌ Por favor, ingresa el nombre de tu empresa.")
            return
        
        if not chat_id or not chat_id.strip():
            st.error("❌ Por favor, ingresa tu Chat ID de Telegram.")
            return
        
        # Validar que sea un número
        try:
            int(chat_id)
        except ValueError:
            st.error(f"❌ El Chat ID debe ser un número. Recibiste: {chat_id}")
            return
        
        # Si es semanal, validar que haya seleccionado un día
        if frecuencia == "Semanal" and not dia_semana_texto:
            st.error("❌ Por favor, selecciona un día de la semana.")
            return
        
        # Guardar en Supabase
        if guardar_reporte(
            nombre_empresa=nombre_empresa.strip(),
            chat_id=chat_id.strip(),
            frecuencia=frecuencia.lower(),
            hora_reporte=hora_reporte,
            dia_semana_texto=dia_semana_texto
        ):
            st.success(
                f"""
                ✅ **Configuración guardada correctamente!**
                
                📊 Empresa: {nombre_empresa}
                💬 Chat ID: {chat_id}
                📅 Frecuencia: {frecuencia}
                🕐 Hora: {hora_reporte:02d}:00 (Chile)
                {f"📆 Día: {dia_semana_texto}" if frecuencia == "semanal" else ""}
                
                Comenzarás a recibir reportes en tu próximo horario programado.
                """
            )
        else:
            st.error("❌ No se pudo guardar la configuración. Intenta de nuevo.")

def mostrar_resumen_reportes():
    """
    Muestra un resumen de las configuraciones guardadas (opcional).
    """
    st.subheader("📋 Mis Configuraciones de Reporte")
    
    try:
        supabase = init_supabase_client()
        response = supabase.table("clientes_reportes").select("*").execute()
        
        if response.data and len(response.data) > 0:
            # Convertir a DataFrame para visualización más clara
            import pandas as pd
            
            datos = []
            for row in response.data:
                dia_nombre = DIAS_SEMANA_REVERSE.get(row.get("dia_semana"), "-")
                datos.append({
                    "Empresa": row.get("nombre_empresa", "-"),
                    "Chat ID": row.get("chat_id", "-"),
                    "Frecuencia": row.get("frecuencia", "-").capitalize(),
                    "Hora": f"{row.get('hora_reporte', '-'):02d}:00",
                    "Día Semana": dia_nombre if row.get("frecuencia") == "semanal" else "-",
                })
            
            df = pd.DataFrame(datos)
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("📭 No hay configuraciones guardadas aún.")
    
    except Exception as e:
        st.warning(f"⚠️ No se pudo cargar el resumen: {str(e)}")

# ============================================================================
# PUNTO DE ENTRADA PRINCIPAL
# ============================================================================

if __name__ == "__main__":
    mostrar_formulario_reportes()
    st.markdown("---")
    mostrar_resumen_reportes()
