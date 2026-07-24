from pathlib import Path

from biocore.config.brand import (
    BIOCORE_BACKGROUND,
    BIOCORE_BLUE,
    BIOCORE_GOLD,
    BIOCORE_GREEN,
    BIOCORE_GREEN_DARK,
    BIOCORE_TEXT,
    BRAND,
    asset_data_uri,
    available_logo,
)


def test_official_brand_assets_are_available() -> None:
    assert BRAND.master_logo.is_file()
    assert BRAND.darwincheck_logo.is_file()
    assert BRAND.intelligence_logo.is_file()
    assert BRAND.field_logo.is_file()
    assert BRAND.reports_logo.is_file()
    assert BRAND.academy_logo.is_file()


def test_brand_message_matches_official_identity() -> None:
    assert BRAND.name == "BioCore"
    assert BRAND.descriptor == "Plataforma de inteligencia ecológica"
    assert BRAND.slogan == "Transformamos datos en inteligencia ecológica"


def test_brand_palette_matches_approved_tokens() -> None:
    assert BIOCORE_GREEN_DARK == "#12372A"
    assert BIOCORE_GREEN == "#2F7D4A"
    assert BIOCORE_GOLD == "#B58A38"
    assert BIOCORE_BLUE == "#176B87"
    assert BIOCORE_TEXT == "#14211B"
    assert BIOCORE_BACKGROUND == "#F4F7F4"


def test_missing_logo_uses_controlled_fallback(tmp_path: Path) -> None:
    missing = tmp_path / "missing.png"
    fallback = tmp_path / "fallback.png"
    fallback.write_bytes(b"brand")
    assert available_logo(missing, fallback) == fallback
    assert asset_data_uri(missing, fallback).startswith("data:image/png;base64,")
    assert available_logo(missing) is None
    assert asset_data_uri(missing) == ""
