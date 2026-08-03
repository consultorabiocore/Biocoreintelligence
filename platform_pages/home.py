import logging

import streamlit as st

from biocore.components.dashboard import render_private_dashboard
from biocore.components.module_access import enforce_module_access
from biocore.domain.subscriptions import ModuleCode
from biocore.services.dashboard import DashboardService


LOGGER = logging.getLogger(__name__)

context, subscription = enforce_module_access(ModuleCode.PLATFORM_CORE)
projects = None
project_service = st.session_state.get("biocore_project_service")
if project_service is not None and callable(getattr(project_service, "list", None)):
    try:
        projects = project_service.list(context)
    except Exception:
        LOGGER.exception("Could not load organization projects for home dashboard")

dashboard = DashboardService().build(subscription, projects=projects)
render_private_dashboard(context, subscription, dashboard)
