from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum


class SubscriptionPlan(StrEnum):
    CORE = "core"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"


class SubscriptionStatus(StrEnum):
    TRIAL = "trial"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    SUSPENDED = "suspended"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class ModuleCode(StrEnum):
    PLATFORM_CORE = "platform_core"
    FIELD = "field"
    DARWINCHECK = "darwincheck"
    INTELLIGENCE = "intelligence"
    SATELLITE = "satellite"
    LIDAR = "lidar"
    REPORTS = "reports"
    ACADEMY = "academy"
    API_ACCESS = "api_access"


PLAN_MODULES: dict[SubscriptionPlan, frozenset[ModuleCode]] = {
    SubscriptionPlan.CORE: frozenset(
        {
            ModuleCode.PLATFORM_CORE,
            ModuleCode.REPORTS,
        }
    ),
    SubscriptionPlan.PROFESSIONAL: frozenset(
        {
            ModuleCode.PLATFORM_CORE,
            ModuleCode.FIELD,
            ModuleCode.DARWINCHECK,
            ModuleCode.REPORTS,
        }
    ),
    SubscriptionPlan.ENTERPRISE: frozenset(ModuleCode),
}


PLAN_LABELS: dict[SubscriptionPlan, str] = {
    SubscriptionPlan.CORE: "BioCore Core",
    SubscriptionPlan.PROFESSIONAL: "BioCore Professional",
    SubscriptionPlan.ENTERPRISE: "BioCore Enterprise",
}


STATUS_LABELS: dict[SubscriptionStatus, str] = {
    SubscriptionStatus.TRIAL: "Prueba",
    SubscriptionStatus.ACTIVE: "Activa",
    SubscriptionStatus.PAST_DUE: "Pago pendiente",
    SubscriptionStatus.SUSPENDED: "Suspendida",
    SubscriptionStatus.CANCELLED: "Cancelada",
    SubscriptionStatus.EXPIRED: "Expirada",
}


@dataclass(frozen=True)
class OrganizationSubscription:
    id: str
    organization_id: str
    plan: SubscriptionPlan
    status: SubscriptionStatus
    starts_on: date
    renews_on: date | None
    user_limit: int
    project_limit: int
    storage_limit_gb: float
    support_level: str

    def grants_access(self, today: date | None = None) -> bool:
        current_day = today or date.today()
        if self.starts_on > current_day:
            return False
        if self.status not in {SubscriptionStatus.TRIAL, SubscriptionStatus.ACTIVE}:
            return False
        return self.renews_on is None or self.renews_on >= current_day


@dataclass(frozen=True)
class ModuleEntitlement:
    module_code: ModuleCode
    enabled: bool
    source: str = "plan"
    starts_on: date | None = None
    ends_on: date | None = None

    def is_within_period(self, today: date | None = None) -> bool:
        current_day = today or date.today()
        if self.starts_on and self.starts_on > current_day:
            return False
        return not self.ends_on or self.ends_on >= current_day

    def is_effective(self, today: date | None = None) -> bool:
        return self.enabled and self.is_within_period(today)


@dataclass(frozen=True)
class SubscriptionUsage:
    users_used: int = 0
    projects_used: int = 0
    storage_used_gb: float = 0.0
    measured_on: date | None = None


@dataclass(frozen=True)
class ProjectAccessGrant:
    organization_id: str
    project_reference: str
    starts_on: date
    ends_on: date
    modules: frozenset[ModuleCode]
    included_users: int
    renewable: bool = True
    converted_to_subscription: bool = False

    def is_active(self, today: date | None = None) -> bool:
        current_day = today or date.today()
        return self.starts_on <= current_day <= self.ends_on


@dataclass(frozen=True)
class SubscriptionSnapshot:
    organization_id: str
    organization_name: str
    subscription: OrganizationSubscription | None
    entitlements: tuple[ModuleEntitlement, ...] = ()
    project_grants: tuple[ProjectAccessGrant, ...] = ()
    usage: SubscriptionUsage = field(default_factory=SubscriptionUsage)
    data_available: bool = True

    @classmethod
    def unconfigured(
        cls,
        organization_id: str,
        organization_name: str = "Organización BioCore",
        *,
        data_available: bool = True,
    ) -> "SubscriptionSnapshot":
        return cls(
            organization_id=organization_id,
            organization_name=organization_name,
            subscription=None,
            data_available=data_available,
        )

    @property
    def enabled_modules(self) -> frozenset[ModuleCode]:
        enabled: set[ModuleCode] = set()
        if self.subscription and self.subscription.grants_access():
            enabled.update(PLAN_MODULES[self.subscription.plan])
            for entitlement in self.entitlements:
                if not entitlement.is_within_period():
                    continue
                if entitlement.enabled:
                    enabled.add(entitlement.module_code)
                else:
                    enabled.discard(entitlement.module_code)

        for grant in self.project_grants:
            if grant.is_active() and not grant.converted_to_subscription:
                enabled.update(grant.modules)
        return frozenset(enabled)

    def allows(self, module_code: ModuleCode) -> bool:
        return module_code in self.enabled_modules
