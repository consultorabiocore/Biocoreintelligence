from biocore.components.module_access import (
    render_module_placeholder,
    require_module_page,
)
from biocore.domain.subscriptions import ModuleCode


require_module_page(
    ModuleCode.INTELLIGENCE,
    kicker="Ecosistema BioCore",
    title="BioCore Intelligence",
    subtitle=(
        "Analítica científica y capacidades geoespaciales especializadas, "
        "conectadas al historial de la organización."
    ),
)
render_module_placeholder(ModuleCode.INTELLIGENCE)
