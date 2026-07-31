from pathlib import Path


def test_private_header_has_a_shared_semantic_wrapper() -> None:
    component = Path("biocore/components/page_header.py").read_text(
        encoding="utf-8"
    )
    assert '<header class="bc-page-header">' in component
    assert '<h1 class="bc-page-title">' in component


def test_private_header_stays_below_streamlit_toolbar_and_keeps_contrast() -> None:
    styles = Path("biocore/components/styles.py").read_text(encoding="utf-8")
    private_styles = styles.split('PRIVATE_STYLES = """', maxsplit=1)[1]
    assert "padding-top: 5.5rem !important;" in private_styles
    assert (
        '[data-testid="stAppViewContainer"] .bc-page-title'
        in private_styles
    )
    assert "color: #10231a !important;" in private_styles


def test_compact_sidebar_logo_is_cropped_without_distortion() -> None:
    styles = Path("biocore/components/styles.py").read_text(encoding="utf-8")
    private_styles = styles.split('PRIVATE_STYLES = """', maxsplit=1)[1]
    logo_rule = private_styles.split(
        '[data-testid="stSidebarLogo"] {', maxsplit=1
    )[1].split("}", maxsplit=1)[0]
    assert "height: 70px !important;" in logo_rule
    assert "object-fit: cover !important;" in logo_rule
    assert "object-position: center top !important;" in logo_rule


def test_private_streamlit_subheaders_keep_contrast() -> None:
    styles = Path("biocore/components/styles.py").read_text(encoding="utf-8")
    private_styles = styles.split('PRIVATE_STYLES = """', maxsplit=1)[1]

    assert '[data-testid="stMain"] h2' in private_styles
    assert '[data-testid="stMain"] h3' in private_styles
    assert "color: #173a2b !important;" in private_styles


def test_light_cards_inside_dark_sections_keep_readable_text() -> None:
    styles = Path("biocore/components/styles.py").read_text(encoding="utf-8")
    assert ".bc-section-dark .bc-panel {" in styles
    assert ".bc-section-dark .bc-panel h2," in styles
    assert ".bc-section-dark .bc-panel p," in styles
    assert "color: var(--bc-muted);" in styles


def test_public_diagnostic_owns_a_light_background() -> None:
    source = Path(
        "biocore/components/public_ecological_diagnostic.py"
    ).read_text(encoding="utf-8")
    assert '[data-testid="stAppViewContainer"]' in source
    assert '[data-testid="stMainBlockContainer"]' in source
    assert "background: #f5f8f5 !important;" in source
