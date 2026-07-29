# Gestión de proyectos

## Alcance

El módulo `Proyectos` usa la sesión privada de `biocore_app.py` y el contexto
de organización resuelto en el servidor. Permite crear, buscar, filtrar, abrir,
editar, cambiar de estado y archivar proyectos sin eliminarlos.

Los proyectos no incluyen datos demostrativos. Cada registro contiene:

- nombre y código interno único por organización;
- cliente o entidad, tipo de proyecto, región y comuna;
- modalidad online, terreno o mixta;
- descripción, objetivo y fecha de inicio opcional;
- estado, creador, última persona que modificó y fechas;
- historial básico de creación, edición, cambio de estado y archivo.

## Capas

```text
biocore/domain/projects.py        modelos y estados
biocore/repositories/projects.py  consultas Supabase con organization_id
biocore/services/projects.py      permisos, validaciones e historial
platform_pages/projects.py        interfaz Streamlit
database/migrations/0007_*        esquema, índices y RLS
database/rollbacks/0007_*         reversión no destructiva del incremento
```

La tabla `projects` mantiene la clave compuesta `(id, organization_id)`. Las
áreas de estudio, campañas, mapas, archivos, revisiones e informes podrán
referenciarla posteriormente sin que esos módulos se implementen en esta fase.

## Seguridad

- Toda operación del repositorio incluye `organization_id`.
- Lectores solo pueden consultar.
- Editores, administradores, especialistas y superadministración pueden crear
  o modificar según los permisos de la aplicación.
- RLS repite el aislamiento y restringe escrituras por rol.
- No existe política `DELETE`; el archivo es lógico mediante estado y fecha.
- El servicio valida nuevamente permisos y organización aunque la página no
  muestre controles de edición.

La aplicación usa una clave de servicio exclusivamente en el servidor. Esa
clave nunca debe exponerse a las páginas ni al navegador.

## Despliegue

1. Respaldar Supabase.
2. Aplicar las migraciones `0001` a `0006` en orden si aún no están instaladas.
3. Ejecutar `database/migrations/0007_project_management.sql`.
4. Desplegar `biocore_app.py`.
5. Mantener disponible
   `database/rollbacks/0007_project_management_down.sql` para revertir solo las
   columnas, políticas e historial de esta entrega. El rollback conserva la
   tabla base y los proyectos.

## Prueba manual

1. Ingresar con una membresía `cliente_administrador` o `cliente_editor`.
2. Abrir **Gestión ambiental → Proyectos**.
3. Crear un proyecto con todos los campos obligatorios.
4. Buscarlo por código, cliente, región o comuna.
5. Abrir su ficha, editar un campo y cambiar su estado.
6. Confirmar que el historial contiene cada operación.
7. Archivarlo y comprobar que desaparece del listado normal.
8. Activar **Ver archivados** y comprobar que reaparece sin pérdida de datos.
9. Ingresar como `cliente_lector` y confirmar que no se muestran formularios de
   escritura.
10. Ingresar desde otra organización y confirmar que el proyecto no aparece ni
    puede abrirse por identificador.

El diagnóstico ecológico público permanece separado y no depende del módulo
Proyectos.
