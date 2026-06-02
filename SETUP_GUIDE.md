# 🚀 Guía de Configuración - Sistema de Reportes Automáticos

## 📋 Requisitos Previos

- **GitHub**: Repositorio con acceso a Settings
- **Supabase**: Proyecto PostgreSQL con credenciales
- **Telegram**: Bot creado con BotFather
- **Python 3.11+** (para testing local)

---

## ✅ Paso 1: Estructura de Base de Datos en Supabase

Tu tabla `usuarios` debe tener estas columnas:

```sql
CREATE TABLE usuarios (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    Proyecto TEXT NOT NULL,
    Tipo TEXT,
    id_telegram TEXT NOT NULL UNIQUE,
    frecuencia_reporte TEXT CHECK (frecuencia_reporte IN ('Diario', 'Semanal')),
    hora_reporte TEXT, -- Formato: "HH:MM" (ej: "09:00")
    ultimo_envio TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
