# Aplicaciones nativas BioCore

MycoField, DarwinCheck e Intelligence se ejecutan dentro de la plataforma
privada. Comparten sesión, organización activa, proyectos, permisos y
suscripciones. Ninguna página nativa solicita una segunda cuenta ni redirige a
otra aplicación Streamlit.

## BioCore MycoField

El flujo vincula cada observación a un proyecto y conserva:

- código de muestra único por proyecto;
- fecha y coordenadas WGS84 validadas;
- privacidad privada, aproximada o visible para la organización;
- nombre tentativo, sustrato, hábitat, método, esfuerzo y rasgos observados;
- hasta seis fotografías en el bucket privado `mycofield-evidence`;
- mapa de puntos compartidos, bitácora y descarga Excel.

Los nombres tentativos se presentan como hipótesis de terreno. MycoField no
confirma una identificación taxonómica.

Aplicar `database/migrations/0011_native_mycofield.sql` después de `0010`.

## DarwinCheck

DarwinCheck revisa la hoja `Ocurrencia`, aplica coincidencias exactas y únicas
contra la referencia versionada, normaliza tiempos y coordenadas, calcula
índices ecológicos, registra hallazgos y produce un libro con trazabilidad. Los
casos ambiguos permanecen sin corrección y se marcan para revisión.

La versión independiente dejó de formar parte del flujo privado.

## BioCore Intelligence

El monitoreo nativo recibe un polígono GeoJSON, valida coordenadas WGS84 y
compara una ventana reciente de 90 días con la misma ventana de un año base.
Las fuentes actuales son:

- Sentinel-2 SR para NDVI, EVI, NDMI y cobertura estimada;
- MODIS MOD11A2 para temperatura superficial diurna;
- ERA5-Land para humedad volumétrica superficial.

Cada ejecución conserva geometría, períodos, indicadores, fuentes,
resoluciones, número de imágenes, nubosidad, reglas, confianza, limitaciones y
recomendaciones. Los umbrales describen magnitud de cambio; no determinan una
causa, impacto o incumplimiento.

Aplicar `database/migrations/0012_native_intelligence.sql` después de `0011` y
mantener la credencial de Google Earth Engine solamente en los secretos del
despliegue bajo `gee.json`.

## Validación mínima

1. Iniciar sesión y seleccionar una organización con los módulos habilitados.
2. Crear o abrir un proyecto.
3. Guardar una observación MycoField y verificar su fotografía privada.
4. Ejecutar DarwinCheck y descargar la planilla revisada.
5. Ejecutar Intelligence con un polígono y abrir el resultado histórico.
6. Confirmar con un segundo usuario que los datos de otra organización no son
   visibles y que un registro MycoField privado solo aparece a su creador.
