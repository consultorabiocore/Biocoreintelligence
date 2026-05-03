import pandas as pd
import requests
import datetime
from app import generar_reporte_total # Reutilizamos tu lógica actual

# --- CONFIGURACIÓN DE HORA ---
# Aquí puedes ajustar la lógica según lo que pida el cliente
HORA_ENVIO = "09:00" # Formato 24h

def ejecutar_monitoreo_diario():
    print(f"Iniciando ciclo de monitoreo: {datetime.datetime.now()}")
    
    # Supongamos que tienes tus proyectos en un CSV o Lista
    proyectos = [
        {'Proyecto': 'Pascua Lama', 'telegram_id': 'TU_ID', 'Tipo': 'Minería'},
        # Aquí irían los demás...
    ]
    
    for p in proyectos:
        try:
            txt, v_now, v_base = generar_reporte_total(p)
            token = "TU_BOT_TOKEN" # O usa variables de entorno
            
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            payload = {
                "chat_id": p['telegram_id'],
                "text": f"📢 *REPORTE DIARIO AUTOMÁTICO*\n\n{txt}",
                "parse_mode": "Markdown"
            }
            requests.post(url, data=payload)
            print(f"✅ Reporte enviado: {p['Proyecto']}")
        except Exception as e:
            print(f"❌ Error en {p['Proyecto']}: {e}")

if __name__ == "__main__":
    ejecutar_monitoreo_diario()
