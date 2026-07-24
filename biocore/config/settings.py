from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    environment: str
    supabase_url: str | None
    supabase_key: str | None
    supabase_service_role_key: str | None
    field_url: str | None = None
    darwincheck_url: str | None = None
    intelligence_url: str | None = None
    geot_radar_url: str | None = None

    @classmethod
    def from_environment(cls) -> "Settings":
        return cls(
            environment=os.getenv("BIOCORE_ENV", "development"),
            supabase_url=os.getenv("SUPABASE_URL"),
            supabase_key=os.getenv("SUPABASE_KEY"),
            supabase_service_role_key=os.getenv("SUPABASE_SERVICE_ROLE_KEY"),
            field_url=os.getenv(
                "BIOCORE_FIELD_URL",
                "https://hongos.streamlit.app/",
            ),
            darwincheck_url=os.getenv(
                "DARWINCHECK_URL",
                "https://darwin-check.streamlit.app/",
            ),
            intelligence_url=os.getenv(
                "BIOCORE_INTELLIGENCE_URL",
                "https://biocoreintelligence.streamlit.app/",
            ),
            geot_radar_url=os.getenv(
                "GEOT_RADAR_URL",
                "https://nibaldox.github.io/GeotRadarSim/",
            ),
        )
