from pathlib import Path


def test_ecological_evidence_page_uses_service_layer_and_explains_provenance() -> None:
    page = Path("platform_pages/ecological_evidence.py").read_text(encoding="utf-8")

    assert "biocore_ecological_evidence_service" in page
    assert ".table(" not in page
    assert "Registro BioCore" in page
    assert "Registro externo" in page
    assert "Importar desde iNaturalist" in page
    assert "no se copian" in page
    assert "Solicitar revisión profesional" in page
    assert "Mapa básico de evidencias" in page
    assert "no representan por sí solos riqueza" in page
    assert "-36.82" not in page
    assert "-73.03" not in page


def test_private_styles_cover_headings_labels_tabs_and_inputs() -> None:
    styles = Path("biocore/components/styles.py").read_text(encoding="utf-8")

    assert '[data-testid="stMain"] h1' in styles
    assert '[data-testid="stWidgetLabel"] p' in styles
    assert '[data-baseweb="tab-list"] button' in styles
    assert '[data-testid="stMain"] input' in styles
    assert '#173a2b !important' in styles


def test_project_portada_links_to_ecological_evidence() -> None:
    projects = Path("platform_pages/projects.py").read_text(encoding="utf-8")

    assert 'evidence.button("Evidencias ecológicas"' in projects
    assert 'st.switch_page("platform_pages/ecological_evidence.py")' in projects
