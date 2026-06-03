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
    
    print(f"🕐 Hora actual en Chile: {hora_actual:02d}:00")
    print(f"📅 Día de la semana: {dia_actual} (0=Lunes, 6=Domingo)")
    
    # Consulta: obtener clientes cuya hora coincida con la actual
    response = supabase.table("clientes_reportes").select("*").eq(
        "hora_reporte", hora_actual
    ).execute()
    
    print(f"📨 Clientes con hora={hora_actual}: {len(response.data) if response.data else 0}")
    
    clientes_filtrados = []
    
    if response.data:
        for cliente in response.data:
            frecuencia = cliente.get("frecuencia", "").lower()
            nombre_empresa = cliente.get("nombre_empresa", "N/A")
            chat_id = cliente.get("chat_id", "N/A")
            
            # Si es diario, incluye siempre
            if frecuencia == "diario":
                print(f"✅ {nombre_empresa} ({chat_id}): DIARIO")
                clientes_filtrados.append(cliente)
            
            # Si es semanal, incluye solo si es el día correcto
            elif frecuencia == "semanal":
                dia_semana_programado = cliente.get("dia_semana")
                if dia_semana_programado == dia_actual:
                    print(f"✅ {nombre_empresa} ({chat_id}): SEMANAL (día {dia_actual})")
                    clientes_filtrados.append(cliente)
                else:
                    print(f"⏭️  {nombre_empresa} ({chat_id}): Semanal, pero día {dia_semana_programado} ≠ {dia_actual}")
    
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
        if response.status_code == 200:
            print(f"✅ Reporte enviado a {nombre_empresa} ({chat_id})")
            return True
        else:
            print(f"❌ Error Telegram ({response.status_code}) para {chat_id}: {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error enviando a {chat_id}: {e}")
        return False

def main():
    """Función principal del scheduler."""
    print("=" * 70)
    print("🚀 BioCore Intelligence - Scheduler de Reportes Automáticos")
    print(f"📅 {datetime.now(TIMEZONE_CHILE).strftime('%d/%m/%Y %H:%M:%S')} (Chile)")
    print("=" * 70)
    
    clientes = obtener_clientes_para_reporte()
    
    if not clientes:
        print("ℹ️  No hay clientes para reportes en esta hora.")
        print("=" * 70)
        return
    
    print(f"\n📨 Enviando reportes a {len(clientes)} cliente(s)...\n")
    
    enviados = 0
    errores = 0
    
    for cliente in clientes:
        chat_id = cliente.get("chat_id")
        nombre_empresa = cliente.get("nombre_empresa")
        
        # TODO: Aquí iría tu lógica de generación de reporte
        # Por ahora, enviamos un mensaje simple de prueba
        contenido = (
            "✅ Reporte automático generado exitosamente.\n\n"
            f"📊 Empresa: {nombre_empresa}\n"
            f"🕐 Hora: {datetime.now(TIMEZONE_CHILE).strftime('%H:%M')}\n"
            f"📅 Fecha: {datetime.now(TIMEZONE_CHILE).strftime('%d/%m/%Y')}\n\n"
            "Los datos fueron procesados desde satélites Sentinel-2 y MODIS.\n"
            "Accede a la plataforma BioCore Intelligence para ver el análisis completo."
        )
        
        if enviar_reporte_telegram(chat_id, nombre_empresa, contenido):
            enviados += 1
        else:
            errores += 1
    
    print(f"\n{'=' * 70}")
    print(f"📊 RESUMEN: {enviados} ✅ enviados, {errores} ❌ errores")
    print("=" * 70)

if __name__ == "__main__":
    main()
