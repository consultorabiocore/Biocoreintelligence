from dataclasses import dataclass, field

from biocore.repositories.scope import apply_organization_scope
from biocore.security.authorization import UserContext
from biocore.security.roles import Role


@dataclass
class FakeQuery:
    filters: list[tuple[str, object]] = field(default_factory=list)

    def eq(self, column: str, value: object) -> "FakeQuery":
        self.filters.append((column, value))
        return self


def test_client_query_is_scoped_before_execution() -> None:
    query = FakeQuery()
    context = UserContext("user-1", "org-a", frozenset({Role.CLIENT_READER}))
    apply_organization_scope(query, context)
    assert query.filters == [("organization_id", "org-a")]


def test_superadmin_query_is_not_tenant_scoped() -> None:
    query = FakeQuery()
    context = UserContext("user-1", "org-a", frozenset({Role.SUPERADMIN}))
    apply_organization_scope(query, context)
    assert query.filters == []
