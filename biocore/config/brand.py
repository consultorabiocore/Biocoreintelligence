import base64
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
BRAND_ASSETS = REPOSITORY_ROOT / "assets" / "brand"
MODULE_ASSETS = REPOSITORY_ROOT / "assets" / "modules"

BIOCORE_GREEN_DARK = "#12372A"
BIOCORE_GREEN = "#2F7D4A"
BIOCORE_GOLD = "#B58A38"
BIOCORE_BLUE = "#176B87"
BIOCORE_TEXT = "#14211B"
BIOCORE_BACKGROUND = "#F4F7F4"


def available_logo(preferred: Path, fallback: Path | None = None) -> Path | None:
    """Resolve a controlled brand fallback without mutating the source asset."""
    if preferred.is_file():
        return preferred
    if fallback is not None and fallback.is_file():
        return fallback
    return None


def asset_data_uri(preferred: Path, fallback: Path | None = None) -> str:
    """Encode an existing logo for HTML; return an empty string when unavailable."""
    path = available_logo(preferred, fallback)
    if path is None:
        return ""
    suffix = path.suffix.lower()
    media_type = "image/jpeg" if suffix in {".jpg", ".jpeg"} else "image/png"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{media_type};base64,{encoded}"


@dataclass(frozen=True)
class BrandConfig:
    name: str
    descriptor: str
    slogan: str
    master_logo: Path
    compact_logo: Path
    darwincheck_logo: Path
    intelligence_logo: Path
    field_logo: Path
    reports_logo: Path
    academy_logo: Path
    sales_email: str

    def demo_request_url(self, subject: str = "Solicitud de demostración BioCore") -> str:
        body = (
            "Hola BioCore,\n\n"
            "Quisiera solicitar una demostración de la plataforma.\n\n"
            "Organización:\n"
            "Nombre:\n"
            "Correo:\n"
            "Teléfono:\n"
            "Proyecto o necesidad principal:\n"
            "Módulos de interés:\n"
            "Horario preferido para la demostración:\n"
        )
        return (
            f"mailto:{self.sales_email}"
            f"?subject={quote(subject)}&body={quote(body)}"
        )


BRAND = BrandConfig(
    name="BioCore",
    descriptor="Plataforma de inteligencia ecológica",
    slogan="Transformamos datos en inteligencia ecológica",
    master_logo=BRAND_ASSETS / "biocore_platform_logo.png",
    compact_logo=BRAND_ASSETS / "biocore_mark.png",
    darwincheck_logo=MODULE_ASSETS / "darwincheck.png",
    intelligence_logo=MODULE_ASSETS / "biocore_intelligence.png",
    field_logo=MODULE_ASSETS / "biocore_mycofield.png",
    reports_logo=MODULE_ASSETS / "biocore_reports.png",
    academy_logo=MODULE_ASSETS / "biocore_academy.png",
    sales_email="consultorabiocore@gmail.com",
)
