from typing import Any

from biocore.auth.models import SessionContext


class TenantScopeError(PermissionError):
    pass


def require_tenant(
    context: SessionContext,
    organization_id: str,
) -> None:
    if context.organization_id != organization_id and "superadmin" not in context.roles:
        raise TenantScopeError("Cross-organization access denied")


def require_project(
    context: SessionContext,
    project_id: str,
) -> None:
    if "superadmin" not in context.roles and project_id not in context.project_ids:
        raise TenantScopeError("Project access denied")


def scope_query(
    query: Any,
    context: SessionContext,
    *,
    organization_column: str = "organization_id",
    project_id: str | None = None,
    project_column: str = "project_id",
) -> Any:
    """Apply mandatory server-side tenant filters to a Supabase-like query."""
    scoped = query.eq(organization_column, context.organization_id)
    if project_id is not None:
        require_project(context, project_id)
        scoped = scoped.eq(project_column, project_id)
    return scoped
