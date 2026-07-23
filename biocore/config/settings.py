from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    environment: str
    supabase_url: str | None
    supabase_key: str | None
    supabase_service_role_key: str | None
    geot_radar_url: str | None

    @classmethod
    def from_environment(cls) -> "Settings":
        return cls(
            environment=os.getenv("BIOCORE_ENV", "development"),
            supabase_url=os.getenv("SUPABASE_URL"),
            supabase_key=os.getenv("SUPABASE_KEY"),
            supabase_service_role_key=os.getenv("SUPABASE_SERVICE_ROLE_KEY"),
            geot_radar_url=os.getenv("GEOT_RADAR_URL"),
        )
