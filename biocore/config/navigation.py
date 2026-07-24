from dataclasses import dataclass

from biocore.domain.subscriptions import ModuleCode, SubscriptionSnapshot
from biocore.security.authorization import UserContext
from biocore.security.roles import Permission, Role


@dataclass(frozen=True)
class PageDefinition:
    title: str
    path: str
    permission: Permission
    section: str
    module_code: ModuleCode


PAGES = (
    PageDefinition(
        "Inicio",
        "platform_pages/home.py",
        Permission.PROJECTS_READ,
        "GENERAL",
        ModuleCode.PLATFORM_CORE,
    ),
    PageDefinition(
        "Diagnóstico ecológico",
        "platform_pages/ecological_diagnostic.py",
        Permission.ECOLOGICAL_DIAGNOSTIC_READ,
        "GENERAL",
        ModuleCode.ECOLOGICAL_DIAGNOSTIC,
    ),
    PageDefinition(
        "Proyectos",
        "platform_pages/projects.py",
        Permission.PROJECTS_READ,
        "GESTIÓN AMBIENTAL",
        ModuleCode.PLATFORM_CORE,
    ),
    PageDefinition(
        "Áreas de estudio",
        "platform_pages/areas.py",
        Permission.PROJECTS_READ,
        "GESTIÓN AMBIENTAL",
        ModuleCode.PLATFORM_CORE,
    ),
    PageDefinition(
        "Campañas",
        "platform_pages/campaigns.py",
        Permission.CAMPAIGNS_READ,
        "GESTIÓN AMBIENTAL",
        ModuleCode.PLATFORM_CORE,
    ),
    PageDefinition(
        "Mapas",
        "platform_pages/maps.py",
        Permission.MAPS_READ,
        "GESTIÓN AMBIENTAL",
        ModuleCode.PLATFORM_CORE,
    ),
    PageDefinition(
        "Informes",
        "platform_pages/reports.py",
        Permission.REPORTS_READ,
        "GESTIÓN AMBIENTAL",
        ModuleCode.PLATFORM_CORE,
    ),
    PageDefinition(
        "BioCore Field",
        "platform_pages/field.py",
        Permission.FIELD_READ,
        "MÓDULOS",
        ModuleCode.FIELD,
    ),
    PageDefinition(
        "DarwinCheck",
        "platform_pages/darwincheck.py",
        Permission.DARWINCHECK_READ,
        "MÓDULOS",
        ModuleCode.DARWINCHECK,
    ),
    PageDefinition(
        "BioCore Intelligence",
        "platform_pages/intelligence.py",
        Permission.INTELLIGENCE_READ,
        "MÓDULOS",
        ModuleCode.INTELLIGENCE,
    ),
    PageDefinition(
        "BioCore Reports",
        "platform_pages/biocore_reports.py",
        Permission.REPORTS_READ,
        "MÓDULOS",
        ModuleCode.REPORTS,
    ),
    PageDefinition(
        "BioCore Academy",
        "platform_pages/academy.py",
        Permission.ACADEMY_READ,
        "MÓDULOS",
        ModuleCode.ACADEMY,
    ),
    PageDefinition(
        "Suscripción",
        "platform_pages/subscription.py",
        Permission.SUBSCRIPTIONS_READ,
        "CUENTA",
        ModuleCode.PLATFORM_CORE,
    ),
    PageDefinition(
        "Usuarios",
        "platform_pages/users.py",
        Permission.SUBSCRIPTIONS_READ,
        "CUENTA",
        ModuleCode.PLATFORM_CORE,
    ),
    PageDefinition(
        "Configuración",
        "platform_pages/settings.py",
        Permission.SUBSCRIPTIONS_READ,
        "CUENTA",
        ModuleCode.PLATFORM_CORE,
    ),
    PageDefinition(
        "Administración",
        "platform_pages/admin.py",
        Permission.PLATFORM_ADMIN,
        "ADMINISTRACIÓN BIOCORE",
        ModuleCode.PLATFORM_CORE,
    ),
    PageDefinition(
        "Bandeja de diagnósticos",
        "platform_pages/diagnostic_inbox.py",
        Permission.PLATFORM_ADMIN,
        "ADMINISTRACIÓN BIOCORE",
        ModuleCode.ECOLOGICAL_DIAGNOSTIC,
    ),
)


ACCOUNT_PATHS = frozenset(
    {
        "platform_pages/subscription.py",
        "platform_pages/users.py",
        "platform_pages/settings.py",
        "platform_pages/admin.py",
        "platform_pages/diagnostic_inbox.py",
    }
)


def pages_for(
    context: UserContext,
    subscription: SubscriptionSnapshot | None = None,
) -> dict[str, list[PageDefinition]]:
    result: dict[str, list[PageDefinition]] = {}
    for page in PAGES:
        if not context.has_permission(page.permission):
            continue
        if (
            subscription is not None
            and Role.SUPERADMIN not in context.roles
            and page.path not in ACCOUNT_PATHS
            and not subscription.allows(page.module_code)
        ):
            continue
        result.setdefault(page.section, []).append(page)
    return result
