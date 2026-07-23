from datetime import date, timedelta

from biocore.domain.subscriptions import (
    ModuleCode,
    ModuleEntitlement,
    OrganizationSubscription,
    ProjectAccessGrant,
    SubscriptionPlan,
    SubscriptionSnapshot,
    SubscriptionStatus,
)
from biocore.security.authorization import UserContext
from biocore.security.roles import Role
from biocore.services.subscriptions import (
    SubscriptionService,
    user_can_access_module,
)


def subscription(
    *,
    plan: SubscriptionPlan = SubscriptionPlan.CORE,
    status: SubscriptionStatus = SubscriptionStatus.ACTIVE,
) -> OrganizationSubscription:
    return OrganizationSubscription(
        id="subscription-1",
        organization_id="org-a",
        plan=plan,
        status=status,
        starts_on=date.today(),
        renews_on=date.today() + timedelta(days=30),
        user_limit=5,
        project_limit=3,
        storage_limit_gb=10,
        support_level="estándar",
    )


def snapshot(
    *,
    plan: SubscriptionPlan = SubscriptionPlan.CORE,
    status: SubscriptionStatus = SubscriptionStatus.ACTIVE,
    entitlements: tuple[ModuleEntitlement, ...] = (),
) -> SubscriptionSnapshot:
    return SubscriptionSnapshot(
        organization_id="org-a",
        organization_name="Organización A",
        subscription=subscription(plan=plan, status=status),
        entitlements=entitlements,
    )


def client_context() -> UserContext:
    return UserContext("user-1", "org-a", frozenset({Role.CLIENT_READER}))


def test_core_plan_allows_platform_and_reports_only() -> None:
    current = snapshot()
    assert current.allows(ModuleCode.PLATFORM_CORE)
    assert current.allows(ModuleCode.REPORTS)
    assert not current.allows(ModuleCode.INTELLIGENCE)


def test_entitlement_can_enable_or_disable_a_plan_module() -> None:
    current = snapshot(
        entitlements=(
            ModuleEntitlement(ModuleCode.INTELLIGENCE, True, "add_on"),
            ModuleEntitlement(ModuleCode.REPORTS, False, "manual"),
        )
    )
    assert current.allows(ModuleCode.INTELLIGENCE)
    assert not current.allows(ModuleCode.REPORTS)


def test_expired_add_on_does_not_remove_a_plan_module() -> None:
    current = snapshot(
        entitlements=(
            ModuleEntitlement(
                ModuleCode.REPORTS,
                True,
                "add_on",
                ends_on=date.today() - timedelta(days=1),
            ),
        )
    )
    assert current.allows(ModuleCode.REPORTS)


def test_inactive_subscription_denies_modules() -> None:
    current = snapshot(status=SubscriptionStatus.SUSPENDED)
    assert current.enabled_modules == frozenset()


def test_active_project_grant_can_provide_temporary_module_access() -> None:
    grant = ProjectAccessGrant(
        organization_id="org-a",
        project_reference="project-2026-01",
        starts_on=date.today() - timedelta(days=1),
        ends_on=date.today() + timedelta(days=30),
        modules=frozenset({ModuleCode.FIELD}),
        included_users=3,
    )
    current = SubscriptionSnapshot(
        organization_id="org-a",
        organization_name="Organización A",
        subscription=None,
        project_grants=(grant,),
    )
    assert current.allows(ModuleCode.FIELD)
    assert not current.allows(ModuleCode.INTELLIGENCE)


def test_module_authorization_rejects_user_and_organization_mismatch() -> None:
    context = client_context()
    current = snapshot()
    assert user_can_access_module(
        "user-1",
        "org-a",
        ModuleCode.PLATFORM_CORE,
        context=context,
        subscription=current,
    )
    assert not user_can_access_module(
        "another-user",
        "org-a",
        ModuleCode.PLATFORM_CORE,
        context=context,
        subscription=current,
    )
    assert not user_can_access_module(
        "user-1",
        "org-b",
        ModuleCode.PLATFORM_CORE,
        context=context,
        subscription=current,
    )


def test_superadmin_can_configure_an_unconfigured_organization() -> None:
    context = UserContext("admin-1", "org-a", frozenset({Role.SUPERADMIN}))
    current = SubscriptionSnapshot.unconfigured("org-a")
    assert user_can_access_module(
        "admin-1",
        "org-a",
        ModuleCode.INTELLIGENCE,
        context=context,
        subscription=current,
    )


class FailingRepository:
    def get_snapshot(self, organization_id: str) -> SubscriptionSnapshot:
        raise RuntimeError("migration not applied")


def test_service_fallback_does_not_grant_paid_modules_to_clients() -> None:
    context = client_context()
    current = SubscriptionService(FailingRepository()).resolve_for(context)
    assert not current.data_available
    assert not current.allows(ModuleCode.PLATFORM_CORE)
