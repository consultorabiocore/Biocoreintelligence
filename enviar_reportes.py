import os
from datetime import datetime
import zoneinfo  # Para manejar la hora de Chile de forma nativa
import requests
from supabase import create_client, Client

# Configuración de entornos
url: str = os.environ.get("SUPABASE_URL")
key: str = os.environ.get("SUPABASE_KEY")
TOKEN: str = os.environ.get("TELEGRAM_TOKEN")
ENVIAR_TODOS: str = os.environ.get("ENVIAR_TODOS", "false")

supabase: Client = create_client(url, key)

def obtener_clientes_programados():
    # 1. Obtener hora y día actual en Chile
    tz_chile = zoneinfo.ZoneInfo("America/Santiago")
    ahora_chile = datetime.now(tz_chile)
    
    hora_actual = ahora_chile.hour
    dia_semana_actual = ahora_chile.weekday() # 0 = Lunes, 6 = Domingo

    # Si activaste "Enviar a TODOS" manualmente desde GitHub Actions
    if ENVIAR_TODOS == "true":
        print("🔄 Modo manual: Extrayendo todos los clientes activos...")
        res = supabase.table("clientes_reportes").select("*").execute()
        return res.data

    print(f"⏰ Evaluando programación para las {hora_actual}:00 hrs (Chile) - Día: {dia_semana_actual}")

    # 2. Consultar clientes diarios para esta hora
    diarios = supabase.table("clientes_reportes")\
        .select("*")\
        .eq("hora_reporte", hora_actual)\
        .eq("frecuencia", "diario")\
        .execute().data

    # 3. Consultar clientes semanales para esta hora y este día
    semanales = supabase.table("clientes_reportes")\
        .select("*")\
        .eq("hora_reporte", hora_actual)\
        .eq("frecuencia", "semanal")\
        .eq("dia_semana", str(dia_semana_actual))\
        .execute().data

    return diarios + semanales

def enviar_reporte(chat_id, datos_cliente):
    # Aquí generas el reporte dinámico con tus índices de biodiversidad
    mensaje = f"📊 *Reporte de Biodiversidad para {datos_cliente['nombre_empresa']}*\n\n..."
    
    url_tg = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": mensaje, "parse_mode": "Markdown"}
    
    res = requests.post(url_tg, json=payload)
    return res.status_code == 200

if __name__ == "__main__":
    clientes = obtener_clientes_programados()
    print(f"👥 Clientes encontrados para procesar: {len(clientes)}")
    
    for cliente in clientes:
        chat_id = cliente.get("chat_id")
        if chat_id:
            exito = enviar_reporte(chat_id, cliente)
            if exito:
                print(f"✅ Reporte enviado a {cliente['nombre_empresa']}")
            else:
                print(f"❌ Falló el envío a {cliente['nombre_empresa']}")
