from pathlib import Path


def test_public_landing_exposes_central_account_cta() -> None:
    source = Path("biocore/components/public_landing.py").read_text(
        encoding="utf-8"
    )
    assert "Crear cuenta" in source
    assert "BIOCORE_AUTH_LOGIN_URL" in Path(
        "biocore/config/settings.py"
    ).read_text(encoding="utf-8")


def test_legacy_admin_password_is_not_hardcoded() -> None:
    source = Path("app.py").read_text(encoding="utf-8")
    admin_function = source.split("def es_admin", maxsplit=1)[1].split(
        "# === FUNCIÓN DE MAPA", maxsplit=1
    )[0]
    assert "pbkdf2_hmac" in admin_function
    assert "compare_digest" in admin_function
    assert "== \"" not in admin_function
