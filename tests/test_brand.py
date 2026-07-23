from biocore.config.brand import BRAND


def test_official_brand_assets_are_available() -> None:
    assert BRAND.master_logo.is_file()
    assert BRAND.field_logo.is_file()
    assert BRAND.reports_logo.is_file()
    assert BRAND.academy_logo.is_file()


def test_brand_message_matches_official_identity() -> None:
    assert BRAND.name == "BioCore"
    assert BRAND.descriptor == "Empresa de base científico-tecnológica"
    assert BRAND.slogan == "Transformamos datos en inteligencia ecológica"
