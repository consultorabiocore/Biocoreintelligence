from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Mapping, Protocol


@dataclass(frozen=True)
class AuditEvent:
    event_code: str
    outcome: str
    organization_id: str | None = None
    user_id: str | None = None
    session_id: str | None = None
    resource_type: str | None = None
    resource_id: str | None = None
    metadata: Mapping[str, object] = field(default_factory=dict)
    occurred_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


class AuditWriter(Protocol):
    def write(self, event: AuditEvent) -> None:
        """Persist a security or authorization event."""


class AuditService:
    def __init__(self, writer: AuditWriter) -> None:
        self._writer = writer

    def record(self, event: AuditEvent) -> None:
        if event.outcome not in {"success", "denied", "failure"}:
            raise ValueError("Invalid audit outcome")
        self._writer.write(event)
