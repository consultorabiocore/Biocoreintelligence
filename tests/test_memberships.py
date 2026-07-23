from dataclasses import dataclass

import pytest

from biocore.repositories.memberships import (
    IdentityNotProvisionedError,
    OrganizationSelectionRequired,
    SupabaseMembershipResolver,
)
from biocore.security.identity import AuthenticatedIdentity
from biocore.security.roles import Role


@dataclass
class Response:
    data: list[dict[str, object]]


class Query:
    def __init__(self, rows: list[dict[str, object]]) -> None:
        self.rows = rows
        self.filters: list[tuple[str, object]] = []

    def select(self, _columns: str) -> "Query":
        return self

    def eq(self, column: str, value: object) -> "Query":
        self.filters.append((column, value))
        return self

    def limit(self, _count: int) -> "Query":
        return self

    def execute(self) -> Response:
        rows = [
            row
            for row in self.rows
            if all(row.get(column) == value for column, value in self.filters)
        ]
        return Response(rows)


class Client:
    def __init__(self, tables: dict[str, list[dict[str, object]]]) -> None:
        self.tables = tables

    def table(self, name: str) -> Query:
        return Query(self.tables[name])


def resolver(memberships: list[dict[str, object]]) -> SupabaseMembershipResolver:
    return SupabaseMembershipResolver(
        Client(
            {
                "app_users": [
                    {"id": "user-1", "external_subject": "oidc|1", "active": True}
                ],
                "memberships": memberships,
            }
        )
    )


def identity() -> AuthenticatedIdentity:
    return AuthenticatedIdentity("oidc|1", "user@example.com")


def test_resolver_uses_database_roles() -> None:
    result = resolver(
        [
            {
                "user_id": "user-1",
                "organization_id": "org-a",
                "role": "cliente_lector",
                "active": True,
            }
        ]
    ).resolve_context(identity())
    assert result.organization_id == "org-a"
    assert result.roles == frozenset({Role.CLIENT_READER})


def test_multiple_organizations_require_explicit_selection() -> None:
    memberships = [
        {"user_id": "user-1", "organization_id": org, "role": "cliente_lector", "active": True}
        for org in ("org-a", "org-b")
    ]
    with pytest.raises(OrganizationSelectionRequired):
        resolver(memberships).resolve_context(identity())


def test_unknown_organization_is_rejected() -> None:
    memberships = [
        {"user_id": "user-1", "organization_id": "org-a", "role": "cliente_lector", "active": True}
    ]
    with pytest.raises(IdentityNotProvisionedError):
        resolver(memberships).resolve_context(identity(), "org-b")
