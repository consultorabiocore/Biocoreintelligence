# Plataforma BioCore

## Entradas de la aplicación

- `biocore_app.py`: portada pública, autenticación OIDC y plataforma privada.
- `app.py`: aplicación histórica. Se conserva para una migración gradual y no
  debe convertirse en la entrada de la nueva plataforma.

La portada pública no consulta datos operativos ni usa credenciales de
Supabase. Después de iniciar sesión, la aplicación resuelve en el servidor la
identidad, la organización, los roles y la suscripción.

## Capas

```text
biocore/components      presentación reutilizable
biocore/config          marca, navegación y configuración
biocore/domain          modelos sin dependencia de Streamlit
biocore/repositories    consultas a fuentes de datos
biocore/security        identidad, roles y autorización base
biocore/services        casos de uso y acceso a módulos
platform_pages          composición de páginas Streamlit
database/migrations     esquema y políticas RLS
```

Las páginas no deben consultar directamente la base de datos ni aceptar
organizaciones, roles o permisos provenientes de controles de interfaz.

## Autenticación y autorización

La migración hacia sesión única, Auth/API y códigos de lanzamiento se describe
en [`central_authentication.md`](central_authentication.md). Durante la Fase A,
el modo `shadow` registra y valida la sesión central sin retirar el acceso OIDC
actual.

1. Google autentica al usuario mediante OIDC.
2. `AuthenticatedIdentity` conserva `sub`, correo y nombre visible.
3. `SupabaseMembershipResolver` busca `sub` con una clave de servicio que solo
   existe en el servidor.
4. `UserContext` determina la organización y los permisos por rol.
5. `SubscriptionService` resuelve el plan, su estado, complementos, consumo y
   accesos temporales incluidos por proyecto.
6. `user_can_access_module(...)` verifica usuario, organización y módulo antes
   de ejecutar una capacidad protegida.

Ocultar una página del menú no reemplaza la autorización del servicio. Las
tablas nuevas tienen RLS de lectura por organización y no conceden escrituras
al cliente.

## Suscripciones

La migración `0002_subscriptions_and_entitlements.sql` incorpora:

- planes `core`, `professional` y `enterprise`;
- estados de prueba, activo, pago pendiente, suspendido, cancelado y expirado;
- límites de usuarios, proyectos y almacenamiento;
- activación o desactivación explícita de módulos;
- medición de consumo;
- accesos temporales incluidos por proyecto.

Los accesos por proyecto pueden habilitar módulos durante un periodo sin crear
una segunda cuenta. Al finalizar, la organización puede convertir la
continuidad en una suscripción principal.

## Orden de despliegue

1. Ejecutar `database/migrations/0001_identity_and_tenancy.sql`.
2. Ejecutar `database/migrations/0002_subscriptions_and_entitlements.sql`.
3. Ejecutar `database/migrations/0003_ecological_diagnostics.sql`.
4. Ejecutar la migración pública `0004_public_ecological_diagnostic_leads.sql`.
5. Ejecutar las migraciones de autenticación central `0005` a `0007`.
6. Ejecutar `database/migrations/0008_project_management.sql`.
7. Registrar la suscripción de cada organización desde un contexto
   administrativo. Para staging puede utilizarse
   `database/seeds/001_biocore_staging_subscription.sql`.
8. Configurar `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY` y la autenticación
   OIDC únicamente en los secretos del despliegue.
9. Desplegar `biocore_app.py`.

La clave `service_role` nunca debe enviarse al navegador, guardarse en Git ni
mostrarse en mensajes de error.

## Activos de marca

Los archivos oficiales están en `assets/brand/`:

- `biocore-logo-horizontal.png`
- `biocore-field.png`
- `biocore-reports.png`
- `biocore-academy.png`

Cuando exista un isotipo oficial independiente, debe guardarse como
`assets/brand/biocore-isotipo.png` y configurarse como `compact_logo` en
`biocore/config/brand.py`.

## Verificación

```powershell
python -m compileall -q biocore biocore_app.py platform_pages tests
python -m pytest -q
```

El workflow `Platform tests` ejecuta estas verificaciones en cada pull request
que modifica la plataforma, las migraciones o los activos de marca.

## Gestión de proyectos

El flujo de sesión, el esquema, los permisos, la reversión y la prueba manual
del módulo se describen en
[`project_management.md`](project_management.md).

## Diagnóstico ecológico

El diseño, alcance, versionado y decisiones del prototipo se describen en
[`ecological_diagnostic.md`](ecological_diagnostic.md).
