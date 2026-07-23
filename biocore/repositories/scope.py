from typing import Protocol, TypeVar

from biocore.security.authorization import UserContext
from biocore.security.roles import Role


Query = TypeVar("Query", bound="OrganizationFilter")


class OrganizationFilter(Protocol):
    def eq(self: Query, column: str, value: object) -> Query: ...


def apply_organization_scope(query: Query, context: UserContext) -> Query:
    """Apply tenant isolation before a query is sent to the data service."""
    if Role.SUPERADMIN in context.roles:
        return query
    return query.eq("organization_id", context.organization_id)
