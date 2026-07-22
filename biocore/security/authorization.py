from dataclasses import dataclass
from typing import Mapping, TypeVar

from .roles import Permission, ROLE_PERMISSIONS, Role


class AuthorizationError(PermissionError):
    """Raised when an authenticated user lacks access to an operation."""


@dataclass(frozen=True)
class UserContext:
    user_id: str
    organization_id: str
    roles: frozenset[Role]

    def has_permission(self, permission: Permission) -> bool:
        return any(permission in ROLE_PERMISSIONS[role] for role in self.roles)


def require_permission(context: UserContext, permission: Permission) -> None:
    if not context.has_permission(permission):
        raise AuthorizationError(f"Missing permission: {permission}")


def require_organization(context: UserContext, organization_id: str) -> None:
    if Role.SUPERADMIN not in context.roles and context.organization_id != organization_id:
        raise AuthorizationError("Cross-organization access denied")


Row = TypeVar("Row", bound=Mapping[str, object])


def scope_to_organization(context: UserContext, rows: list[Row]) -> list[Row]:
    """Defense-in-depth helper; database repositories must also filter server-side."""
    if Role.SUPERADMIN in context.roles:
        return rows
    return [row for row in rows if row.get("organization_id") == context.organization_id]
