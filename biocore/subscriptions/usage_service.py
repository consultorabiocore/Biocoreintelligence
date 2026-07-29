from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class UsageDelta:
    users: int = 0
    projects: int = 0
    storage_gb: float = 0
    processing_minutes: float = 0


class UsageRepository(Protocol):
    def add(self, subscription_id: str, delta: UsageDelta) -> None:
        """Record metering without changing authorization rules."""


class UsageService:
    def __init__(self, repository: UsageRepository) -> None:
        self._repository = repository

    def record(self, subscription_id: str, delta: UsageDelta) -> None:
        if min(delta.users, delta.projects, delta.storage_gb, delta.processing_minutes) < 0:
            raise ValueError("Usage deltas cannot be negative")
        self._repository.add(subscription_id, delta)
