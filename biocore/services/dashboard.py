from biocore.domain.dashboard import DashboardSnapshot, ProjectSummary
from biocore.domain.projects import PROJECT_STATUS_LABELS, Project
from biocore.domain.subscriptions import SubscriptionSnapshot


class DashboardService:
    """Build the private dashboard without placing data rules in Streamlit pages."""

    def build(
        self,
        subscription: SubscriptionSnapshot,
        *,
        projects: tuple[Project, ...] | None = None,
    ) -> DashboardSnapshot:
        """Create an honest snapshot from organization-scoped source records.

        ``None`` means the project source could not be read. An empty tuple
        means it was read successfully and the organization has no projects.
        The distinction prevents an integration problem from being presented
        as a real empty state.
        """

        project_summaries: tuple[ProjectSummary, ...] = ()
        active_projects: int | None = None
        projects_loaded = projects is not None
        if projects is not None:
            active_projects = len(projects)
            project_summaries = tuple(
                ProjectSummary(
                    id=project.id,
                    name=project.name,
                    code=project.code,
                    client=project.client_name,
                    current_stage=project.current_stage,
                    progress_percent=project.progress_percent,
                    responsible_name=project.responsible_name,
                    next_activity=project.next_activity,
                    status=PROJECT_STATUS_LABELS[project.status],
                    updated_at=project.updated_at,
                )
                for project in projects[:3]
            )
        elif subscription.subscription is not None:
            active_projects = subscription.usage.projects_used

        return DashboardSnapshot(
            active_projects=active_projects,
            projects_loaded=projects_loaded,
            recent_projects=project_summaries,
        )
