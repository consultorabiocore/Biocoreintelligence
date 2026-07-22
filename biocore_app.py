"""Gradual BioCore entrypoint; the legacy application remains in app.py."""
import streamlit as st

from biocore.config.navigation import pages_for
from biocore.security.authorization import UserContext
from biocore.security.roles import Role


st.set_page_config(page_title="BioCore", layout="wide")


def current_context() -> UserContext:
    # Temporary adapter until OIDC is configured. It grants least privilege and
    # never accepts an organization identifier from URL parameters.
    return UserContext(
        user_id=st.session_state.get("user_id", "anonymous"),
        organization_id=st.session_state.get("organization_id", "unassigned"),
        roles=frozenset({Role.CLIENT_READER}),
    )


context = current_context()
navigation = {
    section: [st.Page(item.path, title=item.title) for item in items]
    for section, items in pages_for(context).items()
}
st.navigation(navigation).run()
