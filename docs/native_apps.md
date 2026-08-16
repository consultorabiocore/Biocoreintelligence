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
La primera conexión operativa usa Copernicus Data Space Ecosystem (CDSE), sin
activar una prueba de Google Cloud ni registrar una tarjeta. Los indicadores
actuales son:

- Sentinel-2 L2A para NDVI, EVI, NDMI y cobertura vegetal estimada;
- máscara de nubes y sombras basada en la clasificación SCL;
- estadísticas calculadas por CDSE sobre el polígono, sin descargar imágenes
  completas al servidor de Streamlit.

Temperatura superficial y humedad de suelo no se presentan todavía. Se
incorporarán únicamente cuando sus fuentes reales, unidades, resoluciones y
límites queden conectados y probados; no se sustituyen por valores sintéticos.

Cada ejecución conserva geometría, períodos, indicadores, fuentes,
resoluciones, número de imágenes, nubosidad, reglas, confianza, limitaciones y
recomendaciones. Los umbrales describen magnitud de cambio; no determinan una
causa, impacto o incumplimiento.

Aplicar `database/migrations/0012_native_intelligence.sql` después de `0011`.

### Activar Copernicus Data Space en Streamlit Community Cloud

La interfaz, el historial, los permisos y la persistencia de Intelligence son
parte nativa de BioCore. La ejecución de un monitoreo nuevo permanece
deshabilitada hasta completar esta conexión administrativa:

1. Crear una cuenta general gratuita en `https://dataspace.copernicus.eu/`.
2. Abrir el Sentinel Hub Dashboard en
   `https://shapps.dataspace.copernicus.eu/dashboard/` y crear un OAuth client.
   Copiar su Client ID y Client Secret. No publicarlos ni subirlos a GitHub.
3. En la aplicación desplegada, abrir **Manage app → Settings → Secrets** y
   agregar esta estructura:

   ```toml
   [copernicus]
   client_id = "PEGAR_CLIENT_ID"
   client_secret = "PEGAR_CLIENT_SECRET"
   ```

4. Guardar los secretos y reiniciar la aplicación. El formulario de **Nuevo
   monitoreo** quedará habilitado; los resultados seguirán ligados a la
   organización y al proyecto activo.

CDSE permite construir servicios comerciales sobre sus datos y ofrece cuotas
mensuales gratuitas para usuarios generales. BioCore controla errores de cuota
y nunca guarda un resultado parcial. Las cuotas son un límite operativo, no una
garantía de capacidad ni de nivel de servicio.

Un despliegue que ya cuente con una licencia comercial válida de Earth Engine
puede conservarla como proveedor alternativo bajo `gee.json`. BioCore no debe
registrarse como no comercial para desarrollar u ofrecer el producto.

Referencias operativas:

- https://documentation.dataspace.copernicus.eu/APIs/SentinelHub/Overview/Authentication.html
- https://documentation.dataspace.copernicus.eu/APIs/SentinelHub/Statistical.html
- https://documentation.dataspace.copernicus.eu/Quotas.html
- https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/secrets-management

## Validación mínima

1. Iniciar sesión y seleccionar una organización con los módulos habilitados.
2. Crear o abrir un proyecto.
3. Guardar una observación MycoField y verificar su fotografía privada.
4. Ejecutar DarwinCheck y descargar la planilla revisada.
5. Ejecutar Intelligence con un polígono y abrir el resultado histórico.
6. Confirmar con un segundo usuario que los datos de otra organización no son
   visibles y que un registro MycoField privado solo aparece a su creador.
