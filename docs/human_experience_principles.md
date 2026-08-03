# Principios de dignidad, explicabilidad y calidad accesible

Este documento forma parte de los criterios arquitectónicos de BioCore. Una
funcionalidad no se considera terminada solamente porque ejecute su caso de
uso: también debe ser comprensible, segura, accesible, explicable y útil para
la siguiente decisión de la persona usuaria.

## Cuatro principios inseparables

1. **Rigor científico.** Los datos, métodos, alcances y limitaciones deben
   describirse sin exagerar capacidades ni presentar inferencias como hechos.
2. **Excelencia tecnológica.** La implementación debe ser segura, mantenible,
   trazable, probada y aislada por organización cuando corresponda.
3. **Experiencia humana.** El sistema reduce complejidad, carga cognitiva e
   incertidumbre antes de mostrar información.
4. **Explicabilidad.** Una persona debe poder comprender el origen, las reglas,
   el resultado, su confianza, sus límites y la siguiente acción recomendada.

## Principio de dignidad

BioCore entrega la misma calidad de experiencia sin depender del nivel
educativo, experiencia profesional, alfabetización digital, condición
económica o experiencia previa con plataformas ambientales.

La interfaz no aprovecha el desconocimiento, no oculta consecuencias y no usa
lenguaje técnico cuando una formulación más clara conserva el rigor. Los
errores esperables se previenen, advierten o explican antes de convertirse en
frustración.

## Principio de orientación al problema

La navegación principal se organiza alrededor de tareas y objetivos de las
personas, no de la arquitectura interna del software. Antes de preguntar qué
módulo desea abrir alguien, BioCore debe ayudarle a responder qué quiere
lograr.

En proyectos ecológicos, el recorrido principal es:

1. Proyecto.
2. Área de estudio.
3. Campaña de terreno.
4. Captura.
5. Validación.
6. Análisis.
7. Informe.

Los módulos especializados aparecen como herramientas disponibles dentro de
ese recorrido. Un dashboard es una vista de un proyecto o de una organización,
no un objetivo autónomo del usuario.

## Contrato de explicabilidad

Toda clasificación, alerta, recomendación, inferencia o puntaje debe permitir
responder:

- qué datos se utilizaron;
- qué relaciones se detectaron;
- qué reglas se aplicaron;
- por qué se obtuvo el resultado;
- qué nivel de confianza existe;
- cuáles son sus limitaciones;
- qué debería hacer ahora la persona usuaria.

La presentación distingue explícitamente:

- **dato observado**: registro obtenido de una fuente identificada;
- **dato calculado**: valor derivado mediante una regla reproducible;
- **comparación**: relación entre periodos, sitios o conjuntos de datos;
- **inferencia**: interpretación sujeta a supuestos e incertidumbre;
- **recomendación**: acción sugerida, no obligación ni hecho confirmado;
- **incertidumbre**: límite conocido del dato o del método;
- **dato faltante**: información ausente que afecta el resultado.

Las reglas de puntuación o clasificación deben permanecer fuera de Streamlit,
ser deterministas, versionadas y probadas. La interfaz solo explica y presenta
el resultado del servicio correspondiente.

## Contrato mínimo de cada pantalla

Cada pantalla debe permitir identificar rápidamente:

1. dónde se encuentra la persona;
2. qué acaba de ocurrir;
3. qué puede hacer ahora;
4. cuál es la siguiente acción recomendada.

Toda acción importante ofrece retroalimentación visible. Cada flujo contempla
carga, contenido, estado vacío real, error recuperable, permiso insuficiente,
sesión vencida y operación exitosa. Los errores técnicos se registran para
depuración, pero se traducen a mensajes comprensibles sin exponer secretos ni
detalles internos.

## Lista de aceptación obligatoria

Antes de cerrar una tarea, el equipo debe poder responder afirmativamente:

- ¿Es técnicamente correcta y segura?
- ¿Es científicamente correcta y declara su alcance?
- ¿Es mantenible y trazable?
- ¿Es comprensible para una persona con poca experiencia digital?
- ¿Respeta el tiempo de la persona usuaria?
- ¿Explica suficientemente el resultado y sus limitaciones?
- ¿Previene o reduce errores?
- ¿Reduce incertidumbre y carga cognitiva?
- ¿Mantiene consistencia con el resto de BioCore?
- ¿Permite continuar sin frustración?
- ¿Ayuda a comprender, decidir y actuar con mayor confianza?

Si alguna respuesta es negativa, la tarea continúa abierta.

## Regla de oro

BioCore no mide la calidad por la complejidad del software, sino por su
capacidad de ayudar a las personas a comprender, decidir y actuar con
confianza.
