from html import escape

import streamlit as st


def render_page_header(kicker: str, title: str, subtitle: str) -> None:
    st.markdown(
        f"""
        <div class="bc-page-kicker">{escape(kicker)}</div>
        <h1 class="bc-page-title">{escape(title)}</h1>
        <p class="bc-page-subtitle">{escape(subtitle)}</p>
        """,
        unsafe_allow_html=True,
    )
