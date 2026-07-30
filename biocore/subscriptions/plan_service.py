from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class PlanDefinition:
    id: str
    slug: str
    display_name: str
    user_limit: int
    project_limit: int
    storage_limit_gb: float
    modules: frozenset[str]
    active: bool = True


class PlanRepository(Protocol):
    def get_by_slug(self, slug: str) -> PlanDefinition | None:
        """Return one configurable plan without embedding prices in code."""


class PlanService:
    def __init__(self, repository: PlanRepository) -> None:
        self._repository = repository

    def require_active(self, slug: str) -> PlanDefinition:
        plan = self._repository.get_by_slug(slug)
        if plan is None or not plan.active:
            raise LookupError("Subscription plan is not available")
        return plan
