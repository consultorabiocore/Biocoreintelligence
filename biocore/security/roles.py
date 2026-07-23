from enum import StrEnum


class Role(StrEnum):
    SUPERADMIN = "superadmin"
    BIOCORE_ADMIN = "administradora_biocore"
    BIOCORE_SPECIALIST = "especialista_biocore"
    CLIENT_ADMIN = "cliente_administrador"
    CLIENT_READER = "cliente_lector"


class Permission(StrEnum):
    PLATFORM_ADMIN = "platform:admin"
    ORGANIZATIONS_READ = "organizations:read"
    PROJECTS_READ = "projects:read"
    PROJECTS_WRITE = "projects:write"
    CAMPAIGNS_READ = "campaigns:read"
    CAMPAIGNS_WRITE = "campaigns:write"
    MAPS_READ = "maps:read"
    FIELD_READ = "field:read"
    FIELD_WRITE = "field:write"
    DARWINCHECK_READ = "darwincheck:read"
    DARWINCHECK_WRITE = "darwincheck:write"
    INTELLIGENCE_READ = "intelligence:read"
    INTELLIGENCE_WRITE = "intelligence:write"
    REPORTS_READ = "reports:read"
    REPORTS_PUBLISH = "reports:publish"
    ACADEMY_READ = "academy:read"
    SUBSCRIPTIONS_READ = "subscriptions:read"


ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.SUPERADMIN: frozenset(Permission),
    Role.BIOCORE_ADMIN: frozenset(Permission),
    Role.BIOCORE_SPECIALIST: frozenset(
        {
            Permission.ORGANIZATIONS_READ,
            Permission.PROJECTS_READ,
            Permission.PROJECTS_WRITE,
            Permission.CAMPAIGNS_READ,
            Permission.CAMPAIGNS_WRITE,
            Permission.MAPS_READ,
            Permission.FIELD_READ,
            Permission.FIELD_WRITE,
            Permission.DARWINCHECK_READ,
            Permission.DARWINCHECK_WRITE,
            Permission.INTELLIGENCE_READ,
            Permission.INTELLIGENCE_WRITE,
            Permission.REPORTS_READ,
            Permission.REPORTS_PUBLISH,
            Permission.ACADEMY_READ,
            Permission.SUBSCRIPTIONS_READ,
        }
    ),
    Role.CLIENT_ADMIN: frozenset(
        {
            Permission.PROJECTS_READ,
            Permission.CAMPAIGNS_READ,
            Permission.MAPS_READ,
            Permission.FIELD_READ,
            Permission.DARWINCHECK_READ,
            Permission.INTELLIGENCE_READ,
            Permission.REPORTS_READ,
            Permission.ACADEMY_READ,
            Permission.SUBSCRIPTIONS_READ,
        }
    ),
    Role.CLIENT_READER: frozenset(
        {
            Permission.PROJECTS_READ,
            Permission.CAMPAIGNS_READ,
            Permission.MAPS_READ,
            Permission.FIELD_READ,
            Permission.DARWINCHECK_READ,
            Permission.INTELLIGENCE_READ,
            Permission.REPORTS_READ,
            Permission.ACADEMY_READ,
            Permission.SUBSCRIPTIONS_READ,
        }
    ),
}
