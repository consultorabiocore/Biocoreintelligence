from biocore.config.integrations import (
    external_applications,
    normalize_external_url,
)
from biocore.config.settings import Settings


def _settings(**overrides: str | None) -> Settings:
    values: dict[str, str | None] = {
        "environment": "test",
        "supabase_url": None,
        "supabase_key": None,
        "supabase_service_role_key": None,
        "field_url": None,
        "darwincheck_url": None,
        "geot_radar_url": None,
    }
    values.update(overrides)
    return Settings(**values)


def test_external_application_urls_can_be_configured_without_secrets_in_code() -> None:
    catalog = external_applications(
        _settings(field_url="https://field.example.com"),
        {"darwincheck_url": "https://check.example.com"},
    )

    assert catalog["field"].url == "https://field.example.com"
    assert catalog["darwincheck"].url == "https://check.example.com"
    assert catalog["field"].is_configured
    assert catalog["darwincheck"].is_configured


def test_secret_configuration_overrides_environment_url() -> None:
    catalog = external_applications(
        _settings(field_url="https://old.example.com"),
        {"field_url": "https://new.example.com"},
    )
    assert catalog["field"].url == "https://new.example.com"


def test_external_urls_fail_closed_when_scheme_is_not_http() -> None:
    assert normalize_external_url("javascript:alert(1)") is None
    assert normalize_external_url("not-a-url") is None
    assert normalize_external_url("https://field.example.com") == (
        "https://field.example.com"
    )


def test_radar_tool_is_not_presented_as_lidar() -> None:
    radar = external_applications(
        _settings(
            geot_radar_url="https://nibaldox.github.io/GeotRadarSim/"
        )
    )["geot_radar"]

    assert "radar" in radar.label.lower()
    assert "no corresponde a LiDAR" in radar.description
