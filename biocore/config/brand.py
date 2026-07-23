from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
BRAND_ASSETS = REPOSITORY_ROOT / "assets" / "brand"


@dataclass(frozen=True)
class BrandConfig:
    name: str
    descriptor: str
    slogan: str
    master_logo: Path
    compact_logo: Path
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
            "Teléfono:\n"
        )
        return (
            f"mailto:{self.sales_email}"
            f"?subject={quote(subject)}&body={quote(body)}"
        )


BRAND = BrandConfig(
    name="BioCore",
    descriptor="Empresa de base científico-tecnológica",
    slogan="Transformamos datos en inteligencia ecológica",
    master_logo=BRAND_ASSETS / "biocore-logo-horizontal.png",
    # Hasta recibir el isotipo maestro por separado, la aplicación usa el logo
    # horizontal oficial también en la navegación privada.
    compact_logo=BRAND_ASSETS / "biocore-logo-horizontal.png",
    intelligence_logo=REPOSITORY_ROOT / "logo_biocore.png",
    field_logo=BRAND_ASSETS / "biocore-field.png",
    reports_logo=BRAND_ASSETS / "biocore-reports.png",
    academy_logo=BRAND_ASSETS / "biocore-academy.png",
    sales_email="consultorabiocore@gmail.com",
)
