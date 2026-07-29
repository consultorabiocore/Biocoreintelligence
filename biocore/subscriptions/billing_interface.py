from dataclasses import dataclass
from typing import Mapping, Protocol


@dataclass(frozen=True)
class BillingEvent:
    organization_id: str
    event_code: str
    subscription_id: str | None = None
    provider: str | None = None
    external_reference: str | None = None
    metadata: Mapping[str, object] | None = None


class BillingEventRepository(Protocol):
    def append(self, event: BillingEvent) -> None:
        """Persist a commercial event without charging a payment method."""


class BillingInterface:
    """No-payment boundary prepared for a future approved provider."""

    def __init__(self, repository: BillingEventRepository) -> None:
        self._repository = repository

    def record(self, event: BillingEvent) -> None:
        self._repository.append(event)
