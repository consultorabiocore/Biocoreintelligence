# Auditoría funcional de la plataforma

Estado observado antes del módulo Evidencias ecológicas.

| Componente | Estado | Próximo trabajo verificable |
|---|---|---|
| Sesión, organización y permisos | Operativo | Pruebas end-to-end de expiración y cambio de organización |
| Proyectos | MVP persistente | Vincular documentos, áreas, campañas e hitos reales |
| Evidencias ecológicas | MVP implementado en `0013` | Validar en Supabase y con una observación controlada |
| Áreas de estudio | Página informativa | Dominio, repositorio de geometrías, RLS y CRUD |
| Campañas | Página informativa | Planificación, equipo, fechas y vínculo con evidencias |
| Mapas | Página informativa | Capas autorizadas y privacidad espacial |
| Informes | Página informativa | Repositorio documental, versiones y generación |
| BioCore Reports | Página informativa | Plantillas, versiones y descarga trazable |
| Usuarios | Página informativa | Invitaciones, roles y revocación autoservicio |
| Administración | Página informativa | Organizaciones, membresías y suscripciones auditables |
| Configuración | Página informativa | Preferencias por organización |
| BioCore Academy | Placeholder | Catálogo, progreso y permisos |
| Frontend 3D | Código desacoplado | Integración segura, atribución del autor y propósito ecológico claro |
| Consulta de servicios | Enlace de contacto | Bandeja interna y estados de seguimiento |

No se consideran terminados los componentes que todavía muestran únicamente
mensajes informativos. El orden recomendado después de Evidencias es: Áreas de
estudio → Campañas → Mapas → Informes, porque corresponde al flujo real del
proyecto y evita construir pantallas aisladas.
