# BioCore platform client

Cliente de servidor compartido por BioCore MycoField, DarwinCheck e Intelligence.

- Canjea códigos de lanzamiento de un solo uso.
- Conserva el token únicamente en la sesión del servidor del módulo.
- Revalida usuario, organización, permisos, módulos y proyectos con Auth/API.
- No contiene `service_role`, contraseñas ni reglas de suscripción.

Instalación desde el repositorio, fijando una versión o commit aprobado:

```text
biocore-platform-client @ git+https://github.com/consultorabiocore/Biocoreintelligence.git@VERSION#subdirectory=packages/biocore_client
```
