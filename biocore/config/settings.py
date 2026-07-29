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
    auth_mode: str = "shadow"
    auth_api_url: str | None = None
    auth_login_url: str | None = None
    auth_cookie_name: str = "biocore_session"
    auth_cookie_secure: bool = True
    auth_session_hours: int = 8
    auth_module_session_hours: int = 2
    auth_launch_minutes: int = 2
    oidc_provider: str = "supabase"
    oidc_issuer: str | None = None
    oidc_audience: str | None = None
    oidc_jwks_url: str | None = None
    auth_allowed_redirect_hosts: frozenset[str] = frozenset()

    @classmethod
    def from_environment(cls) -> "Settings":
        allowed_hosts = frozenset(
            item.strip().lower()
            for item in os.getenv("BIOCORE_AUTH_ALLOWED_REDIRECT_HOSTS", "").split(",")
            if item.strip()
        )
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
            auth_mode=os.getenv("BIOCORE_AUTH_MODE", "shadow").strip().lower(),
            auth_api_url=os.getenv("BIOCORE_AUTH_API_URL"),
            auth_login_url=os.getenv("BIOCORE_AUTH_LOGIN_URL"),
            auth_cookie_name=os.getenv(
                "BIOCORE_AUTH_COOKIE_NAME", "biocore_session"
            ),
            auth_cookie_secure=(
                os.getenv("BIOCORE_AUTH_COOKIE_SECURE", "true").strip().lower()
                != "false"
            ),
            auth_session_hours=int(os.getenv("BIOCORE_AUTH_SESSION_HOURS", "8")),
            auth_module_session_hours=int(
                os.getenv("BIOCORE_AUTH_MODULE_SESSION_HOURS", "2")
            ),
            auth_launch_minutes=int(
                os.getenv("BIOCORE_AUTH_LAUNCH_MINUTES", "2")
            ),
            oidc_provider=os.getenv("BIOCORE_OIDC_PROVIDER", "supabase"),
            oidc_issuer=os.getenv("BIOCORE_OIDC_ISSUER"),
            oidc_audience=os.getenv("BIOCORE_OIDC_AUDIENCE"),
            oidc_jwks_url=os.getenv("BIOCORE_OIDC_JWKS_URL"),
            auth_allowed_redirect_hosts=allowed_hosts,
        )
