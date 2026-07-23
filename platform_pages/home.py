from biocore.components.dashboard import render_private_dashboard
from biocore.components.module_access import enforce_module_access
from biocore.domain.subscriptions import ModuleCode
from biocore.services.dashboard import DashboardService


context, subscription = enforce_module_access(ModuleCode.PLATFORM_CORE)
dashboard = DashboardService().build(subscription)
render_private_dashboard(context, subscription, dashboard)
