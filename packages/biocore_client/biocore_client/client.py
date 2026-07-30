from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping
from urllib.parse import urlencode

import requests

from .errors import (
    BioCoreAccessDenied,
    BioCoreAuthRequired,
    BioCoreClientError,
    BioCoreUnavailable,
)


@dataclass(frozen=True)
class ClientSessionContext:
    token: str
    session_id: str
    user_id: str
    organization_id: str
    roles: frozenset[str]
    permissions: frozenset[str]
    modules: frozenset[str]
    project_ids: frozenset[str]
    audience: str
    started_at: datetime
    expires_at: datetime
    project_modules: Mapping[str, frozenset[str]]

    def require_permission(self, permission_code: str) -> None:
        if permission_code not in self.permissions:
            raise BioCoreAccessDenied(f"Permission denied: {permission_code}")

    def require_module(self, module_code: str) -> None:
        if module_code not in self.modules:
            raise BioCoreAccessDenied(f"Module not enabled: {module_code}")

    def require_project(self, project_id: str) -> None:
        if project_id not in self.project_ids:
            raise BioCoreAccessDenied("Project access denied")

    def require_project_module(
        self, project_id: str, module_code: str
    ) -> None:
        self.require_project(project_id)
        if module_code not in self.project_modules.get(project_id, frozenset()):
            raise BioCoreAccessDenied("Module is not enabled for this project")


class BioCoreClient:
    """Small server-side client; never place the central token in a URL."""

    def __init__(
        self,
        base_url: str,
        *,
        timeout_seconds: float = 10,
        http: requests.Session | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds
        self._http = http or requests.Session()

    def authorization_url(
        self,
        module_code: str,
        return_to: str,
        project_id: str | None = None,
    ) -> str:
        values = {"module_code": module_code, "return_to": return_to}
        if project_id:
            values["project_id"] = project_id
        return f"{self._base_url}/v1/authorize?{urlencode(values)}"

    def require_authenticated(
        self,
        *,
        module_code: str,
        return_to: str,
        session_token: str | None,
        launch_code: str | None = None,
        project_id: str | None = None,
    ) -> ClientSessionContext:
        if launch_code:
            context = self.exchange_launch_code(launch_code, module_code)
        elif session_token:
            context = self.get_session(session_token)
        else:
            raise BioCoreAuthRequired(
                self.authorization_url(module_code, return_to, project_id)
            )
        if project_id:
            context.require_project(project_id)
            if module_code not in context.modules:
                context.require_project_module(project_id, module_code)
        else:
            context.require_module(module_code)
        return context

    def exchange_launch_code(
        self, launch_code: str, module_code: str
    ) -> ClientSessionContext:
        response = self._request(
            "POST",
            "/v1/module-exchange",
            json={"code": launch_code, "module_code": module_code},
        )
        return self._context(response)

    def get_session(self, token: str) -> ClientSessionContext:
        response = self._request(
            "GET",
            "/v1/session",
            headers={"Authorization": f"Bearer {token}"},
        )
        return self._context(response, token=token)

    def revoke(self, token: str) -> None:
        self._request(
            "POST",
            "/v1/session/revoke",
            headers={"Authorization": f"Bearer {token}"},
            expected_status=204,
        )

    def _request(
        self,
        method: str,
        path: str,
        *,
        expected_status: int = 200,
        **kwargs: Any,
    ) -> dict[str, Any]:
        try:
            response = self._http.request(
                method,
                f"{self._base_url}{path}",
                timeout=self._timeout,
                **kwargs,
            )
        except requests.RequestException as exc:
            raise BioCoreUnavailable(
                "Central BioCore authentication is unavailable"
            ) from exc
        if response.status_code in {401, 403}:
            raise BioCoreAccessDenied("Central BioCore access was denied")
        if response.status_code != expected_status:
            raise BioCoreClientError(
                f"Central BioCore request failed ({response.status_code})"
            )
        if expected_status == 204:
            return {}
        try:
            return dict(response.json())
        except ValueError as exc:
            raise BioCoreClientError("Central BioCore response is invalid") from exc

    @staticmethod
    def _context(
        values: dict[str, Any],
        *,
        token: str | None = None,
    ) -> ClientSessionContext:
        session_token = token or str(values.get("token") or "")
        if not session_token:
            raise BioCoreClientError("Central session token is missing")
        return ClientSessionContext(
            token=session_token,
            session_id=str(values["session_id"]),
            user_id=str(values["user_id"]),
            organization_id=str(values["organization_id"]),
            roles=frozenset(str(item) for item in values.get("roles", [])),
            permissions=frozenset(
                str(item) for item in values.get("permissions", [])
            ),
            modules=frozenset(str(item) for item in values.get("modules", [])),
            project_ids=frozenset(
                str(item) for item in values.get("project_ids", [])
            ),
            audience=str(values["audience"]),
            started_at=datetime.fromisoformat(
                str(values["started_at"]).replace("Z", "+00:00")
            ),
            expires_at=datetime.fromisoformat(
                str(values["expires_at"]).replace("Z", "+00:00")
            ),
            project_modules={
                str(project_id): frozenset(str(item) for item in modules)
                for project_id, modules in dict(
                    values.get("project_modules") or {}
                ).items()
            },
        )
