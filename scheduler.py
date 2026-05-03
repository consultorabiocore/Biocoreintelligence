import pandas as pd
import requests
import datetime
import pytz
from supabase import create_client
import os

# 1. Configuración de Conexiones (Usa variables de entorno de GitHub)
URL = os.environ.get("SUPABASE_URL")
KEY = os.environ.get("SUPABASE_KEY")
TOKEN_TELEGRAM = os.environ.get("TELEGRAM_TOKEN")

supabase = create_client(URL, KEY)

def ejecutar_monitoreo_inteligente():
    # Configurar hora de Chile para comparar
    tz_chile = pytz.timezone('America/Santiago')
    ahora = datetime.datetime.now(tz_chile).strftime("%H:%M")
    
    print(f"⏰ Iniciando revisión de las {ahora} (Hora Chile)...")
    
    # 2. Leer todos los proyectos desde Supabase
    try:
        proyectos = supabase.table("usuarios").select("*").execute().data
    except Exception as e:
        print(f"❌ Error leyendo Supabase: {e}")
        return

    for p in proyectos:
        # 3. Comparar: ¿Es la hora de este cliente?
        # Si en la base de datos dice "08:30" y ahora son las "08:30" (o cerca)
        if p.get('hora_envio') == ahora:
            try:
                # Aquí importas tu lógica de cálculo
                from app import generar_reporte_total 
                
                txt, v_now, v_base = generar_reporte_total(p)
                
                url = f"https://api.telegram.org/bot{TOKEN_TELEGRAM}/sendMessage"
                payload = {
                    "chat_id": p['telegram_id'],
                    "text": f"🚀 *REPORTE DIARIO AUTOMÁTICO*\n\n{txt}",
                    "parse_mode": "Markdown"
                }
                requests.post(url, data=payload)
                print(f"✅ Reporte enviado con éxito a: {p['Proyecto']}")
                
            except Exception as e:
                print(f"❌ Falló el reporte para {p['Proyecto']}: {e}")
        else:
            # Solo para debug en los logs de GitHub
            print(f"⏳ {p['Proyecto']} programado para las {p['hora_envio']}. Saltando...")

if __name__ == "__main__":
    ejecutar_monitoreo_inteligente()
