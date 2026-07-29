from datetime import datetime, timedelta, timezone

import pytest

from packages.biocore_client.biocore_client.client import (
    BioCoreClient,
    ClientSessionContext,
)
from packages.biocore_client.biocore_client.errors import BioCoreAccessDenied


def client_context(
    *,
    modules: frozenset[str] = frozenset(),
    project_modules: dict[str, frozenset[str]] | None = None,
) -> ClientSessionContext:
    now = datetime.now(timezone.utc)
    return ClientSessionContext(
        token="session-token",
        session_id="session-1",
        user_id="user-1",
        organization_id="org-a",
        roles=frozenset({"cliente_editor"}),
        permissions=frozenset({"field:read"}),
        modules=modules,
        project_ids=frozenset({"project-a"}),
        audience="field",
        started_at=now,
        expires_at=now + timedelta(hours=1),
        project_modules=project_modules or {},
    )


class StubClient(BioCoreClient):
    def __init__(self, context: ClientSessionContext) -> None:
        super().__init__("https://auth.example.com")
        self.context = context

    def get_session(self, token: str) -> ClientSessionContext:
        return self.context


def test_global_module_access_does_not_require_a_project_grant() -> None:
    expected = client_context(modules=frozenset({"field"}))
    result = StubClient(expected).require_authenticated(
        module_code="field",
        return_to="https://field.example.com",
        session_token="token",
    )
    assert result == expected


def test_project_scoped_module_access_is_accepted_without_global_entitlement() -> None:
    expected = client_context(
        project_modules={"project-a": frozenset({"field"})}
    )
    result = StubClient(expected).require_authenticated(
        module_code="field",
        return_to="https://field.example.com",
        session_token="token",
        project_id="project-a",
    )
    assert result == expected


def test_project_scoped_module_access_rejects_another_module() -> None:
    current = client_context(
        project_modules={"project-a": frozenset({"field"})}
    )
    with pytest.raises(BioCoreAccessDenied):
        StubClient(current).require_authenticated(
            module_code="darwincheck",
            return_to="https://darwin.example.com",
            session_token="token",
            project_id="project-a",
        )
