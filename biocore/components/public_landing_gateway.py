import streamlit as st

from biocore.components.public_landing import render_public_landing


_PUBLIC_DIAGNOSTIC_LINK = "?diagnostico=publico"


def render_public_landing_with_diagnostic_cta() -> None:
    """Render the existing landing plus a public, no-login diagnostic entry."""
    st.markdown(
        f"""
        <style>
        .bc-public-diagnostic-fab {{
            position: fixed;
            right: 24px;
            bottom: 24px;
            z-index: 9999;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            padding: 14px 18px;
            border-radius: 999px;
            background: #B58A38;
            color: #ffffff !important;
            font-weight: 800;
            text-decoration: none !important;
            box-shadow: 0 12px 28px rgba(18, 55, 42, 0.28);
        }}
        .bc-public-diagnostic-fab:hover {{
            transform: translateY(-1px);
            filter: brightness(1.04);
        }}
        @media (max-width: 720px) {{
            .bc-public-diagnostic-fab {{
                right: 12px;
                bottom: 12px;
                left: 12px;
                border-radius: 14px;
            }}
        }}
        </style>
        <a class="bc-public-diagnostic-fab" href="{_PUBLIC_DIAGNOSTIC_LINK}">
            Diagnóstico ecológico gratuito · sin cuenta
        </a>
        """,
        unsafe_allow_html=True,
    )
    render_public_landing()
