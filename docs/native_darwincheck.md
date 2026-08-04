# DarwinCheck nativo

DarwinCheck se ejecuta dentro de la plataforma privada BioCore. La URL
independiente se conserva solo como respaldo durante la validación de esta
integración.

## Flujo

1. La plataforma resuelve identidad, organización, roles y suscripción.
2. La persona selecciona un proyecto de la organización activa.
3. DarwinCheck acepta una planilla Excel con hoja `Ocurrencia` y la estructura
   Darwin Core/SMA utilizada por la aplicación original.
4. El motor aplica reglas deterministas sobre estructura, taxonomía,
   coordenadas, horas e índices ecológicos.
5. La ejecución se registra en `darwincheck_runs` con organización, proyecto,
   usuario, hash SHA-256, referencia taxonómica, resumen y hallazgos.
6. El archivo revisado se descarga con hojas de resumen, hallazgos,
   trazabilidad y contexto BioCore.

## Límites científicos visibles

- Solo se aplican correcciones taxonómicas cuando existe una coincidencia
  exacta y única en la referencia SIMBIO versionada.
- Una coincidencia de texto no confirma la identidad biológica.
- Las comprobaciones geográficas son geométricas y no constituyen una
  determinación administrativa.
- Los índices ecológicos son cálculos derivados de los valores numéricos
  disponibles.
- DarwinCheck no usa IA generativa para corregir o puntuar la planilla.
- El resultado es preliminar: no certifica cumplimiento ni reemplaza una
  revisión profesional.

## Seguridad y aislamiento

- `DarwinCheckService` exige `darwincheck:write` para ejecutar y
  `darwincheck:read` para consultar.
- El proyecto se obtiene mediante `(organization_id, project_id)` antes de
  procesar o listar resultados.
- El repositorio filtra por organización y proyecto.
- La base de datos aplica RLS para lectura y escritura autorizada.
- Las ejecuciones son trazas inmutables: no existen políticas de actualización
  ni eliminación.
- El archivo cargado se procesa en memoria. Esta versión conserva el hash y el
  resultado resumido, no el archivo original en Supabase.

## Despliegue

1. Aplicar `database/migrations/0010_native_darwincheck.sql` después de `0009`.
2. Desplegar `biocore_app.py` con las dependencias de `requirements.txt`.
3. Iniciar sesión con una organización que tenga DarwinCheck habilitado.
4. Validar el flujo: proyecto → DarwinCheck → carga → resultado → descarga →
   historial.
