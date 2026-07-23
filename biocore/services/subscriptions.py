from biocore.domain.subscriptions import ModuleCode, SubscriptionSnapshot
from biocore.repositories.subscriptions import SubscriptionRepository
from biocore.security.authorization import UserContext
from biocore.security.roles import Role


class ModuleAccessDenied(PermissionError):
    """Raised when a user lacks a module entitlement."""


def user_can_access_module(
    user_id: str,
    organization_id: str,
    module_code: ModuleCode | str,
    *,
    context: UserContext,
    subscription: SubscriptionSnapshot,
) -> bool:
    """Authorize a module using trusted context plus organization subscription."""
    if context.user_id != user_id:
        return False
    if context.organization_id != organization_id:
        return False
    if subscription.organization_id != organization_id:
        return False
    if Role.SUPERADMIN in context.roles:
        return True
    return subscription.allows(ModuleCode(module_code))


def require_module_access(
    context: UserContext,
    subscription: SubscriptionSnapshot,
    module_code: ModuleCode | str,
) -> None:
    if not user_can_access_module(
        context.user_id,
        context.organization_id,
        module_code,
        context=context,
        subscription=subscription,
    ):
        raise ModuleAccessDenied(f"Module not enabled: {module_code}")


class SubscriptionService:
    def __init__(self, repository: SubscriptionRepository) -> None:
        self._repository = repository

    def resolve_for(self, context: UserContext) -> SubscriptionSnapshot:
        try:
            return self._repository.get_snapshot(context.organization_id)
        except Exception:
            # Authentication must remain available while the migration is being
            # rolled out. Non-superadmins receive no paid module entitlement.
            return SubscriptionSnapshot.unconfigured(
                context.organization_id,
                data_available=False,
            )

    def can_access(
        self,
        context: UserContext,
        subscription: SubscriptionSnapshot,
        module_code: ModuleCode | str,
    ) -> bool:
        return user_can_access_module(
            context.user_id,
            context.organization_id,
            module_code,
            context=context,
            subscription=subscription,
        )
