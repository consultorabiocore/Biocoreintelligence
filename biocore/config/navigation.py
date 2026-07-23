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
        "BioCore",
        ModuleCode.PLATFORM_CORE,
    ),
    PageDefinition(
        "Diagnóstico ecológico",
        "platform_pages/ecological_diagnostic.py",
        Permission.ECOLOGICAL_DIAGNOSTIC_READ,
        "BioCore",
        ModuleCode.ECOLOGICAL_DIAGNOSTIC,
    ),
    PageDefinition(
        "Proyectos",
        "platform_pages/projects.py",
        Permission.PROJECTS_READ,
        "Gestión",
        ModuleCode.PLATFORM_CORE,
    ),
    PageDefinition(
        "Campañas",
        "platform_pages/campaigns.py",
        Permission.CAMPAIGNS_READ,
        "Gestión",
        ModuleCode.PLATFORM_CORE,
    ),
    PageDefinition(
        "Mapas",
        "platform_pages/maps.py",
        Permission.MAPS_READ,
        "Gestión",
        ModuleCode.PLATFORM_CORE,
    ),
    PageDefinition(
        "Informes",
        "platform_pages/reports.py",
        Permission.REPORTS_READ,
        "Resultados",
        ModuleCode.REPORTS,
    ),
    PageDefinition(
        "BioCore Field",
        "platform_pages/field.py",
        Permission.FIELD_READ,
        "Ecosistema",
        ModuleCode.FIELD,
    ),
    PageDefinition(
        "DarwinCheck",
        "platform_pages/darwincheck.py",
        Permission.DARWINCHECK_READ,
        "Ecosistema",
        ModuleCode.DARWINCHECK,
    ),
    PageDefinition(
        "BioCore Intelligence",
        "platform_pages/intelligence.py",
        Permission.INTELLIGENCE_READ,
        "Ecosistema",
        ModuleCode.INTELLIGENCE,
    ),
    PageDefinition(
        "BioCore Academy",
        "platform_pages/academy.py",
        Permission.ACADEMY_READ,
        "Ecosistema",
        ModuleCode.ACADEMY,
    ),
    PageDefinition(
        "Suscripción",
        "platform_pages/subscription.py",
        Permission.SUBSCRIPTIONS_READ,
        "Cuenta",
        ModuleCode.PLATFORM_CORE,
    ),
    PageDefinition(
        "Módulos",
        "platform_pages/modules.py",
        Permission.SUBSCRIPTIONS_READ,
        "Cuenta",
        ModuleCode.PLATFORM_CORE,
    ),
    PageDefinition(
        "Administración",
        "platform_pages/admin.py",
        Permission.PLATFORM_ADMIN,
        "Sistema",
        ModuleCode.PLATFORM_CORE,
    ),
    PageDefinition(
        "Bandeja de diagnósticos",
        "platform_pages/diagnostic_inbox.py",
        Permission.PLATFORM_ADMIN,
        "Sistema",
        ModuleCode.ECOLOGICAL_DIAGNOSTIC,
    ),
)


ACCOUNT_PATHS = frozenset(
    {
        "platform_pages/subscription.py",
        "platform_pages/modules.py",
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
