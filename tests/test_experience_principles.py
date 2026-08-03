from pathlib import Path


def test_human_experience_principles_are_part_of_architecture() -> None:
    principles = Path("docs/human_experience_principles.md").read_text(
        encoding="utf-8"
    )
    architecture = Path("docs/platform_architecture.md").read_text(
        encoding="utf-8"
    )

    for requirement in (
        "Rigor científico",
        "Experiencia humana",
        "Contrato de explicabilidad",
        "Principio de orientación al problema",
        "dato observado",
        "dato calculado",
        "inferencia",
        "incertidumbre",
        "siguiente acción recomendada",
        "Regla de oro",
    ):
        assert requirement in principles

    assert "human_experience_principles.md" in architecture


def test_public_diagnostic_cta_is_in_flow_not_a_fixed_overlay() -> None:
    gateway = Path(
        "biocore/components/public_landing_gateway.py"
    ).read_text(encoding="utf-8")
    landing = Path("biocore/components/public_landing.py").read_text(
        encoding="utf-8"
    )

    assert "bc-public-diagnostic-fab" not in gateway
    assert 'diagnostic_url = "?diagnostico=publico"' in landing
    assert "Realizar diagnóstico ecológico" in landing
