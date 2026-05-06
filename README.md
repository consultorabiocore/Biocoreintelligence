# BioCore Intelligence — Reportes Automáticos vía GitHub Actions

Este repositorio envía reportes satelitales automáticos por Telegram
a los clientes de BioCore Intelligence, gratis y sin servidor.

---

## ¿Cómo funciona?

```
Todos los días a las 09:00 (hora Chile)
        ↓
GitHub Actions despierta automáticamente
        ↓
scheduler/enviar_reportes.py se ejecuta
        ↓
Consulta Supabase → ¿quién recibe reporte hoy?
        ↓
Envía mensaje por Telegram a cada cliente
```

---

## Configuración paso a paso

### 1. Crear el repositorio en GitHub

1. Ve a https://github.com/new
2. Nombre: `biocore-scheduler` (puede ser **privado** ✅)
3. Sube estos archivos tal como están

### 2. Agregar los Secrets (contraseñas) en GitHub

Ve a tu repositorio → **Settings** → **Secrets and variables** → **Actions** → **New repository secret**

Agrega estos 4 secrets:

| Nombre del Secret | Valor |
|---|---|
| `SUPABASE_URL` | La URL de tu proyecto Supabase (ej: `https://xxxxx.supabase.co`) |
| `SUPABASE_KEY` | La `anon public key` de Supabase (en Project Settings → API) |
| `TELEGRAM_TOKEN` | El token de tu bot de Telegram (del BotFather) |
| `GEE_JSON` | El JSON completo de credenciales de Google Earth Engine (en una sola línea) |

### 3. Verificar que funciona

1. Ve a tu repositorio → pestaña **Actions**
2. Haz clic en **"BioCore - Reportes Automáticos Telegram"**
3. Haz clic en **"Run workflow"** → **"Run workflow"**
4. Revisa los logs — deberías ver el resumen de envíos

---

## Horario

El workflow corre automáticamente todos los días a las **09:00 hora Chile**.

Internamente usa `cron: '0 12 * * *'` (12:00 UTC = 09:00 Chile UTC-3).

> **Nota:** GitHub Actions puede tardar hasta 10-15 minutos extra en ejecutarse
> en horarios de alta demanda. Esto es normal en el plan gratuito.

### ¿Qué pasa con los clientes "Semanal"?

El script solo les envía los **lunes**. El resto de días los omite aunque el
workflow corra.

---

## Ejecución manual (cuando quieras)

Puedes forzar el envío a **todos** los clientes desde GitHub:

1. Ve a **Actions** → **BioCore - Reportes Automáticos Telegram**
2. Clic en **"Run workflow"**
3. En el campo "¿Enviar a TODOS?" escribe `true`
4. Clic en **"Run workflow"**

---

## Estructura del repositorio

```
biocore-scheduler/
├── .github/
│   └── workflows/
│       └── reportes_diarios.yml   ← Configuración de GitHub Actions
├── scheduler/
│   └── enviar_reportes.py         ← Script principal
└── README.md
```

---

## Plan gratuito de GitHub Actions

| Límite | Plan Free |
|---|---|
| Minutos/mes | 2,000 minutos |
| Uso estimado BioCore (1 ejecución/día × ~1 min) | ~30 minutos/mes |
| Costo | **$0** ✅ |

Con el uso de BioCore usarás solo el **1.5% del límite gratuito mensual**.

---

## Tabla de clientes en Supabase requerida

El script lee la tabla `usuarios` con estas columnas:

| Columna | Tipo | Ejemplo |
|---|---|---|
| `Proyecto` | text | "Minera Los Andes" |
| `Tipo` | text | "MINERIA" |
| `id_telegram` | text | "123456789" |
| `frecuencia_reporte` | text | "Diario" o "Semanal" |
| `hora_reporte` | text | "09:00" |

Y lee la tabla `historial_reportes` para obtener los últimos índices de cada proyecto.

---

*BioCore Intelligence © 2026 — Loreto Campos Carrasco*
