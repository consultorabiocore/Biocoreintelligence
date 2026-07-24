from collections.abc import Mapping
from dataclasses import dataclass
from urllib.parse import urlparse

from biocore.config.settings import Settings
from biocore.domain.subscriptions import ModuleCode


@dataclass(frozen=True)
class ExternalApplication:
    """Safe launch metadata for an application outside the platform shell."""

    code: str
    label: str
    module_code: ModuleCode
    url: str | None
    description: str
    secret_key: str

    @property
    def is_configured(self) -> bool:
        return self.url is not None


def normalize_external_url(value: object) -> str | None:
    """Accept only explicit HTTP(S) application URLs."""
    if not isinstance(value, str):
        return None
    candidate = value.strip()
    if not candidate:
        return None
    parsed = urlparse(candidate)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return candidate


def _configured_url(
    secret_values: Mapping[str, object],
    secret_key: str,
    environment_value: str | None,
) -> str | None:
    return normalize_external_url(
        secret_values.get(secret_key) or environment_value
    )


def external_applications(
    settings: Settings,
    secret_values: Mapping[str, object] | None = None,
) -> dict[str, ExternalApplication]:
    """Build a deterministic catalog without importing Streamlit."""
    values = secret_values or {}
    return {
        "field": ExternalApplication(
            code="field",
            label="BioCore Field",
            module_code=ModuleCode.FIELD,
            url=_configured_url(values, "field_url", settings.field_url),
            description=(
                "Captura y organización de observaciones, fotografías y datos "
                "georreferenciados de terreno."
            ),
            secret_key="field_url",
        ),
        "darwincheck": ExternalApplication(
            code="darwincheck",
            label="DarwinCheck",
            module_code=ModuleCode.DARWINCHECK,
            url=_configured_url(
                values,
                "darwincheck_url",
                settings.darwincheck_url,
            ),
            description=(
                "Validación y revisión de consistencia para conjuntos de datos "
                "Darwin Core."
            ),
            secret_key="darwincheck_url",
        ),
        "intelligence": ExternalApplication(
            code="intelligence",
            label="BioCore Intelligence",
            module_code=ModuleCode.INTELLIGENCE,
            url=_configured_url(
                values,
                "intelligence_url",
                settings.intelligence_url,
            ),
            description=(
                "Analítica ecológica y herramientas científicas especializadas."
            ),
            secret_key="intelligence_url",
        ),
        "geot_radar": ExternalApplication(
            code="geot_radar",
            label="Simulador de cobertura radar geotécnico",
            module_code=ModuleCode.INTELLIGENCE,
            url=_configured_url(
                values,
                "geot_radar_url",
                settings.geot_radar_url,
            ),
            description=(
                "Simula geometría y cobertura de radar para monitoreo de taludes. "
                "Esta herramienta utiliza radar; no corresponde a LiDAR."
            ),
            secret_key="geot_radar_url",
        ),
    }
