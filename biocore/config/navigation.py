from dataclasses import dataclass

from biocore.security.authorization import UserContext
from biocore.security.roles import Permission


@dataclass(frozen=True)
class PageDefinition:
    title: str
    path: str
    permission: Permission
    section: str


PAGES = (
    PageDefinition("Inicio", "platform_pages/home.py", Permission.PROJECTS_READ, "BioCore"),
    PageDefinition("Proyectos", "platform_pages/projects.py", Permission.PROJECTS_READ, "Gestión"),
    PageDefinition("Campañas", "platform_pages/campaigns.py", Permission.CAMPAIGNS_READ, "Gestión"),
    PageDefinition("Inteligencia", "platform_pages/intelligence.py", Permission.INTELLIGENCE_READ, "Análisis"),
    PageDefinition("Administración", "platform_pages/admin.py", Permission.PLATFORM_ADMIN, "Sistema"),
)


def pages_for(context: UserContext) -> dict[str, list[PageDefinition]]:
    result: dict[str, list[PageDefinition]] = {}
    for page in PAGES:
        if context.has_permission(page.permission):
            result.setdefault(page.section, []).append(page)
    return result
