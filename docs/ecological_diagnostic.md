# Diagnóstico Ecológico Digital BioCore

## Alcance del prototipo

El prototipo breve evalúa únicamente la disponibilidad y preparación de
información sobre:

- flora vascular;
- vegetación y cobertura vegetal;
- hongos;
- líquenes;
- campañas ecológicas de terreno;
- fotografías, cartografía y datos georreferenciados;
- calidad, trazabilidad y comparación de campañas;
- informes ecológicos.

No califica el estado del ambiente ni produce conclusiones técnicas
definitivas. El descargo se muestra antes del cuestionario, antes de los
resultados y dentro del informe descargable.

## Cuestionario y reglas

La configuración está en `biocore/config/ecological_diagnostic.py`:

- cuestionario `brief-1.0`, con 15 preguntas;
- reglas `ecological-rules-1.0`;
- opciones y campos admitidos;
- pesos por dimensión;
- textos explicativos y módulos recomendados.

`EcologicalDiagnosticService` calcula de forma determinista:

1. completitud documental;
2. cobertura espacial;
3. cobertura temporal;
4. cobertura taxonómica;
5. calidad de registros;
6. trazabilidad;
7. preparación geoespacial;
8. preparación para comparar campañas.

Cada versión conserva las respuestas, el resultado estructurado, la versión
del cuestionario y la versión de reglas. Volver a evaluar crea una versión
nueva; no sobrescribe silenciosamente el resultado anterior.

## Persistencia y aislamiento

La migración `0003_ecological_diagnostics.sql` crea:

- `ecological_diagnostics`;
- `ecological_diagnostic_responses`;
- `ecological_diagnostic_assessments`;
- `ecological_diagnostic_review_requests`.

Todas las consultas del repositorio filtran por `organization_id`. Las tablas
usan RLS y no conceden escritura a clientes. La aplicación escribe mediante el
servicio confiable después de verificar rol, organización y módulo contratado.

## Suscripciones

- `ecological_diagnostic`: diagnóstico breve incluido desde BioCore Core.
- `ecological_diagnostic_detailed`: complemento futuro, deshabilitado por
  defecto y sin pagos en esta fase.

El producto detallado, carga persistente de archivos, cotizaciones y conversión
real a proyecto quedan fuera de este prototipo. La política de extensiones y
tamaño de archivo está preparada y probada para la siguiente fase.

## Informe

El informe HTML descargable incluye marca BioCore, identificación, fecha,
versiones, descargo, resultados por dimensión, brechas, recomendaciones y
próximos pasos. Siempre muestra:

> Resultado preliminar no revisado profesionalmente

Una futura revisión especialista debe crear otra versión identificada y nunca
reemplazar la automática.
