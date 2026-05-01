import streamlit as st
import pandas as pd

# --- INTERFAZ DE USUARIO ---
tab1, tab2, tab3 = st.tabs(["🚀 VIGILANCIA", "📊 HISTORIAL", "📄 CONFIGURACIÓN"])

# PESTAÑA 1: VIGILANCIA (El motor que ya tenemos)
with tab1:
    st.subheader("Auditoría de Cumplimiento Ambiental")
    # Aquí va el bucle 'for p in proyectos' con los botones de procesamiento
    # que ya construimos.

# PESTAÑA 2: HISTORIAL
with tab2:
    st.subheader("Registro de Auditorías Realizadas")
    try:
        # Consultamos una tabla de logs (puedes crearla en Supabase para guardar cada envío)
        # Por ahora, mostramos un resumen de los proyectos activos
        df_proyectos = pd.DataFrame(proyectos)
        if not df_proyectos.empty:
            st.dataframe(df_proyectos[['Proyecto', 'Tipo', 'telegram_id']], use_container_width=True)
            
            st.info("💡 Próximo paso: Conectar con tabla 'logs' para ver alertas históricas.")
        else:
            st.write("No hay datos para mostrar.")
    except Exception as e:
        st.error(f"Error al cargar historial: {e}")

# PESTAÑA 3: CONFIGURACIÓN
with tab3:
    st.subheader("Parámetros Técnicos y Legales")
    st.write("Ajusta los umbrales de alerta y referencias normativas para cada perfil.")
    
    tipo_edit = st.selectbox("Seleccionar Perfil a Editar", list(PERFILES.keys()))
    
    col1, col2 = st.columns(2)
    with col1:
        nuevo_umbral = st.number_input(f"Umbral Crítico ({PERFILES[tipo_edit]['sensor']})", 
                                       value=PERFILES[tipo_edit]['u'], step=0.05)
        nueva_ley = st.text_input("Referencia Legal / Catastro", value=PERFILES[tipo_edit]['cat'])
    
    with col2:
        nueva_ve7 = st.text_area("Explicación VE-7 (Hábitat)", value=PERFILES[tipo_edit]['ve7'])
        nueva_clima = st.text_input("Blindaje Climático", value=PERFILES[tipo_edit]['clima'])

    if st.button("Guardar Cambios en Perfil"):
        # Actualizamos el diccionario en memoria (Para que sea permanente, 
        # lo ideal sería guardarlo en una tabla 'config' de Supabase)
        PERFILES[tipo_edit]['u'] = nuevo_umbral
        PERFILES[tipo_edit]['cat'] = nueva_ley
        PERFILES[tipo_edit]['ve7'] = nueva_ve7
        PERFILES[tipo_edit]['clima'] = nueva_clima
        st.success(f"Perfil {tipo_edit} actualizado para esta sesión.")
