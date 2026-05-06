"""
BioCore Intelligence — Scheduler de Reportes Automáticos
=========================================================
Se ejecuta diariamente via GitHub Actions.
Revisa en Supabase qué clientes deben recibir reporte hoy
(según su frecuencia: Diario o Semanal) y les envía
el mensaje por Telegram.

Variables de entorno requeridas (GitHub Secrets):
  SUPABASE_URL    → URL de tu proyecto Supabase
  SUPABASE_KEY    → Clave anon/service de Supabase
  TELEGRAM_TOKEN  → Token del bot de Telegram
  GEE_JSON        → JSON de credenciales de Google Earth Engine
  FORZAR_TODOS    → 'true' para ignorar frecuencia (dispatch manual)
"""

import os
import json
import requests
import hashlib
from datetime import datetime, timezone
from supabase import create_client

# ============================================================
# CONFIGURACIÓN
# ============================================================

SUPABASE_URL   = os.environ["SUPABASE_URL"]
SUPABASE_KEY   = os.environ["SUPABASE_KEY"]
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
GEE_JSON_STR   = os.environ.get("GEE_JSON", "")
FORZAR_TODOS   = os.environ.get("FORZAR_TODOS", "false").lower() == "true"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# Hora y día actual en Chile (UTC-3)
from datetime import timedelta
ahora_chile = datetime.now(timezone.utc) - timedelta(hours=3)
hora_actual  = ahora_chile.strftime("%H:%M")
dia_semana   = ahora_chile.weekday()   # 0=Lunes … 6=Domingo
es_lunes     = dia_semana == 0


# ============================================================
# FUNCIONES AUXILIARES
# ============================================================

def debe_enviar_hoy(cliente: dict) -> bool:
    """Decide si este cliente recibe reporte hoy."""
    if FORZAR_TODOS:
        return True

    frecuencia = (cliente.get("frecuencia_reporte") or "Diario").strip()
    hora_cfg   = (cliente.get("hora_reporte") or "09:00").strip()

    # Tolerancia ±30 min para que no importa si GitHub Actions corre
    # unos minutos tarde
    hh_cfg, mm_cfg = map(int, hora_cfg.split(":"))
    hh_act, mm_act = map(int, hora_actual.split(":"))
    minutos_cfg = hh_cfg * 60 + mm_cfg
    minutos_act = hh_act * 60 + mm_act
    en_ventana  = abs(minutos_act - minutos_cfg) <= 30

    if frecuencia == "Diario":
        return en_ventana
    elif frecuencia == "Semanal":
        # Semanal = solo los lunes dentro de la ventana horaria
        return es_lunes and en_ventana
    else:
        return en_ventana


def generar_mensaje(cliente: dict, indices: dict) -> str:
    """Genera el mensaje de Telegram para el cliente."""
    proyecto = cliente.get("Proyecto", "N/A")
    tipo     = cliente.get("Tipo", "GENERAL").upper()
    fecha    = ahora_chile.strftime("%d/%m/%Y %H:%M")

    savi  = indices.get("savi",  0.0)
    ndwi  = indices.get("ndwi",  0.0)
    ndsi  = indices.get("ndsi",  0.0)
    temp  = indices.get("temp",  0.0)
    nivel = indices.get("nivel", "DESCONOCIDO")
    estado= indices.get("estado","")

    # Emoji según nivel
    emoji = {"NORMAL": "🟢", "MODERADO": "🟡", "CRÍTICO": "🔴"}.get(nivel, "⚪")

    mensaje = f"""
╔══════════════════════════════════════════╗
║   🛰️  BIOCORE INTELLIGENCE  🛰️          ║
║      REPORTE AUTOMÁTICO SATELITAL        ║
╚══════════════════════════════════════════╝

📍 *Proyecto:* {proyecto}
📊 *Tipo:* {tipo}
📅 *Fecha:* {fecha}

{emoji} *Estado:* {estado}
⚠️ *Nivel de Riesgo:* {nivel}

📈 *Índices Espectrales:*
  • SAVI (Vegetación): `{savi:.4f}`
  • NDWI (Agua):       `{ndwi:.4f}`
  • NDSI (Nieve/Hielo):`{ndsi:.4f}`
  • Temperatura LST:   `{temp:.1f}°C`

🔗 Ver reporte completo en BioCore Intelligence
📧 consultorabiocore@gmail.com

_BioCore Intelligence © {ahora_chile.year}_
"""
    return mensaje.strip()


def obtener_indices_supabase(proyecto: str) -> dict:
    """
    Obtiene los últimos índices del historial guardado en Supabase.
    Si no hay historial, devuelve valores en cero.
    """
    try:
        res = supabase.table("historial_reportes")\
            .select("*")\
            .eq("proyecto", proyecto)\
            .order("created_at", desc=True)\
            .limit(1)\
            .execute()

        if res.data:
            r = res.data[0]
            return {
                "savi":   r.get("savi_actual", 0.0),
                "ndwi":   r.get("ndwi_actual", 0.0),
                "ndsi":   r.get("ndsi_actual", 0.0),
                "temp":   r.get("temperatura",  0.0),
                "nivel":  r.get("nivel",        "DESCONOCIDO"),
                "estado": r.get("estado",       "Sin datos recientes"),
            }
    except Exception as e:
        print(f"  ⚠️  Error leyendo historial de {proyecto}: {e}")

    return {
        "savi": 0.0, "ndwi": 0.0, "ndsi": 0.0,
        "temp": 0.0, "nivel": "SIN DATOS", "estado": "Sin análisis reciente disponible"
    }


def enviar_telegram(chat_id: str, mensaje: str) -> bool:
    """Envía un mensaje por Telegram. Retorna True si tuvo éxito."""
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        resp = requests.post(url, json={
            "chat_id":    chat_id,
            "text":       mensaje,
            "parse_mode": "Markdown"
        }, timeout=15)

        if resp.status_code == 200:
            return True
        else:
            print(f"  ❌ Telegram error {resp.status_code}: {resp.text[:200]}")
            return False
    except Exception as e:
        print(f"  ❌ Excepción al enviar Telegram: {e}")
        return False


def guardar_log(proyecto: str, exito: bool, detalle: str = ""):
    """Guarda un registro del envío en Supabase (tabla historial_reportes o logs)."""
    try:
        supabase.table("historial_reportes").insert({
            "proyecto":      proyecto,
            "tipo":          "LOG_TELEGRAM",
            "fecha_analisis": ahora_chile.strftime("%d/%m/%Y"),
            "estado":        "Enviado OK" if exito else f"Error: {detalle}",
            "nivel":         "AUTO",
            "created_at":    datetime.now(timezone.utc).isoformat()
        }).execute()
    except Exception:
        pass   # El log no debe interrumpir el flujo principal


# ============================================================
# FLUJO PRINCIPAL
# ============================================================

def main():
    print("=" * 55)
    print(f"  BioCore Scheduler — {ahora_chile.strftime('%d/%m/%Y %H:%M')} (hora Chile)")
    print(f"  Forzar todos: {FORZAR_TODOS} | Día semana: {dia_semana} | Es lunes: {es_lunes}")
    print("=" * 55)

    # 1. Obtener todos los clientes con Telegram configurado
    try:
        res = supabase.table("usuarios")\
            .select("Proyecto, Tipo, id_telegram, frecuencia_reporte, hora_reporte")\
            .not_.is_("id_telegram", "null")\
            .execute()
        clientes = res.data or []
    except Exception as e:
        print(f"❌ No se pudo conectar a Supabase: {e}")
        return

    print(f"  Clientes con Telegram: {len(clientes)}")
    print()

    enviados  = 0
    omitidos  = 0
    errores   = 0

    for cliente in clientes:
        proyecto  = cliente.get("Proyecto", "?")
        chat_id   = cliente.get("id_telegram", "")
        frecuencia= cliente.get("frecuencia_reporte", "Diario")
        hora_cfg  = cliente.get("hora_reporte", "09:00")

        print(f"  → {proyecto} | {frecuencia} | {hora_cfg} | chat_id: {chat_id}")

        if not chat_id:
            print("     ⏭️  Sin chat_id, omitido.")
            omitidos += 1
            continue

        if not debe_enviar_hoy(cliente):
            print("     ⏭️  No corresponde enviar hoy/ahora.")
            omitidos += 1
            continue

        # Obtener últimos índices del historial
        indices = obtener_indices_supabase(proyecto)

        # Generar y enviar mensaje
        mensaje = generar_mensaje(cliente, indices)
        exito   = enviar_telegram(chat_id, mensaje)

        if exito:
            print("     ✅ Enviado correctamente.")
            guardar_log(proyecto, True)
            enviados += 1
        else:
            print("     ❌ Falló el envío.")
            guardar_log(proyecto, False, "Error en API Telegram")
            errores += 1

    print()
    print("=" * 55)
    print(f"  RESUMEN: ✅ {enviados} enviados | ⏭️ {omitidos} omitidos | ❌ {errores} errores")
    print("=" * 55)

    # Si hubo errores, salir con código 1 (GitHub Actions lo marcará como fallido)
    if errores > 0:
        exit(1)


if __name__ == "__main__":
    main()
