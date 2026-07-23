from biocore.domain.dashboard import DashboardSnapshot
from biocore.domain.subscriptions import SubscriptionSnapshot


class DashboardService:
    """Build the private dashboard without placing data rules in Streamlit pages."""

    def build(self, subscription: SubscriptionSnapshot) -> DashboardSnapshot:
        # Project and campaign repositories will populate these fields in the
        # next integration. None is deliberate: the UI must not present demo
        # values as if they belonged to the authenticated organization.
        return DashboardSnapshot(
            active_projects=(
                subscription.usage.projects_used
                if subscription.subscription is not None
                else None
            )
        )
