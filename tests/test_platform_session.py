from pathlib import Path

from biocore.domain.subscriptions import SubscriptionSnapshot
from biocore.platform_session import (
    PLATFORM_SESSION_KEY,
    PlatformSessionUnavailable,
    clear_platform_session,
    load_platform_session,
    store_platform_session,
)
from biocore.security.authorization import UserContext
from biocore.security.identity import AuthenticatedIdentity
from biocore.security.roles import Role


def private_session_values(
    organization_id: str = "org-a",
) -> tuple[AuthenticatedIdentity, UserContext, SubscriptionSnapshot]:
    return (
        AuthenticatedIdentity(
            "google|user-1",
            "user@example.com",
            "Persona BioCore",
            True,
        ),
        UserContext(
            "user-1",
            organization_id,
            frozenset({Role.CLIENT_ADMIN}),
        ),
        SubscriptionSnapshot.unconfigured(
            organization_id, "Organización A"
        ),
    )


def test_platform_session_is_stored_atomically_with_compatibility_aliases() -> None:
    state: dict[str, object] = {}
    identity, context, subscription = private_session_values()
    stored = store_platform_session(state, identity, context, subscription)

    assert stored.context == context
    assert state[PLATFORM_SESSION_KEY]
    assert state["biocore_identity"] == identity
    assert state["biocore_user_context"] == context
    assert state["biocore_subscription"] == subscription
    assert state["biocore_selected_organization_id"] == "org-a"


def test_platform_session_repairs_missing_aliases_after_page_rerun() -> None:
    state: dict[str, object] = {}
    identity, context, subscription = private_session_values()
    store_platform_session(state, identity, context, subscription)
    state.pop("biocore_user_context")
    state.pop("biocore_subscription")

    restored = load_platform_session(state)

    assert restored.context == context
    assert state["biocore_user_context"] == context
    assert state["biocore_subscription"] == subscription


def test_legacy_private_session_is_promoted_to_atomic_record() -> None:
    identity, context, subscription = private_session_values()
    state: dict[str, object] = {
        "biocore_identity": identity,
        "biocore_user_context": context,
        "biocore_subscription": subscription,
    }

    restored = load_platform_session(state)

    assert restored.identity == identity
    assert PLATFORM_SESSION_KEY in state


def test_session_rejects_cross_organization_subscription() -> None:
    state: dict[str, object] = {}
    identity, context, _ = private_session_values("org-a")
    subscription = SubscriptionSnapshot.unconfigured("org-b")

    try:
        store_platform_session(state, identity, context, subscription)
    except PlatformSessionUnavailable:
        pass
    else:
        raise AssertionError("Cross-organization session was accepted")


def test_clear_platform_session_removes_authentication_keys() -> None:
    state: dict[str, object] = {"unrelated": "keep"}
    store_platform_session(state, *private_session_values())
    state["biocore_central_session_token"] = "secret"

    clear_platform_session(state)

    assert state == {"unrelated": "keep"}


def test_entrypoint_initializes_private_session_before_navigation_runs() -> None:
    entrypoint = Path("biocore_app.py").read_text(encoding="utf-8")
    assert entrypoint.index("store_platform_session(") < entrypoint.index(
        "st.navigation(navigation).run()"
    )
    assert 'st.session_state["biocore_project_service"]' in entrypoint
