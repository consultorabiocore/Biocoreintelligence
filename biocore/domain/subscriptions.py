from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum


class SubscriptionPlan(StrEnum):
    CORE = "core"
    PROFESSIONAL = "professional"
    ENTERPRISE = "enterprise"


class SubscriptionStatus(StrEnum):
    TRIAL = "trial"
    PENDING_ACTIVATION = "pending_activation"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    GRACE_PERIOD = "grace_period"
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
    ECOLOGICAL_DIAGNOSTIC = "ecological_diagnostic"
    ECOLOGICAL_DIAGNOSTIC_DETAILED = "ecological_diagnostic_detailed"


PLAN_MODULES: dict[SubscriptionPlan, frozenset[ModuleCode]] = {
    SubscriptionPlan.CORE: frozenset(
        {
            ModuleCode.PLATFORM_CORE,
            ModuleCode.REPORTS,
            ModuleCode.ECOLOGICAL_DIAGNOSTIC,
        }
    ),
    SubscriptionPlan.PROFESSIONAL: frozenset(
        {
            ModuleCode.PLATFORM_CORE,
            ModuleCode.FIELD,
            ModuleCode.DARWINCHECK,
            ModuleCode.REPORTS,
            ModuleCode.ECOLOGICAL_DIAGNOSTIC,
        }
    ),
    SubscriptionPlan.ENTERPRISE: frozenset(
        set(ModuleCode) - {ModuleCode.ECOLOGICAL_DIAGNOSTIC_DETAILED}
    ),
}


PLAN_LABELS: dict[SubscriptionPlan, str] = {
    SubscriptionPlan.CORE: "BioCore Core",
    SubscriptionPlan.PROFESSIONAL: "BioCore Professional",
    SubscriptionPlan.ENTERPRISE: "BioCore Enterprise",
}


STATUS_LABELS: dict[SubscriptionStatus, str] = {
    SubscriptionStatus.TRIAL: "Prueba",
    SubscriptionStatus.PENDING_ACTIVATION: "Pendiente de activación",
    SubscriptionStatus.ACTIVE: "Activa",
    SubscriptionStatus.PAST_DUE: "Pago pendiente",
    SubscriptionStatus.GRACE_PERIOD: "Periodo de gracia",
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
        if self.status not in {
            SubscriptionStatus.TRIAL,
            SubscriptionStatus.ACTIVE,
            SubscriptionStatus.GRACE_PERIOD,
        }:
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
class SubscriptionAddon:
    code: str
    status: str
    starts_on: date
    ends_on: date | None = None

    def is_active(self, today: date | None = None) -> bool:
        current_day = today or date.today()
        return (
            self.status == "active"
            and self.starts_on <= current_day
            and (self.ends_on is None or self.ends_on >= current_day)
        )


@dataclass(frozen=True)
class SubscriptionUsage:
    users_used: int = 0
    projects_used: int = 0
    storage_used_gb: float = 0.0
    processing_minutes: float = 0.0
    measured_on: date | None = None


@dataclass(frozen=True)
class ProjectAccessGrant:
    organization_id: str
    project_reference: str
    starts_on: date
    ends_on: date
    modules: frozenset[ModuleCode]
    included_users: int
    status: str = "active"
    renewable: bool = True
    converted_to_subscription: bool = False
    project_id_value: str | None = None

    @property
    def project_id(self) -> str:
        return self.project_id_value or self.project_reference

    def is_active(self, today: date | None = None) -> bool:
        current_day = today or date.today()
        return self.status == "active" and self.starts_on <= current_day <= self.ends_on


ProjectPlatformAccess = ProjectAccessGrant


@dataclass(frozen=True)
class SubscriptionSnapshot:
    organization_id: str
    organization_name: str
    subscription: OrganizationSubscription | None
    entitlements: tuple[ModuleEntitlement, ...] = ()
    project_grants: tuple[ProjectAccessGrant, ...] = ()
    usage: SubscriptionUsage = field(default_factory=SubscriptionUsage)
    data_available: bool = True
    configured_plan_modules: frozenset[ModuleCode] | None = None
    addons: tuple[SubscriptionAddon, ...] = ()

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
    def base_enabled_modules(self) -> frozenset[ModuleCode]:
        enabled: set[ModuleCode] = set()
        if self.subscription and self.subscription.grants_access():
            enabled.update(
                self.configured_plan_modules
                if self.configured_plan_modules is not None
                else PLAN_MODULES[self.subscription.plan]
            )
            for entitlement in self.entitlements:
                if not entitlement.is_within_period():
                    continue
                if entitlement.enabled:
                    enabled.add(entitlement.module_code)
                else:
                    enabled.discard(entitlement.module_code)

            addon_modules = {
                "lidar": ModuleCode.LIDAR,
                "satellite_monitoring": ModuleCode.SATELLITE,
                "api_access": ModuleCode.API_ACCESS,
                "advanced_reports": ModuleCode.REPORTS,
                "academy_training": ModuleCode.ACADEMY,
                "specialized_processing": ModuleCode.INTELLIGENCE,
            }
            for addon in self.addons:
                module = addon_modules.get(addon.code)
                if module and addon.is_active():
                    enabled.add(module)
        return frozenset(enabled)

    @property
    def project_module_map(self) -> dict[str, frozenset[ModuleCode]]:
        return {
            grant.project_id: grant.modules
            for grant in self.project_grants
            if grant.is_active() and not grant.converted_to_subscription
        }

    @property
    def enabled_modules(self) -> frozenset[ModuleCode]:
        enabled = set(self.base_enabled_modules)
        for modules in self.project_module_map.values():
            enabled.update(modules)
        return frozenset(enabled)

    def allows(self, module_code: ModuleCode) -> bool:
        return module_code in self.enabled_modules
