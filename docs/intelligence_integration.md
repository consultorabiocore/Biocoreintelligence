# Integración nativa de BioCore Intelligence

## Fuente funcional correcta

La referencia vigente es
[`consultorabiocore/Biocoreintelligenceaparte`](https://github.com/consultorabiocore/Biocoreintelligenceaparte),
revisada inicialmente en el commit
`153fe467a204d77207c8b1fa3ed0883374ae9525`.

El `app.py` histórico de este repositorio no es la fuente de nuevas funciones.
Se mantiene temporalmente solo para evitar romper despliegues antiguos mientras
se verifica la migración. No aparece como segundo módulo dentro de la plataforma.

## Regla de integración

La aplicación actualizada no se incrusta mediante `iframe`, no redirige a otro
Streamlit y no conserva su autenticación o tabla de usuarios independiente.
Cada capacidad se traslada a la arquitectura nativa:

- sesión y autorización central de BioCore;
- `organization_id` y `project_id` obligatorios;
- servicios y repositorios separados de Streamlit;
- historial inmutable con RLS;
- secretos únicamente en el servidor;
- errores técnicos registrados y mensajes comprensibles para el usuario.

## Estado de migración

| Capacidad de la app actualizada | Estado nativo | Implementación |
| --- | --- | --- |
| Selección del proyecto | Integrada | Proyectos de la organización activa |
| Área de análisis | Integrada | Reutilizar, dibujar en mapa o cargar GeoJSON |
| Sentinel-2 óptico | Integrada | Copernicus Data Space, sin datos simulados |
| NDVI, EVI, SAVI, NDWI, NDMI, NDSI, SWIR y cobertura | Integrada | Cálculo determinista y versionado |
| Hallazgos explicables | Integrada | Dato, comparación, regla, confianza y limitación |
| Historial por proyecto | Integrada | `intelligence_monitoring_runs` con RLS |
| Informes ejecutivo y técnico | Integrada | PDF versionado desde una ejecución inmutable |
| Exportación tabular | Integrada | XLSX con indicadores, hallazgos y trazabilidad |
| Series temporales largas | Pendiente | Requiere ampliar el proveedor y el modelo de series |
| Sentinel-1, MODIS y ERA5-Land | Pendiente | No se muestran como disponibles hasta tener fuente real |
| Terreno 3D/DEM | Pendiente | Se migrará sin depender del Earth Engine personal |
| InSAR y radar geotécnico | Pendiente | Requieren resultados y QA trazables, no simulación comercial |
| Telegram automático | Pendiente | Se conectará a la identidad y preferencias centrales |

## Retiro del legado

El `app.py` antiguo se eliminará únicamente después de comprobar equivalencia de
las funciones necesarias y confirmar que ningún despliegue activo lo utiliza.
Hasta entonces permanece fuera de la navegación y no constituye una segunda
experiencia para clientes.
