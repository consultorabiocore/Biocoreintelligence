from biocore.components.module_access import (
    render_module_placeholder,
    require_module_page,
)
from biocore.domain.subscriptions import ModuleCode


require_module_page(
    ModuleCode.DARWINCHECK,
    kicker="Ecosistema BioCore",
    title="DarwinCheck",
    subtitle=(
        "Valida consistencia, calidad y trazabilidad antes de usar los datos "
        "en análisis e informes."
    ),
)
render_module_placeholder(ModuleCode.DARWINCHECK)
