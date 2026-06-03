import os
from datetime import datetime
import pytz
from supabase import create_client, Client
import requests

# Zona horaria de Chile
TIMEZONE_CHILE = pytz.timezone("America/Santiago")

def obtener_hora_actual_chile() -> int:
    """Obtiene la hora actual en Chile (0-23)."""
    ahora = datetime.now(TIMEZONE_CHILE)
    return ahora.hour

def obtener_dia_semana_actual() -> int:
    """Obtiene el día de la semana actual (0=Lunes, 6=Domingo)."""
    ahora = datetime.now(TIMEZONE_CHILE)
    return ahora.weekday()

def obtener_clientes_para_reporte() -> list:
    """
    Consulta Supabase y devuelve los clientes que deben recibir reporte HOY.
    """
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    supabase: Client = create_client(supabase_url, supabase_key)
    
    hora_actual = obtener_hora_actual_chile()
    dia_actual = obtener_dia_semana_actual()
    
    # Consulta: obtener clientes cuya hora coincida con la actual
    response = supabase.table("clientes_reportes").select("*").eq(
        "hora_reporte", hora_actual
    ).execute()
    
    clientes_filtrados = []
    
    for cliente in response.data:
        frecuencia = cliente.get("frecuencia", "").lower()
        
        # Si es diario, incluye siempre
        if frecuencia == "diario":
            clientes_filtrados.append(cliente)
        
        # Si es semanal, incluye solo si es el día correcto
        elif frecuencia == "semanal":
            dia_semana_programado = cliente.get("dia_semana")
            if dia_semana_programado == dia_actual:
                clientes_filtrados.append(cliente)
    
    return clientes_filtrados

def enviar_reporte_telegram(chat_id: int, nombre_empresa: str, contenido: str) -> bool:
    """
    Envía un mensaje por Telegram.
    """
    token = os.getenv("TELEGRAM_TOKEN")
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    
    payload = {
        "chat_id": chat_id,
        "text": f"📊 **Reporte {nombre_empresa}**\n\n{contenido}",
        "parse_mode": "Markdown"
    }
    
    try:
        response = requests.post(url, json=payload, timeout=10)
        return response.status_code == 200
    except Exception as e:
        print(f"❌ Error enviando a {chat_id}: {e}")
        return False

def main():
    """Función principal del scheduler."""
    print("🚀 Iniciando envío de reportes automáticos...")
    
    clientes = obtener_clientes_para_reporte()
    
    if not clientes:
        print("ℹ️ No hay clientes para reportes en esta hora.")
        return
    
    print(f"📨 Enviando reportes a {len(clientes)} cliente(s)...")
    
    for cliente in clientes:
        chat_id = cliente.get("chat_id")
        nombre_empresa = cliente.get("nombre_empresa")
        
        # TODO: Aquí iría tu lógica de generación de reporte
        contenido = "Reporte generado exitosamente."
        
        if enviar_reporte_telegram(chat_id, nombre_empresa, contenido):
            print(f"✅ Reporte enviado a {nombre_empresa} ({chat_id})")
        else:
            print(f"❌ Error enviando reporte a {nombre_empresa} ({chat_id})")

if __name__ == "__main__":
    main()
