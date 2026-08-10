# Evidencias ecológicas

## Propósito

BioCore conserva una base propia de antecedentes ecológicos vinculados a una
organización y un proyecto. Una evidencia puede contener datos observados,
fotografías privadas, procedencia externa, una identificación propuesta y una
revisión profesional, manteniendo cada concepto diferenciado.

iNaturalist es una fuente complementaria. BioCore continúa funcionando si su
API pública está caída y nunca convierte su grado de calidad en una validación
profesional BioCore.

## Arquitectura

```text
platform_pages/ecological_evidence.py
    ↓
EcologicalEvidenceService
    ↓                         ↘
EcologicalEvidenceRepository   INaturalistClient
    ↓                            ↓
Supabase + Storage privado       API pública documentada
```

La página Streamlit no ejecuta SQL. El servicio valida coordenadas, permisos,
licencias, duplicados, estados y trazabilidad. El repositorio incluye siempre
`organization_id` y la base aplica RLS como segunda barrera.

## Modelo MVP

- `ecological_evidence`: antecedente, taxonomía, ubicación, procedencia,
  identificación, revisión y archivado lógico.
- `ecological_evidence_media`: múltiples fotografías propias o referencias
  externas con autor, licencia, hash, fuente y metadatos.
- `ecological_evidence_history`: bitácora append-only de creación, edición,
  coordenadas, identificación, medios, revisión y archivado.
- bucket privado `ecological-evidence`: objetos propios con URL firmada breve.

`study_area_id` es nullable hasta que Áreas de estudio tenga persistencia. No
se usa una clave foránea inexistente ni se bloquea el módulo.

## iNaturalist y licencias

La primera integración acepta una URL pública o un ID de observación. Consulta
la API documentada, no realiza scraping y guarda:

- ID y URL originales;
- observador, fecha y coordenadas públicas disponibles;
- taxón y calidad informados por la fuente;
- licencia de la observación y de cada fotografía;
- atribución.

Las fotografías externas se guardan como referencias. El MVP no copia ningún
archivo de iNaturalist al Storage de BioCore y muestra una advertencia antes de
su posible reutilización.

## Migración manual

Después de fusionar y antes de abrir el módulo en producción, ejecutar completo
en Supabase SQL Editor:

```text
database/migrations/0013_ecological_evidence.sql
```

La migración es aditiva e idempotente y debe aplicarse después de `0012`.
El rollback de estructura está en:

```text
database/rollbacks/0013_ecological_evidence_down.sql
```

El rollback preserva deliberadamente los objetos privados para recuperación.

## Prueba manual

1. Iniciar sesión y seleccionar la organización.
2. Abrir **Proyectos** y entrar al proyecto creado.
3. Pulsar **Evidencias ecológicas**.
4. Crear un registro BioCore sin nombre científico predeterminado.
5. Adjuntar dos fotografías indicando autor y licencia.
6. Verificar tabla, resumen, mapa básico y control de calidad.
7. Editar coordenadas y comprobar el historial.
8. Solicitar revisión profesional.
9. Con un rol especialista, revisar y registrar fundamento.
10. Importar solo una observación pública controlada de iNaturalist.
11. Verificar que figure como externa y que la fotografía sea un enlace, no un
    archivo copiado.
12. Archivar el registro y confirmar que desaparece de activos sin eliminar su
    historial.

## Límites explícitos

Este MVP no identifica especies con IA, no calcula riqueza o impacto, no
interpreta calidad ecológica, no usa LiDAR ni análisis satelital y no sustituye
una revisión profesional. El mapa es operativo y no reemplaza el futuro
repositorio geoespacial.
