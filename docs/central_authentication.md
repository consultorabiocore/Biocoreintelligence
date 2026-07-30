# Autenticación central BioCore

## Alcance de esta fase

Esta entrega crea la base de identidad, sesiones, permisos, proyectos,
invitaciones y planes configurables. Es deliberadamente aditiva:

- no elimina los accesos heredados;
- no copia contraseñas ni hashes;
- no conecta pagos;
- no entrega `service_role` a Field, DarwinCheck o Intelligence;
- mantiene la plataforma actual en modo `shadow`.

## Componentes

```text
biocore/auth                 casos de uso de identidad y sesión
biocore/api                  servicio FastAPI central
biocore/repositories         acceso confiable a Supabase
biocore/security             tenant scope, auditoría y rate limiting
biocore/subscriptions        planes, habilitaciones, uso y billing boundary
packages/biocore_client      cliente compartido para módulos Streamlit
database/migrations/0005-*   identidad, sesiones, permisos y proyectos
database/migrations/0006-*   planes y complementos configurables
database/migrations/0007-*   vinculación de cuentas heredadas
database/migrations/0008-*   gestión de proyectos
```

## Flujo SSO entre dominios Streamlit

Las cookies de aplicaciones `*.streamlit.app` distintas no se pueden compartir
de manera segura. BioCore usa una sesión central más un código de lanzamiento:

1. Auth/API verifica un JWT firmado del proveedor OIDC.
2. Crea una sesión opaca y guarda únicamente su hash.
3. La plataforma solicita un código de lanzamiento de dos minutos.
4. El navegador llega al módulo con el código, nunca con el token de sesión.
5. El servidor del módulo canjea el código una sola vez.
6. Auth/API entrega una sesión hija limitada al módulo.
7. El módulo revalida permisos, organización y proyecto contra Auth/API.

## Despliegue

1. Respaldar la base de datos.
2. Ejecutar, en orden:
   - `0005_central_identity_sessions_and_permissions.sql`
   - `0006_configurable_subscriptions.sql`
   - `0007_legacy_identity_mapping.sql`
   - `0008_project_management.sql`
3. Mantener `BIOCORE_AUTH_MODE=shadow`.
4. Configurar Supabase Auth/OIDC y las variables descritas en
   `.streamlit/secrets.example.toml`.
5. Desplegar Auth/API con:

   ```text
   uvicorn biocore.api.main:app --host 0.0.0.0 --port 8000
   ```

6. Confirmar `/health` con `central_auth_configured=true`.
7. Integrar Field y DarwinCheck con `packages/biocore_client`.
8. Cambiar a `optional` para usuarios piloto.
9. Cambiar a `required` únicamente cuando las pruebas integrales pasen.

## Proveedor de identidad

BioCore no implementa hashing de contraseñas. Supabase Auth/OIDC debe gestionar:

- creación de cuenta;
- correo verificado;
- Google;
- recuperación y cambio de contraseña;
- protección contra fuerza bruta;
- MFA cuando se habilite.

`Auth/API` valida firma, emisor, audiencia, expiración, `sub`, correo y
`email_verified`.

## Seguridad

- Los tokens de sesión, invitación y lanzamiento son aleatorios y en la base
  solo se conserva SHA-256 del valor aleatorio.
- SHA-256 no se usa para contraseñas.
- Los códigos de lanzamiento y las invitaciones se consumen atómicamente.
- Cada consulta operativa debe filtrar `organization_id` y, cuando corresponda,
  `project_id`.
- Las URL de retorno deben usar HTTPS y estar en la lista permitida.
- Una suspensión de membresía o suscripción se refleja al revalidar el contexto.
- La cancelación no elimina datos.

## Reversión

El modo puede volver de `optional` a `shadow` sin revertir datos. Las migraciones
no eliminan tablas ni columnas existentes. Los logins heredados solo se
retirarán después de que las sesiones, los códigos, el aislamiento y la
recuperación hayan sido probados en producción controlada.
