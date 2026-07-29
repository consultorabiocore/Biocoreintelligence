from biocore.auth.models import SessionContext


class EntitlementDenied(PermissionError):
    pass


def require_module(context: SessionContext, module_code: str) -> None:
    if not context.has_module(module_code):
        raise EntitlementDenied(f"Module not enabled: {module_code}")


def require_project_access(context: SessionContext, project_id: str) -> None:
    if not context.has_project(project_id):
        raise EntitlementDenied("Project is not authorized")
