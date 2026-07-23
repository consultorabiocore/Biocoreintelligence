import pytest

from biocore.security.authorization import (
    AuthorizationError,
    UserContext,
    require_organization,
    require_permission,
    scope_to_organization,
)
from biocore.security.roles import Permission, Role


def context(role: Role, organization_id: str = "org-a") -> UserContext:
    return UserContext("user-1", organization_id, frozenset({role}))


def test_client_reader_cannot_write_projects() -> None:
    with pytest.raises(AuthorizationError):
        require_permission(context(Role.CLIENT_READER), Permission.PROJECTS_WRITE)


def test_specialist_can_write_intelligence() -> None:
    require_permission(context(Role.BIOCORE_SPECIALIST), Permission.INTELLIGENCE_WRITE)


def test_client_cannot_access_another_organization() -> None:
    with pytest.raises(AuthorizationError):
        require_organization(context(Role.CLIENT_ADMIN), "org-b")


def test_repository_results_are_scoped_to_organization() -> None:
    rows = [
        {"id": "a", "organization_id": "org-a"},
        {"id": "b", "organization_id": "org-b"},
    ]
    assert scope_to_organization(context(Role.CLIENT_READER), rows) == [rows[0]]


def test_superadmin_can_cross_organization_boundary() -> None:
    require_organization(context(Role.SUPERADMIN), "org-b")
