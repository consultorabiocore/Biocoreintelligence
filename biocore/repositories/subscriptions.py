from datetime import date
from typing import Any, Protocol

from biocore.domain.subscriptions import (
    ModuleCode,
    ModuleEntitlement,
    OrganizationSubscription,
    ProjectAccessGrant,
    SubscriptionPlan,
    SubscriptionSnapshot,
    SubscriptionStatus,
    SubscriptionUsage,
)


class SubscriptionRepository(Protocol):
    def get_snapshot(self, organization_id: str) -> SubscriptionSnapshot:
        """Return the subscription state scoped to one organization."""


def _parse_date(value: object) -> date | None:
    if value in (None, ""):
        return None
    return date.fromisoformat(str(value)[:10])


class SupabaseSubscriptionRepository:
    """Read subscription data with a trusted server-side Supabase client."""

    def __init__(self, client: Any) -> None:
        self._client = client

    def _get_project_grants(
        self, organization_id: str
    ) -> tuple[ProjectAccessGrant, ...]:
        response = (
            self._client.table("project_access_grants")
            .select(
                "organization_id,project_reference,starts_on,ends_on,modules,"
                "included_users,renewable,converted_to_subscription"
            )
            .eq("organization_id", organization_id)
            .execute()
        )
        return tuple(
            ProjectAccessGrant(
                organization_id=str(item["organization_id"]),
                project_reference=str(item["project_reference"]),
                starts_on=_parse_date(item["starts_on"]) or date.today(),
                ends_on=_parse_date(item["ends_on"]) or date.today(),
                modules=frozenset(
                    ModuleCode(str(module)) for module in (item.get("modules") or [])
                ),
                included_users=int(item.get("included_users") or 1),
                renewable=bool(item.get("renewable", True)),
                converted_to_subscription=bool(
                    item.get("converted_to_subscription", False)
                ),
            )
            for item in (response.data or [])
        )

    def get_snapshot(self, organization_id: str) -> SubscriptionSnapshot:
        organization_response = (
            self._client.table("organizations")
            .select("name")
            .eq("id", organization_id)
            .limit(1)
            .execute()
        )
        organizations = organization_response.data or []
        organization_name = (
            str(organizations[0]["name"])
            if organizations
            else "Organización BioCore"
        )

        subscription_response = (
            self._client.table("organization_subscriptions")
            .select(
                "id,organization_id,plan,status,starts_on,renews_on,"
                "user_limit,project_limit,storage_limit_gb,support_level"
            )
            .eq("organization_id", organization_id)
            .limit(1)
            .execute()
        )
        rows = subscription_response.data or []
        project_grants = self._get_project_grants(organization_id)
        if not rows:
            return SubscriptionSnapshot(
                organization_id=organization_id,
                organization_name=organization_name,
                subscription=None,
                project_grants=project_grants,
            )

        row = rows[0]
        subscription = OrganizationSubscription(
            id=str(row["id"]),
            organization_id=str(row["organization_id"]),
            plan=SubscriptionPlan(str(row["plan"])),
            status=SubscriptionStatus(str(row["status"])),
            starts_on=_parse_date(row["starts_on"]) or date.today(),
            renews_on=_parse_date(row.get("renews_on")),
            user_limit=int(row.get("user_limit") or 0),
            project_limit=int(row.get("project_limit") or 0),
            storage_limit_gb=float(row.get("storage_limit_gb") or 0),
            support_level=str(row.get("support_level") or "estándar"),
        )

        entitlements_response = (
            self._client.table("module_entitlements")
            .select("module_code,enabled,source,starts_on,ends_on")
            .eq("subscription_id", subscription.id)
            .execute()
        )
        entitlements = tuple(
            ModuleEntitlement(
                module_code=ModuleCode(str(item["module_code"])),
                enabled=bool(item.get("enabled", True)),
                source=str(item.get("source") or "plan"),
                starts_on=_parse_date(item.get("starts_on")),
                ends_on=_parse_date(item.get("ends_on")),
            )
            for item in (entitlements_response.data or [])
        )

        usage_response = (
            self._client.table("subscription_usage")
            .select("users_used,projects_used,storage_used_gb,measured_on")
            .eq("subscription_id", subscription.id)
            .limit(1)
            .execute()
        )
        usage_rows = usage_response.data or []
        usage = SubscriptionUsage()
        if usage_rows:
            usage_row = usage_rows[0]
            usage = SubscriptionUsage(
                users_used=int(usage_row.get("users_used") or 0),
                projects_used=int(usage_row.get("projects_used") or 0),
                storage_used_gb=float(usage_row.get("storage_used_gb") or 0),
                measured_on=_parse_date(usage_row.get("measured_on")),
            )

        return SubscriptionSnapshot(
            organization_id=organization_id,
            organization_name=organization_name,
            subscription=subscription,
            entitlements=entitlements,
            project_grants=project_grants,
            usage=usage,
        )
