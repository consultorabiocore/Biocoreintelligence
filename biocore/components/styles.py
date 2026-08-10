PUBLIC_STYLES = """
<style>
:root {
    --bc-forest: #12372a;
    --bc-forest-deep: #09251c;
    --bc-green: #2f7d4a;
    --bc-green-bright: #5fae64;
    --bc-gold: #b58a38;
    --bc-gold-soft: #e9d8ad;
    --bc-ink: #14211b;
    --bc-muted: #607068;
    --bc-line: #dfe7e1;
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
    font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont,
        "Segoe UI", sans-serif;
    overflow: hidden;
}

.bc-public *,
.bc-public *::before,
.bc-public *::after {
    box-sizing: border-box;
}

.bc-container {
    width: min(1180px, calc(100% - 40px));
    margin: 0 auto;
}

.bc-navbar {
    position: sticky;
    top: 0;
    z-index: 10;
    background: rgba(255, 255, 255, 0.94);
    backdrop-filter: blur(18px);
    border-bottom: 1px solid rgba(18, 55, 42, 0.1);
}

.bc-navbar-inner {
    min-height: 82px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 24px;
}

.bc-brand {
    display: flex;
    align-items: center;
    width: 235px;
    height: 68px;
    min-width: 235px;
    overflow: hidden;
    border: 1px solid rgba(18, 55, 42, 0.1);
    border-radius: 12px;
    background: #ffffff;
}

.bc-brand img {
    width: 100%;
    height: 100%;
    max-height: none;
    padding: 5px 8px;
    object-fit: contain;
    object-position: center;
}

.bc-navlinks {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 22px;
    flex: 1;
}

.bc-navlinks a,
.bc-footer a {
    color: var(--bc-muted);
    text-decoration: none;
    font-size: 0.9rem;
    font-weight: 650;
}

.bc-navlinks a:hover,
.bc-footer a:hover {
    color: var(--bc-green);
}

.bc-nav-actions {
    display: flex;
    gap: 10px;
    align-items: center;
}

.bc-button {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-height: 44px;
    padding: 0 20px;
    border-radius: 12px;
    text-decoration: none !important;
    font-size: 0.9rem;
    font-weight: 750;
    transition: transform 160ms ease, box-shadow 160ms ease, background 160ms ease;
}

.bc-button:hover {
    transform: translateY(-1px);
}

.bc-button-primary {
    color: white !important;
    background: var(--bc-green);
    box-shadow: 0 10px 24px rgba(47, 125, 74, 0.2);
}

.bc-button-primary:hover {
    background: #25683d;
}

.bc-button-secondary {
    color: var(--bc-forest) !important;
    background: white;
    border: 1px solid rgba(18, 55, 42, 0.22);
}

.bc-button-gold {
    color: var(--bc-forest-deep) !important;
    background: var(--bc-gold-soft);
    border: 1px solid rgba(181, 138, 56, 0.3);
}

.bc-hero {
    position: relative;
    padding: 92px 0 78px;
    background:
        radial-gradient(circle at 75% 18%, rgba(95, 174, 100, 0.15), transparent 30%),
        linear-gradient(180deg, #fbfdfb 0%, #f1f6f2 100%);
}

.bc-hero::after {
    content: "";
    position: absolute;
    inset: auto 0 0;
    height: 1px;
    background: linear-gradient(90deg, transparent, rgba(18, 55, 42, 0.18), transparent);
}

.bc-hero-grid {
    display: grid;
    grid-template-columns: 1.02fr 0.98fr;
    gap: 56px;
    align-items: center;
}

.bc-eyebrow {
    display: inline-flex;
    align-items: center;
    gap: 9px;
    margin-bottom: 22px;
    color: var(--bc-green);
    font-size: 0.78rem;
    font-weight: 800;
    letter-spacing: 0.11em;
    text-transform: uppercase;
}

.bc-eyebrow::before {
    content: "";
    width: 28px;
    height: 2px;
    background: var(--bc-gold);
}

.bc-hero h1 {
    max-width: 720px;
    margin: 0 0 24px;
    color: var(--bc-forest-deep);
    font-size: clamp(2.65rem, 5vw, 4.75rem);
    line-height: 1.02;
    letter-spacing: -0.055em;
}

.bc-hero-copy {
    max-width: 650px;
    margin: 0 0 30px;
    color: var(--bc-muted);
    font-size: clamp(1.03rem, 2vw, 1.2rem);
    line-height: 1.7;
}

.bc-hero-note {
    margin: -14px 0 28px;
    color: var(--bc-forest);
    font-size: .92rem;
    font-weight: 720;
}

.bc-hero-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
    margin-bottom: 34px;
}

.bc-trust-row {
    display: flex;
    flex-wrap: wrap;
    gap: 18px;
    color: #51625a;
    font-size: 0.83rem;
    font-weight: 650;
}

.bc-trust-row span::before {
    content: "✓";
    margin-right: 7px;
    color: var(--bc-green);
}

.bc-demo-contact-note {
    max-width: 620px;
    margin: 16px 0 0;
    color: #65766d;
    font-size: .78rem;
    line-height: 1.5;
}

.bc-hero-ecosystem {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 28px;
    margin-top: 42px;
    padding: 18px 22px;
    border: 1px solid rgba(18, 55, 42, 0.1);
    border-radius: 18px;
    background: rgba(255, 255, 255, 0.78);
    box-shadow: 0 14px 34px rgba(18, 55, 42, 0.06);
}

.bc-hero-ecosystem > strong {
    max-width: 210px;
    color: var(--bc-forest);
    font-size: .82rem;
    line-height: 1.45;
}

.bc-ecosystem-brands {
    display: flex;
    flex: 1;
    align-items: center;
    justify-content: flex-end;
    gap: 12px;
}

.bc-ecosystem-brand {
    display: flex;
    min-width: 0;
    align-items: center;
    gap: 8px;
    color: var(--bc-forest);
}

.bc-ecosystem-brand img {
    width: 46px;
    height: 46px;
    flex: 0 0 46px;
    border: 1px solid var(--bc-line);
    border-radius: 12px;
    background: #fff;
    object-fit: contain;
}

.bc-ecosystem-brand small {
    max-width: 90px;
    color: #52635a;
    font-size: .66rem;
    font-weight: 750;
    line-height: 1.25;
}

.bc-demo-shell {
    position: relative;
    padding: 15px;
    border: 1px solid rgba(18, 55, 42, 0.12);
    border-radius: 24px;
    background: rgba(255, 255, 255, 0.82);
    box-shadow: 0 32px 80px rgba(9, 37, 28, 0.16);
}

.bc-demo-window {
    overflow: hidden;
    border-radius: 17px;
    background: var(--bc-forest-deep);
    color: white;
}

.bc-demo-topbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 13px 16px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
    color: rgba(255, 255, 255, 0.72);
    font-size: 0.73rem;
}

.bc-demo-badge {
    padding: 5px 9px;
    border-radius: 999px;
    background: rgba(233, 216, 173, 0.14);
    color: #f2dfad;
    font-weight: 750;
}

.bc-demo-body {
    display: grid;
    grid-template-columns: 1.35fr 0.65fr;
    min-height: 370px;
}

.bc-demo-map {
    position: relative;
    min-height: 370px;
    background:
        radial-gradient(circle at 32% 40%, rgba(93, 175, 102, 0.7) 0 4%, transparent 4.5%),
        radial-gradient(circle at 66% 58%, rgba(233, 216, 173, 0.8) 0 3%, transparent 3.5%),
        linear-gradient(145deg, transparent 46%, rgba(233, 216, 173, 0.45) 47% 48%, transparent 49%),
        repeating-linear-gradient(25deg, rgba(255,255,255,.04) 0 1px, transparent 1px 32px),
        repeating-linear-gradient(115deg, rgba(255,255,255,.035) 0 1px, transparent 1px 28px),
        linear-gradient(145deg, #163f30, #0d2b21);
}

.bc-map-zone {
    position: absolute;
    left: 17%;
    top: 20%;
    width: 58%;
    height: 56%;
    border: 2px solid #d9bd73;
    border-radius: 48% 38% 50% 42%;
    background: rgba(181, 138, 56, 0.12);
    transform: rotate(-8deg);
}

.bc-map-legend {
    position: absolute;
    left: 16px;
    bottom: 16px;
    padding: 10px 12px;
    border-radius: 10px;
    background: rgba(7, 29, 22, 0.8);
    color: rgba(255,255,255,.74);
    font-size: 0.68rem;
    line-height: 1.7;
}

.bc-demo-panel {
    display: flex;
    flex-direction: column;
    gap: 10px;
    padding: 14px;
    background: rgba(255, 255, 255, 0.04);
}

.bc-demo-metric {
    padding: 12px;
    border: 1px solid rgba(255,255,255,.08);
    border-radius: 11px;
    background: rgba(255,255,255,.04);
}

.bc-demo-metric small {
    display: block;
    color: rgba(255,255,255,.58);
    font-size: 0.65rem;
}

.bc-demo-metric strong {
    display: block;
    margin-top: 3px;
    color: white;
    font-size: 1.18rem;
}

.bc-demo-comparison {
    display: grid;
    grid-template-columns: auto 1fr auto 1fr auto;
    gap: 6px;
    align-items: center;
    padding: 9px 6px 2px;
    color: rgba(255,255,255,.62);
    font-size: .62rem;
    text-align: center;
}

.bc-demo-comparison i {
    height: 2px;
    border-radius: 999px;
    background: linear-gradient(90deg, var(--bc-green-bright), var(--bc-gold));
}

.bc-demo-comparison strong {
    color: white;
    font-size: .65rem;
}

.bc-section {
    padding: 92px 0;
    background: white;
}

.bc-section-soft {
    background: var(--bc-soft);
}

.bc-section-dark {
    background:
        radial-gradient(circle at 80% 0%, rgba(95,174,100,.18), transparent 30%),
        var(--bc-forest-deep);
    color: white;
}

.bc-section-head {
    max-width: 760px;
    margin: 0 auto 48px;
    text-align: center;
}

.bc-section-head h2 {
    margin: 8px 0 16px;
    color: var(--bc-forest-deep);
    font-size: clamp(2rem, 4vw, 3.2rem);
    line-height: 1.12;
    letter-spacing: -0.04em;
}

.bc-section-dark .bc-section-head h2,
.bc-section-dark h2,
.bc-section-dark h3 {
    color: white;
}

.bc-section-head p {
    margin: 0;
    color: var(--bc-muted);
    font-size: 1.04rem;
    line-height: 1.7;
}

.bc-section-dark .bc-section-head p {
    color: rgba(255,255,255,.68);
}

.bc-split {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 22px;
}

.bc-panel {
    padding: 32px;
    border: 1px solid var(--bc-line);
    border-radius: 20px;
    background: white;
}

.bc-panel h3 {
    margin: 0 0 12px;
    color: var(--bc-forest);
    font-size: 1.25rem;
}

.bc-section-dark .bc-panel {
    color: var(--bc-ink);
}

.bc-section-dark .bc-panel h2,
.bc-section-dark .bc-panel h3,
.bc-section-dark .bc-panel h4 {
    color: var(--bc-forest) !important;
    -webkit-text-fill-color: var(--bc-forest) !important;
}

.bc-section-dark .bc-panel p,
.bc-section-dark .bc-panel li {
    color: #46594f !important;
    -webkit-text-fill-color: #46594f !important;
    opacity: 1 !important;
}

.bc-section-dark .bc-panel small {
    color: #52665d !important;
    -webkit-text-fill-color: #52665d !important;
    opacity: 1 !important;
}

.bc-list {
    display: grid;
    gap: 11px;
    margin: 20px 0 0;
    padding: 0;
    list-style: none;
}

.bc-list li {
    position: relative;
    padding-left: 24px;
    color: var(--bc-muted);
    line-height: 1.5;
}

.bc-list li::before {
    content: "•";
    position: absolute;
    left: 6px;
    color: var(--bc-gold);
    font-weight: 900;
}

.bc-solution-panel {
    border-color: rgba(47,125,74,.28);
    background: linear-gradient(145deg, #f7fbf8, #edf6ef);
}

.bc-card-grid {
    display: grid;
    grid-template-columns: repeat(5, 1fr);
    gap: 15px;
}

.bc-module-card,
.bc-benefit-card {
    position: relative;
    padding: 24px 20px;
    border: 1px solid var(--bc-line);
    border-radius: 18px;
    background: white;
    transition: transform 160ms ease, box-shadow 160ms ease, border-color 160ms ease;
}

.bc-module-card:hover,
.bc-benefit-card:hover {
    transform: translateY(-3px);
    border-color: rgba(47,125,74,.3);
    box-shadow: 0 18px 38px rgba(18,55,42,.08);
}

.bc-module-icon {
    display: inline-grid;
    place-items: center;
    width: 44px;
    height: 44px;
    margin-bottom: 18px;
    border-radius: 13px;
    background: #edf6ef;
    color: var(--bc-green);
    font-size: 1.1rem;
    font-weight: 850;
}

.bc-module-logo {
    display: block;
    width: 76px;
    height: 76px;
    margin-bottom: 18px;
    border: 1px solid var(--bc-line);
    border-radius: 16px;
    background: #fff;
    object-fit: contain;
}

.bc-module-card h3,
.bc-benefit-card h3 {
    margin: 0 0 10px;
    color: var(--bc-forest);
    font-size: 1.02rem;
}

.bc-module-card p,
.bc-benefit-card p {
    min-height: 68px;
    margin: 0 0 16px;
    color: var(--bc-muted);
    font-size: 0.88rem;
    line-height: 1.55;
}

.bc-text-link {
    color: var(--bc-green);
    text-decoration: none;
    font-size: 0.84rem;
    font-weight: 800;
}

.bc-module-card .bc-text-link::after {
    content: "";
    position: absolute;
    inset: 0;
}

.bc-flow {
    display: grid;
    grid-template-columns: repeat(9, 1fr);
    gap: 8px;
    align-items: center;
}

.bc-flow-step {
    position: relative;
    min-height: 92px;
    display: grid;
    place-items: center;
    padding: 14px 8px;
    border: 1px solid rgba(255,255,255,.12);
    border-radius: 14px;
    background: rgba(255,255,255,.055);
    color: white;
    text-align: center;
    font-size: 0.78rem;
    font-weight: 750;
}

.bc-flow-step:not(:last-child)::after {
    content: "→";
    position: absolute;
    right: -10px;
    z-index: 2;
    color: var(--bc-gold-soft);
}

.bc-benefits-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 16px;
}

.bc-benefit-card p {
    min-height: auto;
    margin-bottom: 0;
}

.bc-plans {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 20px;
    align-items: stretch;
}

.bc-plan {
    position: relative;
    display: flex;
    flex-direction: column;
    padding: 30px;
    border: 1px solid var(--bc-line);
    border-radius: 22px;
    background: white;
}

.bc-plan-featured {
    border: 2px solid var(--bc-green);
    box-shadow: 0 24px 60px rgba(47,125,74,.14);
}

.bc-plan-badge {
    position: absolute;
    top: -14px;
    right: 22px;
    padding: 6px 11px;
    border-radius: 999px;
    background: var(--bc-green);
    color: white;
    font-size: 0.7rem;
    font-weight: 850;
    letter-spacing: .04em;
    text-transform: uppercase;
}

.bc-plan small {
    color: var(--bc-gold);
    font-size: .72rem;
    font-weight: 850;
    letter-spacing: .09em;
    text-transform: uppercase;
}

.bc-plan h3 {
    margin: 9px 0 8px;
    color: var(--bc-forest);
    font-size: 1.5rem;
}

.bc-plan-copy {
    min-height: 46px;
    color: var(--bc-muted);
    font-size: .9rem;
    line-height: 1.55;
}

.bc-plan .bc-list {
    flex: 1;
    margin-bottom: 26px;
}

.bc-addons {
    display: flex;
    flex-wrap: wrap;
    justify-content: center;
    gap: 9px;
    margin-top: 30px;
}

.bc-addon {
    padding: 14px 16px;
    border: 1px solid rgba(18,55,42,.12);
    border-radius: 13px;
    background: white;
    color: #52635a;
    box-shadow: 0 8px 24px rgba(18,55,42,.045);
    font-size: .8rem;
    font-weight: 720;
}

.bc-continuity {
    display: grid;
    grid-template-columns: .85fr 1.15fr;
    gap: 44px;
    align-items: center;
}

.bc-continuity h2 {
    margin: 0 0 18px;
    color: var(--bc-forest-deep);
    font-size: clamp(2rem, 4vw, 3.1rem);
    letter-spacing: -.04em;
}

.bc-continuity p {
    color: var(--bc-muted);
    line-height: 1.75;
}

.bc-continuity-flow {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 12px;
}

.bc-continuity-step {
    padding: 19px;
    border: 1px solid var(--bc-line);
    border-radius: 15px;
    background: white;
    color: var(--bc-forest);
    font-weight: 730;
}

.bc-final {
    padding: 84px 0;
    text-align: center;
    background:
        radial-gradient(circle at 50% 0%, rgba(95,174,100,.24), transparent 42%),
        var(--bc-forest-deep);
    color: white;
}

.bc-final h2 {
    max-width: 840px;
    margin: 0 auto 20px;
    font-size: clamp(2.1rem, 4vw, 3.6rem);
    letter-spacing: -.045em;
    line-height: 1.12;
}

.bc-final p {
    max-width: 650px;
    margin: 0 auto 30px;
    color: rgba(255,255,255,.68);
}

.bc-final-actions {
    display: flex;
    justify-content: center;
    flex-wrap: wrap;
    gap: 12px;
}

.bc-footer {
    padding: 54px 0 28px;
    background: #061c15;
    color: rgba(255,255,255,.62);
}

.bc-footer-grid {
    display: grid;
    grid-template-columns: 1.4fr repeat(3, .7fr);
    gap: 36px;
}

.bc-footer img {
    width: 260px;
    height: 80px;
    max-height: none;
    padding: 5px 8px;
    object-fit: contain;
    object-position: center;
    border: 1px solid rgba(255,255,255,.18);
    border-radius: 12px;
    background: #ffffff;
    box-shadow: 0 12px 28px rgba(0,0,0,.16);
}

.bc-footer h4 {
    margin: 0 0 14px;
    color: white;
    font-size: .83rem;
}

.bc-footer p {
    max-width: 360px;
    line-height: 1.65;
}

.bc-footer-links {
    display: grid;
    gap: 10px;
}

.bc-footer a {
    color: rgba(255,255,255,.58);
    font-weight: 550;
}

.bc-footer-bottom {
    margin-top: 38px;
    padding-top: 22px;
    border-top: 1px solid rgba(255,255,255,.1);
    font-size: .78rem;
}

@media (max-width: 1050px) {
    .bc-navlinks { display: none; }
    .bc-card-grid { grid-template-columns: repeat(3, 1fr); }
    .bc-flow { grid-template-columns: repeat(3, 1fr); }
    .bc-flow-step:nth-child(3n)::after { display: none; }
    .bc-ecosystem-brand small { display: none; }
}

@media (max-width: 820px) {
    .bc-hero { padding-top: 64px; }
    .bc-hero-grid,
    .bc-continuity { grid-template-columns: 1fr; }
    .bc-demo-shell { max-width: 650px; }
    .bc-benefits-grid { grid-template-columns: repeat(2, 1fr); }
    .bc-plans { grid-template-columns: 1fr; }
    .bc-plan-copy { min-height: auto; }
    .bc-footer-grid { grid-template-columns: 1fr 1fr; }
    .bc-hero-ecosystem {
        align-items: flex-start;
        flex-direction: column;
    }
    .bc-ecosystem-brands {
        width: 100%;
        justify-content: flex-start;
        flex-wrap: wrap;
    }
}

@media (max-width: 620px) {
    .bc-container { width: min(100% - 24px, 1180px); }
    .bc-navbar-inner { min-height: 72px; }
    .bc-brand {
        width: 160px;
        height: 52px;
        min-width: 160px;
    }
    .bc-nav-actions .bc-button-primary { display: none; }
    .bc-button { min-height: 42px; padding: 0 14px; }
    .bc-hero { padding: 48px 0 58px; }
    .bc-hero h1 { font-size: 2.45rem; }
    .bc-demo-body { grid-template-columns: 1fr; }
    .bc-demo-panel { display: grid; grid-template-columns: repeat(2, 1fr); }
    .bc-demo-map { min-height: 290px; }
    .bc-section { padding: 66px 0; }
    .bc-split,
    .bc-card-grid,
    .bc-benefits-grid,
    .bc-continuity-flow,
    .bc-footer-grid { grid-template-columns: 1fr; }
    .bc-flow { grid-template-columns: repeat(2, 1fr); }
    .bc-flow-step::after { display: none !important; }
    .bc-module-card p { min-height: auto; }
    .bc-panel,
    .bc-plan { padding: 24px; }
    .bc-hero-ecosystem { margin-top: 28px; }
}
</style>
"""


PRIVATE_STYLES = """
<style>
:root {
    --bc-private-forest: #12372a;
    --bc-private-green: #2f7d4a;
    --bc-private-gold: #b58a38;
    --bc-private-soft: #f4f7f4;
}

[data-testid="stSidebar"] {
    background:
        linear-gradient(180deg, rgba(9, 37, 28, .98), rgba(13, 49, 37, .98));
    border-right: 1px solid rgba(255,255,255,.08);
}

[data-testid="stSidebar"] * {
    color: rgba(255,255,255,.88);
}

[data-testid="stSidebarLogo"] {
    display: block !important;
    width: 230px !important;
    height: 70px !important;
    max-height: none !important;
    box-sizing: border-box !important;
    margin: 4px auto 14px !important;
    padding: 0 !important;
    transform: translateY(8px);
    border: 1px solid rgba(255,255,255,.18);
    border-radius: 12px;
    background: #ffffff;
    box-shadow: 0 12px 28px rgba(0,0,0,.16);
    object-fit: cover !important;
    object-position: center top !important;
}

[data-testid="stSidebarNav"] span {
    font-weight: 650;
}

.stApp {
    background: #f5f7f5;
}

.block-container {
    max-width: 1240px;
    padding-top: 5.5rem !important;
    padding-bottom: 3rem;
}

.bc-workspace-card {
    padding: 14px;
    margin: 8px 0 18px;
    border: 1px solid rgba(255,255,255,.1);
    border-radius: 14px;
    background: rgba(255,255,255,.055);
}

.bc-workspace-card strong {
    display: block;
    color: white;
}

.bc-workspace-card span {
    display: block;
    margin-top: 4px;
    color: rgba(255,255,255,.58);
    font-size: .75rem;
}

.bc-account-card {
    display: grid;
    gap: 3px;
    margin: 16px 0 10px;
}

.bc-account-card strong {
    color: white;
    font-size: .86rem;
}

.bc-account-card span {
    color: rgba(255,255,255,.56);
    font-size: .72rem;
}

.bc-plan-pill {
    display: inline-flex !important;
    width: auto;
    margin-top: 10px !important;
    padding: 4px 9px;
    border-radius: 999px;
    background: rgba(233,216,173,.12);
    color: #ead49c !important;
    font-size: .7rem !important;
    font-weight: 750;
}

.bc-page-header {
    display: block;
    margin: 0 0 4px;
}

[data-testid="stAppViewContainer"] .bc-page-kicker {
    margin-bottom: 8px;
    color: var(--bc-private-green) !important;
    font-size: .76rem;
    font-weight: 800;
    letter-spacing: .1em;
    text-transform: uppercase;
}

[data-testid="stAppViewContainer"] .bc-page-title {
    margin: 0;
    color: #10231a !important;
    font-size: clamp(2rem, 4vw, 3rem);
    letter-spacing: -.04em;
}

[data-testid="stAppViewContainer"] .bc-page-subtitle {
    max-width: 760px;
    margin: 10px 0 30px;
    color: #68756e !important;
    line-height: 1.65;
}

[data-testid="stMain"] h2,
[data-testid="stMain"] h3 {
    color: #173a2b !important;
}

.bc-stat-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 14px;
    margin: 18px 0 28px;
}

.bc-metadata-strip {
    display: grid;
    grid-template-columns: 1.4fr repeat(4, 1fr);
    gap: 1px;
    overflow: hidden;
    margin: 8px 0 22px;
    border: 1px solid #dfe7e1;
    border-radius: 16px;
    background: #dfe7e1;
}

.bc-metadata-strip div {
    min-width: 0;
    padding: 14px 16px;
    background: white;
}

.bc-metadata-strip small,
.bc-metadata-strip strong {
    display: block;
}

.bc-metadata-strip small {
    color: #7a8780;
    font-size: .68rem;
}

.bc-metadata-strip strong {
    overflow: hidden;
    margin-top: 5px;
    color: #173a2b;
    font-size: .82rem;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.bc-stat {
    padding: 20px;
    border: 1px solid #dfe7e1;
    border-radius: 16px;
    background: white;
    box-shadow: 0 8px 24px rgba(18,55,42,.045);
}

.bc-stat span {
    display: block;
    color: #6c7972;
    font-size: .78rem;
    font-weight: 650;
}

.bc-stat strong {
    display: block;
    margin: 8px 0 4px;
    color: #12372a;
    font-size: 1.7rem;
}

.bc-stat small {
    color: #859189;
    font-size: .72rem;
}

.bc-metadata-strip-compact {
    grid-template-columns: 1.35fr repeat(3, 1fr);
}

.bc-guidance-card {
    margin: 18px 0 16px;
    padding: 26px 28px;
    border: 1px solid rgba(47, 125, 74, .25);
    border-left: 5px solid var(--bc-private-green);
    border-radius: 18px;
    background: linear-gradient(145deg, #f8fbf8, #edf6ef);
}

.bc-guidance-card small {
    color: var(--bc-private-green);
    font-size: .72rem;
    font-weight: 850;
    letter-spacing: .08em;
    text-transform: uppercase;
}

[data-testid="stAppViewContainer"] .bc-guidance-card h2 {
    margin: 8px 0 8px;
    color: #173a2b !important;
    font-size: clamp(1.35rem, 2.5vw, 1.9rem);
    letter-spacing: -.025em;
}

.bc-guidance-card p {
    max-width: 840px;
    margin: 0;
    color: #5e6e65;
    line-height: 1.6;
}

.bc-project-overview {
    margin-top: 14px;
    padding: 22px;
    border: 1px solid #dfe7e1;
    border-radius: 18px;
    background: #ffffff;
    box-shadow: 0 8px 24px rgba(18, 55, 42, .045);
}

.bc-project-overview-head {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 18px;
}

.bc-project-overview-head small {
    color: #6d7c74;
    font-size: .72rem;
    font-weight: 750;
}

.bc-project-overview-head h3 {
    margin: 6px 0 3px;
    color: #173a2b !important;
    font-size: 1.15rem;
}

.bc-project-overview-head p {
    margin: 0;
    color: #68776f;
    font-size: .82rem;
}

.bc-project-overview-head > strong {
    color: var(--bc-private-green);
    font-size: 1.2rem;
}

.bc-project-progress {
    height: 8px;
    overflow: hidden;
    margin: 17px 0;
    border-radius: 999px;
    background: #e7eee9;
}

.bc-project-progress span {
    display: block;
    height: 100%;
    border-radius: inherit;
    background: linear-gradient(90deg, var(--bc-private-green), #65a868);
}

.bc-project-overview dl {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 12px;
    margin: 0;
}

.bc-project-overview dl div {
    min-width: 0;
}

.bc-project-overview dt {
    color: #7b8881;
    font-size: .68rem;
}

.bc-project-overview dd {
    overflow: hidden;
    margin: 4px 0 0;
    color: #30483c;
    font-size: .78rem;
    font-weight: 700;
    text-overflow: ellipsis;
    white-space: nowrap;
}

.bc-stat-grid-compact {
    grid-template-columns: repeat(3, 1fr);
}

.bc-private-card,
.bc-module-lock {
    padding: 24px;
    border: 1px solid #dfe7e1;
    border-radius: 18px;
    background: white;
}

.bc-private-card h3,
.bc-module-lock h3 {
    margin: 0 0 10px;
    color: #173a2b;
}

.bc-private-card p,
.bc-module-lock p {
    color: #6b7770;
    line-height: 1.6;
}

.bc-module-lock {
    border-style: dashed;
    background: #fbfcfb;
}

.bc-module-lock-badge {
    display: inline-flex;
    padding: 5px 9px;
    margin-bottom: 14px;
    border-radius: 999px;
    background: #f4ecda;
    color: #85631f;
    font-size: .72rem;
    font-weight: 800;
}

.bc-activity-empty {
    padding: 24px;
    border: 1px dashed #ced9d1;
    border-radius: 16px;
    color: #718078;
    text-align: center;
    background: rgba(255,255,255,.65);
}

.bc-dashboard-modules {
    display: grid;
    grid-template-columns: repeat(5, 1fr);
    gap: 12px;
}

.bc-dashboard-module {
    position: relative;
    min-width: 0;
    padding: 20px;
    border: 1px solid #dfe7e1;
    border-radius: 16px;
    background: white;
}

.bc-dashboard-module-brand {
    display: flex;
    min-height: 52px;
    align-items: flex-start;
    justify-content: space-between;
    gap: 10px;
}

.bc-dashboard-module-logo {
    display: block;
    width: 52px;
    height: 52px;
    border: 1px solid #dfe7e1;
    border-radius: 13px;
    background: #fff;
    object-fit: contain;
}

.bc-dashboard-module h3 {
    margin: 13px 0 8px;
    color: #173a2b;
    font-size: .98rem;
}

.bc-dashboard-module p {
    min-height: 86px;
    color: #6b7770;
    font-size: .78rem;
    line-height: 1.5;
}

.bc-dashboard-module a {
    display: block;
    margin-top: 8px;
    color: var(--bc-private-green);
    font-size: .76rem;
    font-weight: 750;
    text-decoration: none;
}

.bc-dashboard-module a::after {
    content: "";
    position: absolute;
    inset: 0;
}

.bc-module-message {
    display: block;
    color: #596961;
    font-size: .71rem;
    line-height: 1.4;
}

.bc-module-status {
    display: inline-flex;
    padding: 4px 8px;
    border-radius: 999px;
    font-size: .66rem;
    font-weight: 800;
}

.bc-status-active {
    background: #e9f5ec;
    color: #25683d;
}

.bc-status-locked {
    background: #f4ecda;
    color: #85631f;
}

.bc-status-soon {
    background: #e8eef5;
    color: #355b7a;
}

.bc-integration-card {
    margin: 12px 0;
    padding: 24px;
    border: 1px solid #dfe7e1;
    border-radius: 18px;
    background: #ffffff;
    box-shadow: 0 8px 24px rgba(18,55,42,.045);
}

.bc-integration-card h3 {
    margin: 14px 0 8px;
    color: #173a2b;
}

.bc-integration-card p {
    max-width: 760px;
    margin: 0;
    color: #6b7770;
    line-height: 1.6;
}

.bc-integration-status {
    display: inline-flex;
    padding: 5px 9px;
    border-radius: 999px;
    font-size: .7rem;
    font-weight: 800;
}

.bc-integration-ready {
    background: #e9f5ec;
    color: #25683d;
}

.bc-integration-pending {
    background: #f4ecda;
    color: #85631f;
}

/* The authenticated workspace uses a light canvas even when Streamlit keeps
   the dark application theme for native widgets. Define the complete private
   reading surface here so every page and embedded BioCore module has the same
   accessible contrast. The sidebar remains intentionally dark. */
[data-testid="stAppViewContainer"] [data-testid="stMain"] {
    color: #173a2b !important;
}

[data-testid="stAppViewContainer"] [data-testid="stMain"] h1,
[data-testid="stAppViewContainer"] [data-testid="stMain"] h2,
[data-testid="stAppViewContainer"] [data-testid="stMain"] h3,
[data-testid="stAppViewContainer"] [data-testid="stMain"] h4,
[data-testid="stAppViewContainer"] [data-testid="stMain"] h5,
[data-testid="stAppViewContainer"] [data-testid="stMain"] h6,
[data-testid="stAppViewContainer"] [data-testid="stMain"] .stMarkdown p,
[data-testid="stAppViewContainer"] [data-testid="stMain"] .stMarkdown li,
[data-testid="stAppViewContainer"] [data-testid="stMain"] [data-testid="stMarkdownContainer"] p,
[data-testid="stAppViewContainer"] [data-testid="stMain"] [data-testid="stMarkdownContainer"] li,
[data-testid="stAppViewContainer"] [data-testid="stMain"] [data-testid="stCaptionContainer"] p,
[data-testid="stAppViewContainer"] [data-testid="stMain"] [data-testid="stWidgetLabel"] p,
[data-testid="stAppViewContainer"] [data-testid="stMain"] [data-testid="stMetricLabel"] p,
[data-testid="stAppViewContainer"] [data-testid="stMain"] [data-testid="stMetricValue"] {
    color: #173a2b !important;
    -webkit-text-fill-color: #173a2b !important;
}

[data-testid="stAppViewContainer"] [data-testid="stMain"] [data-testid="stCaptionContainer"] p {
    color: #68756e !important;
    -webkit-text-fill-color: #68756e !important;
}

[data-testid="stAppViewContainer"] [data-testid="stMain"] [data-baseweb="tab-list"] button,
[data-testid="stAppViewContainer"] [data-testid="stMain"] [data-baseweb="tab-list"] button p,
[data-testid="stAppViewContainer"] [data-testid="stMain"] [data-testid="stTab"],
[data-testid="stAppViewContainer"] [data-testid="stMain"] [data-testid="stTab"] p {
    color: #53675c !important;
    -webkit-text-fill-color: #53675c !important;
}

[data-testid="stAppViewContainer"] [data-testid="stMain"] [data-baseweb="tab-list"] button[aria-selected="true"],
[data-testid="stAppViewContainer"] [data-testid="stMain"] [data-baseweb="tab-list"] button[aria-selected="true"] p,
[data-testid="stAppViewContainer"] [data-testid="stMain"] [data-testid="stTab"][aria-selected="true"],
[data-testid="stAppViewContainer"] [data-testid="stMain"] [data-testid="stTab"][aria-selected="true"] p,
[data-testid="stAppViewContainer"] [data-testid="stMain"] [data-testid="stTab"][data-selected="true"],
[data-testid="stAppViewContainer"] [data-testid="stMain"] [data-testid="stTab"][data-selected="true"] p {
    color: var(--bc-private-green) !important;
    -webkit-text-fill-color: var(--bc-private-green) !important;
}

[data-testid="stAppViewContainer"] [data-testid="stMain"] [data-testid="stAlertContainer"] [data-testid="stMarkdownContainer"] p,
[data-testid="stAppViewContainer"] [data-testid="stMain"] [data-testid="stAlertContainer"] [data-testid="stMarkdownContainer"] li {
    color: #173a2b !important;
    -webkit-text-fill-color: #173a2b !important;
}

[data-testid="stAppViewContainer"] [data-testid="stMain"] input,
[data-testid="stAppViewContainer"] [data-testid="stMain"] textarea,
[data-testid="stAppViewContainer"] [data-testid="stMain"] [data-baseweb="select"] > div,
[data-testid="stAppViewContainer"] [data-testid="stMain"] [data-baseweb="input"] > div {
    border-color: #c8d5cd !important;
    background: #ffffff !important;
    color: #173a2b !important;
    -webkit-text-fill-color: #173a2b !important;
}

[data-testid="stAppViewContainer"] [data-testid="stMain"] input::placeholder,
[data-testid="stAppViewContainer"] [data-testid="stMain"] textarea::placeholder {
    color: #87958d !important;
    -webkit-text-fill-color: #87958d !important;
    opacity: 1;
}

[data-testid="stAppViewContainer"] [data-testid="stMain"] [data-baseweb="select"] span,
[data-testid="stAppViewContainer"] [data-testid="stMain"] [data-baseweb="select"] svg {
    color: #173a2b !important;
    fill: #173a2b !important;
    -webkit-text-fill-color: #173a2b !important;
}

[data-testid="stAppViewContainer"] [data-testid="stMain"] [data-testid="stFileUploaderDropzone"] {
    border-color: #c8d5cd !important;
    background: #f8faf8 !important;
    color: #173a2b !important;
}

[data-testid="stAppViewContainer"] [data-testid="stMain"] [data-testid="stFileUploaderDropzone"] * {
    color: #173a2b !important;
    -webkit-text-fill-color: #173a2b !important;
}

/* Streamlit can retain text colors from a dark theme even though the private
   workspace uses a light canvas. Keep native navigation and actions readable
   without relying on generated class names. */
[data-testid="stAppViewContainer"] a[data-testid="stPageLink-NavLink"] {
    min-height: 44px;
    border: 1px solid #c8d5cd !important;
    border-radius: 12px !important;
    background: #ffffff !important;
    color: #173a2b !important;
    box-shadow: 0 4px 14px rgba(18, 55, 42, .035);
    text-decoration: none !important;
}

[data-testid="stAppViewContainer"] a[data-testid="stPageLink-NavLink"] p,
[data-testid="stAppViewContainer"] a[data-testid="stPageLink-NavLink"] span,
[data-testid="stAppViewContainer"] a[data-testid="stPageLink-NavLink"] [data-testid="stIconMaterial"] {
    color: #173a2b !important;
    -webkit-text-fill-color: #173a2b !important;
}

[data-testid="stAppViewContainer"] a[data-testid="stPageLink-NavLink"]:hover {
    border-color: var(--bc-private-green) !important;
    background: #edf6ef !important;
}

[data-testid="stAppViewContainer"] a[data-testid="stPageLink-NavLink"]:focus-visible {
    outline: 3px solid rgba(47, 125, 74, .28);
    outline-offset: 2px;
}

[data-testid="stAppViewContainer"] button[data-testid="stBaseButton-primary"] {
    border-color: var(--bc-private-green) !important;
    background: var(--bc-private-green) !important;
    color: #ffffff !important;
}

[data-testid="stAppViewContainer"] button[data-testid="stBaseButton-primary"] p,
[data-testid="stAppViewContainer"] button[data-testid="stBaseButton-primary"] span {
    color: #ffffff !important;
    -webkit-text-fill-color: #ffffff !important;
}

[data-testid="stAppViewContainer"] button[data-testid="stBaseButton-primary"]:hover {
    border-color: #25683d !important;
    background: #25683d !important;
}

[data-testid="stAppViewContainer"] button[data-testid="stBaseButton-secondary"] {
    border-color: #b9c9bf !important;
    background: #ffffff !important;
    color: #173a2b !important;
}

[data-testid="stAppViewContainer"] button[data-testid="stBaseButton-secondary"] p,
[data-testid="stAppViewContainer"] button[data-testid="stBaseButton-secondary"] span {
    color: #173a2b !important;
    -webkit-text-fill-color: #173a2b !important;
}

[data-testid="stAppViewContainer"] button[data-testid="stBaseButton-secondary"]:hover {
    border-color: var(--bc-private-green) !important;
    background: #edf6ef !important;
}

@media (max-width: 900px) {
    .bc-stat-grid { grid-template-columns: repeat(2, 1fr); }
    .bc-metadata-strip { grid-template-columns: repeat(2, 1fr); }
    .bc-dashboard-modules { grid-template-columns: repeat(2, 1fr); }
    .bc-project-overview dl { grid-template-columns: repeat(2, 1fr); }
}

@media (max-width: 560px) {
    .block-container { padding: 5rem 1rem 2.5rem !important; }
    .bc-stat-grid { grid-template-columns: 1fr; }
    .bc-metadata-strip,
    .bc-dashboard-modules { grid-template-columns: 1fr; }
    .bc-stat-grid-compact,
    .bc-project-overview dl { grid-template-columns: 1fr; }
    .bc-dashboard-module p { min-height: auto; }
}
</style>
"""
