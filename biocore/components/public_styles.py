"""Styles for the problem-oriented public BioCore experience."""


PUBLIC_STYLES = """
<style>
:root {
    --bc-forest: #12372a;
    --bc-forest-deep: #09251c;
    --bc-green: #2f7d4a;
    --bc-green-dark: #25683d;
    --bc-gold: #b58a38;
    --bc-gold-soft: #f1e4c2;
    --bc-ink: #14211b;
    --bc-muted: #596a61;
    --bc-line: #d9e4dc;
    --bc-surface: #ffffff;
    --bc-soft: #f4f7f4;
}

[data-testid="stSidebar"],
[data-testid="collapsedControl"],
[data-testid="stHeader"] {
    display: none !important;
}

.stApp {
    background: var(--bc-soft);
    color: var(--bc-ink);
}

.block-container {
    max-width: 100% !important;
    padding: 0 !important;
}

.bc-public {
    overflow: hidden;
    color: var(--bc-ink);
    font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont,
        "Segoe UI", sans-serif;
}

.bc-public *,
.bc-public *::before,
.bc-public *::after {
    box-sizing: border-box;
}

.bc-public a:focus-visible {
    outline: 3px solid #d3a43f;
    outline-offset: 4px;
}

.bc-container {
    width: min(1120px, calc(100% - 40px));
    margin: 0 auto;
}

.bc-navbar {
    position: sticky;
    top: 0;
    z-index: 20;
    border-bottom: 1px solid rgba(18, 55, 42, 0.12);
    background: rgba(255, 255, 255, 0.96);
    backdrop-filter: blur(16px);
}

.bc-navbar-inner {
    min-height: 78px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 24px;
}

.bc-brand {
    width: 210px;
    height: 60px;
    min-width: 210px;
    display: flex;
    align-items: center;
    overflow: hidden;
    border: 1px solid rgba(18, 55, 42, 0.1);
    border-radius: 12px;
    background: #fff;
}

.bc-brand img {
    width: 100%;
    height: 100%;
    padding: 5px 8px;
    object-fit: contain;
}

.bc-navlinks,
.bc-nav-actions,
.bc-hero-actions,
.bc-inline-actions,
.bc-footer-links {
    display: flex;
    align-items: center;
}

.bc-navlinks {
    flex: 1;
    justify-content: center;
    gap: 22px;
}

.bc-navlinks a,
.bc-footer-links a {
    color: var(--bc-muted);
    font-size: 0.88rem;
    font-weight: 700;
    text-decoration: none;
}

.bc-navlinks a:hover,
.bc-footer-links a:hover {
    color: var(--bc-green);
}

.bc-nav-actions,
.bc-hero-actions,
.bc-inline-actions {
    gap: 10px;
}

.bc-button {
    min-height: 44px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    padding: 0 19px;
    border-radius: 12px;
    font-size: 0.9rem;
    font-weight: 800;
    text-decoration: none !important;
    transition: transform 160ms ease, box-shadow 160ms ease, background 160ms ease;
}

.bc-button:hover {
    transform: translateY(-1px);
}

.bc-button-primary {
    background: var(--bc-green);
    color: #fff !important;
    box-shadow: 0 10px 24px rgba(47, 125, 74, 0.2);
}

.bc-button-primary:hover {
    background: var(--bc-green-dark);
}

.bc-button-secondary {
    border: 1px solid rgba(18, 55, 42, 0.24);
    background: #fff;
    color: var(--bc-forest) !important;
}

.bc-button-gold {
    border: 1px solid rgba(181, 138, 56, 0.34);
    background: var(--bc-gold-soft);
    color: var(--bc-forest-deep) !important;
}

.bc-hero {
    padding: 88px 0 72px;
    background:
        radial-gradient(circle at 82% 18%, rgba(95, 174, 100, 0.17), transparent 30%),
        linear-gradient(180deg, #fbfdfb 0%, #eef5ef 100%);
}

.bc-hero-grid {
    display: grid;
    grid-template-columns: 1.12fr 0.88fr;
    gap: 64px;
    align-items: center;
}

.bc-eyebrow {
    display: inline-flex;
    align-items: center;
    gap: 9px;
    margin-bottom: 18px;
    color: var(--bc-green);
    font-size: 0.76rem;
    font-weight: 850;
    letter-spacing: 0.1em;
    text-transform: uppercase;
}

.bc-eyebrow::before {
    content: "";
    width: 28px;
    height: 2px;
    background: var(--bc-gold);
}

.bc-hero h1 {
    max-width: 760px;
    margin: 0 0 22px;
    color: var(--bc-forest-deep);
    font-size: clamp(2.65rem, 5.2vw, 4.8rem);
    line-height: 1.02;
    letter-spacing: -0.055em;
}

.bc-hero-copy {
    max-width: 690px;
    margin: 0 0 18px;
    color: var(--bc-muted);
    font-size: clamp(1.04rem, 2vw, 1.2rem);
    line-height: 1.7;
}

.bc-hero-specialty {
    max-width: 680px;
    margin: 0 0 28px;
    color: var(--bc-forest);
    font-weight: 800;
    line-height: 1.55;
}

.bc-hero-actions {
    flex-wrap: wrap;
}

.bc-action-note {
    margin: 13px 0 0;
    color: #6c7b73;
    font-size: 0.76rem;
}

.bc-hero-summary {
    padding: 34px;
    border: 1px solid rgba(18, 55, 42, 0.14);
    border-radius: 24px;
    background: rgba(255, 255, 255, 0.88);
    box-shadow: 0 26px 65px rgba(9, 37, 28, 0.12);
}

.bc-summary-label {
    display: inline-flex;
    padding: 6px 10px;
    border-radius: 999px;
    background: #eaf4ec;
    color: var(--bc-green-dark);
    font-size: 0.72rem;
    font-weight: 850;
}

.bc-hero-summary h2 {
    margin: 18px 0;
    color: var(--bc-forest-deep);
    font-size: clamp(1.65rem, 3vw, 2.2rem);
    line-height: 1.15;
}

.bc-hero-summary ul {
    display: grid;
    gap: 12px;
    margin: 0;
    padding: 0;
    list-style: none;
}

.bc-hero-summary li {
    position: relative;
    padding-left: 25px;
    color: #42564c;
    line-height: 1.45;
}

.bc-hero-summary li::before {
    content: "✓";
    position: absolute;
    left: 0;
    color: var(--bc-green);
    font-weight: 900;
}

.bc-hero-summary > p {
    margin: 22px 0 0;
    padding-top: 18px;
    border-top: 1px solid var(--bc-line);
    color: #65766d;
    font-size: 0.78rem;
    line-height: 1.55;
}

.bc-scope {
    border-top: 1px solid rgba(18, 55, 42, 0.08);
    border-bottom: 1px solid rgba(18, 55, 42, 0.1);
    background: #fff;
}

.bc-scope-inner {
    min-height: 74px;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-wrap: wrap;
    gap: 10px;
}

.bc-scope-inner strong {
    margin-right: 6px;
    color: var(--bc-forest);
    font-size: 0.84rem;
}

.bc-scope-inner span {
    padding: 7px 11px;
    border: 1px solid var(--bc-line);
    border-radius: 999px;
    background: var(--bc-soft);
    color: #506158;
    font-size: 0.76rem;
    font-weight: 700;
}

.bc-section {
    padding: 86px 0;
    background: #fff;
}

.bc-section-soft {
    background: var(--bc-soft);
}

.bc-section-dark {
    background:
        radial-gradient(circle at 85% 0%, rgba(95, 174, 100, 0.18), transparent 32%),
        var(--bc-forest-deep);
    color: #fff;
}

.bc-section-head {
    max-width: 780px;
    margin: 0 auto 42px;
    text-align: center;
}

.bc-section-head-left {
    margin-left: 0;
    text-align: left;
}

.bc-section-head h2,
.bc-audience-layout h2,
.bc-service-layout h2,
.bc-diagnostic h2 {
    margin: 4px 0 16px;
    color: var(--bc-forest-deep);
    font-size: clamp(2rem, 4vw, 3.2rem);
    line-height: 1.12;
    letter-spacing: -0.04em;
}

.bc-section-head p,
.bc-audience-layout p,
.bc-service-layout p,
.bc-diagnostic p {
    margin: 0;
    color: var(--bc-muted);
    font-size: 1.02rem;
    line-height: 1.7;
}

.bc-outcomes {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 18px;
}

.bc-outcome {
    padding: 28px;
    border-top: 4px solid var(--bc-green);
    border-right: 1px solid var(--bc-line);
    border-bottom: 1px solid var(--bc-line);
    border-left: 1px solid var(--bc-line);
    border-radius: 18px;
    background: #fff;
}

.bc-outcome h3,
.bc-tool h3,
.bc-next-actions h3,
.bc-stage h3 {
    margin: 0 0 9px;
    color: var(--bc-forest);
}

.bc-outcome p,
.bc-tool p,
.bc-next-actions p,
.bc-stage p {
    margin: 0;
    color: var(--bc-muted);
    line-height: 1.62;
}

.bc-project-flow {
    display: grid;
    grid-template-columns: repeat(7, 1fr);
    gap: 12px;
    margin: 0;
    padding: 0;
    list-style: none;
}

.bc-stage {
    min-width: 0;
    padding: 20px 16px;
    border: 1px solid var(--bc-line);
    border-radius: 16px;
    background: #fff;
}

.bc-stage > span {
    display: inline-grid;
    width: 34px;
    height: 34px;
    place-items: center;
    margin-bottom: 18px;
    border-radius: 50%;
    background: var(--bc-forest);
    color: #fff;
    font-size: 0.7rem;
    font-weight: 850;
}

.bc-stage h3 {
    font-size: 0.92rem;
}

.bc-stage p {
    font-size: 0.76rem;
}

.bc-audience-layout,
.bc-service-layout,
.bc-diagnostic {
    display: grid;
    grid-template-columns: 0.95fr 1.05fr;
    gap: 64px;
    align-items: center;
}

.bc-audience-list {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 12px;
    margin: 0;
    padding: 0;
    list-style: none;
}

.bc-audience-list li {
    display: flex;
    align-items: center;
    gap: 11px;
    min-height: 58px;
    padding: 14px 16px;
    border: 1px solid var(--bc-line);
    border-radius: 14px;
    background: var(--bc-soft);
    color: #40534a;
    font-weight: 720;
}

.bc-audience-list span {
    color: var(--bc-green);
    font-weight: 900;
}

.bc-section-dark .bc-eyebrow {
    color: #d8bf80;
}

.bc-section-dark h2,
.bc-section-dark p {
    color: #fff;
}

.bc-section-dark p {
    opacity: 0.78;
}

.bc-service-actions {
    display: grid;
    justify-items: start;
    gap: 14px;
    padding: 28px;
    border: 1px solid rgba(255, 255, 255, 0.14);
    border-radius: 18px;
    background: rgba(255, 255, 255, 0.06);
}

.bc-service-actions small {
    max-width: 520px;
    color: rgba(255, 255, 255, 0.7);
    line-height: 1.55;
}

.bc-tools {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 15px;
}

.bc-tool {
    position: relative;
    display: grid;
    grid-template-columns: 64px 1fr;
    gap: 16px;
    padding: 20px;
    border: 1px solid var(--bc-line);
    border-radius: 16px;
    background: #fff;
}

.bc-tool:last-child {
    grid-column: 1 / -1;
}

.bc-tool img {
    width: 64px;
    height: 64px;
    border: 1px solid var(--bc-line);
    border-radius: 14px;
    object-fit: contain;
}

.bc-tool h3 {
    font-size: 1rem;
}

.bc-tool p {
    margin-bottom: 10px;
    font-size: 0.84rem;
}

.bc-tool a,
.bc-text-link {
    color: var(--bc-green-dark);
    font-size: 0.82rem;
    font-weight: 850;
    text-decoration: none;
}

.bc-tool a::after {
    content: "";
    position: absolute;
    inset: 0;
}

.bc-diagnostic {
    padding: 38px;
    border: 1px solid rgba(47, 125, 74, 0.24);
    border-radius: 24px;
    background: linear-gradient(145deg, #f7fbf8, #edf6ef);
}

.bc-diagnostic .bc-disclaimer {
    margin-top: 16px;
    color: #596b61;
    font-size: 0.8rem;
}

.bc-next-actions {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 18px;
}

.bc-next-actions article {
    padding: 30px;
    border: 1px solid var(--bc-line);
    border-radius: 18px;
    background: #fff;
}

.bc-next-actions p {
    margin-bottom: 22px;
}

.bc-inline-actions {
    flex-wrap: wrap;
}

.bc-footer {
    padding: 48px 0 26px;
    background: #061c15;
    color: rgba(255, 255, 255, 0.72);
}

.bc-footer-inner {
    display: grid;
    grid-template-columns: 220px 1fr auto;
    gap: 32px;
    align-items: center;
}

.bc-footer img {
    width: 210px;
    height: 60px;
    padding: 5px 8px;
    border-radius: 12px;
    background: #fff;
    object-fit: contain;
}

.bc-footer p {
    max-width: 470px;
    margin: 0;
    line-height: 1.6;
}

.bc-footer-links {
    justify-content: flex-end;
    flex-wrap: wrap;
    gap: 16px;
}

.bc-footer-links a {
    color: rgba(255, 255, 255, 0.78);
}

.bc-footer-bottom {
    margin-top: 28px;
    padding-top: 20px;
    border-top: 1px solid rgba(255, 255, 255, 0.1);
    font-size: 0.76rem;
}

@media (max-width: 1060px) {
    .bc-navlinks { display: none; }
    .bc-project-flow { grid-template-columns: repeat(4, 1fr); }
}

@media (max-width: 820px) {
    .bc-hero { padding: 66px 0 58px; }
    .bc-hero-grid,
    .bc-audience-layout,
    .bc-service-layout,
    .bc-diagnostic { grid-template-columns: 1fr; gap: 34px; }
    .bc-outcomes { grid-template-columns: 1fr; }
    .bc-project-flow { grid-template-columns: repeat(2, 1fr); }
    .bc-footer-inner { grid-template-columns: 1fr; }
    .bc-footer-links { justify-content: flex-start; }
}

@media (max-width: 620px) {
    .bc-container { width: min(100% - 24px, 1120px); }
    .bc-navbar-inner { min-height: 70px; gap: 10px; }
    .bc-brand { width: 154px; min-width: 154px; height: 50px; }
    .bc-nav-actions .bc-button-primary { display: none; }
    .bc-button { min-height: 42px; padding: 0 14px; }
    .bc-hero h1 { font-size: 2.45rem; }
    .bc-hero-summary { padding: 24px; }
    .bc-section { padding: 64px 0; }
    .bc-scope-inner { justify-content: flex-start; padding: 16px 0; }
    .bc-project-flow,
    .bc-audience-list,
    .bc-tools,
    .bc-next-actions { grid-template-columns: 1fr; }
    .bc-tool:last-child { grid-column: auto; }
    .bc-diagnostic { padding: 26px; }
    .bc-footer img { width: 190px; }
}
</style>
"""
