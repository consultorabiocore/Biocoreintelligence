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
    styles = Path("biocore/components/public_styles.py").read_text(
        encoding="utf-8"
    )
    assert ".bc-section-dark h2," in styles
    assert ".bc-section-dark p" in styles
    assert "color: #fff;" in styles
    assert ".bc-service-actions small" in styles


def test_public_landing_supports_keyboard_and_mobile_navigation() -> None:
    styles = Path("biocore/components/public_styles.py").read_text(
        encoding="utf-8"
    )
    assert ".bc-public a:focus-visible" in styles
    assert "outline: 3px solid" in styles
    assert "@media (max-width: 620px)" in styles
    assert ".bc-project-flow" in styles


def test_specialized_product_cards_remain_readable_and_responsive() -> None:
    styles = Path("biocore/components/public_styles.py").read_text(
        encoding="utf-8"
    )
    assert ".bc-tool-spotlight" in styles
    assert ".bc-tool-features" in styles
    assert ".bc-tool-note" in styles
    assert ".bc-tool-actions" in styles
    assert ".bc-tool-reference" in styles


def test_private_home_has_guidance_and_project_progress_styles() -> None:
    styles = Path("biocore/components/styles.py").read_text(encoding="utf-8")
    private_styles = styles.split('PRIVATE_STYLES = """', maxsplit=1)[1]
    assert ".bc-guidance-card" in private_styles
    assert ".bc-project-overview" in private_styles
    assert ".bc-project-progress" in private_styles


def test_public_diagnostic_owns_a_light_background() -> None:
    source = Path(
        "biocore/components/public_ecological_diagnostic.py"
    ).read_text(encoding="utf-8")
    assert '[data-testid="stAppViewContainer"]' in source
    assert '[data-testid="stMainBlockContainer"]' in source
    assert "background: #f5f8f5 !important;" in source
