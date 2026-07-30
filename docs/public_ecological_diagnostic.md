# Diagnóstico ecológico público

El diagnóstico público funciona antes del inicio de sesión y no depende de una
organización, membresía ni suscripción. Su objetivo es entregar una orientación
preliminar inmediata y registrar un prospecto comercial con consentimiento.

## Ruta pública

La plataforma muestra el formulario cuando la URL contiene:

```text
?diagnostico=publico
```

La portada conserva el acceso privado y añade un botón flotante:

```text
Diagnóstico ecológico gratuito · sin cuenta
```

## Flujo

1. El visitante completa sus datos de contacto, proyecto y cuestionario.
2. El motor de reglas existente genera el resultado preliminar.
3. El resultado y el informe descargable se muestran aunque el almacenamiento
   comercial falle temporalmente.
4. Con consentimiento, el servidor registra el prospecto en
   `public_ecological_diagnostic_leads`.
5. La persona puede solicitar cotización o reunión.
6. Si contrata, BioCore crea su organización y utiliza el módulo privado para
   diagnósticos versionados, revisión profesional e historial.

## Despliegue

Ejecutar después de las migraciones anteriores:

```text
database/migrations/0004_public_ecological_diagnostic_leads.sql
```

El despliegue necesita `SUPABASE_URL` y `SUPABASE_SERVICE_ROLE_KEY`. La clave de
servicio permanece en el servidor. La tabla no concede permisos directos a los
roles `anon` ni `authenticated`.

## Privacidad

El formulario exige autorización explícita para guardar los antecedentes y
contactar al prospecto. El diagnóstico sigue mostrando el descargo de alcance:
no sustituye una campaña de terreno, línea de base ni revisión profesional.
