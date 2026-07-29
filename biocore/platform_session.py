"""Stable Streamlit session contract shared by every private platform page."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, MutableMapping, cast

from biocore.domain.subscriptions import SubscriptionSnapshot
from biocore.security.authorization import UserContext
from biocore.security.identity import AuthenticatedIdentity


PLATFORM_SESSION_KEY = "biocore_platform_session"
PLATFORM_SESSION_VERSION = 1


class PlatformSessionUnavailable(RuntimeError):
    """Raised when a private page has no complete, internally consistent session."""


@dataclass(frozen=True)
class PlatformSession:
    identity: AuthenticatedIdentity
    context: UserContext
    subscription: SubscriptionSnapshot


def _same_organization(context: object, subscription: object) -> bool:
    return bool(
        getattr(context, "organization_id", None)
        and getattr(context, "organization_id", None)
        == getattr(subscription, "organization_id", None)
    )


def store_platform_session(
    state: MutableMapping[str, Any],
    identity: AuthenticatedIdentity,
    context: UserContext,
    subscription: SubscriptionSnapshot,
) -> PlatformSession:
    """Write one atomic session record and maintain compatibility aliases."""
    if not _same_organization(context, subscription):
        raise PlatformSessionUnavailable(
            "La membresía y la suscripción pertenecen a organizaciones distintas"
        )

    session = PlatformSession(identity, context, subscription)
    state[PLATFORM_SESSION_KEY] = {
        "version": PLATFORM_SESSION_VERSION,
        "identity_subject": identity.subject,
        "organization_id": context.organization_id,
        "identity": identity,
        "context": context,
        "subscription": subscription,
    }
    state["biocore_identity"] = identity
    state["biocore_user_context"] = context
    state["biocore_subscription"] = subscription
    state["biocore_selected_organization_id"] = context.organization_id
    return session


def load_platform_session(
    state: MutableMapping[str, Any],
) -> PlatformSession:
    """Load the private session and repair legacy aliases after Streamlit reruns."""
    raw = state.get(PLATFORM_SESSION_KEY)
    identity: object | None = None
    context: object | None = None
    subscription: object | None = None

    if isinstance(raw, dict) and raw.get("version") == PLATFORM_SESSION_VERSION:
        identity = raw.get("identity")
        context = raw.get("context")
        subscription = raw.get("subscription")

    # Compatibility with sessions created before the atomic record existed.
    identity = identity or state.get("biocore_identity")
    context = context or state.get("biocore_user_context")
    subscription = subscription or state.get("biocore_subscription")

    if identity is None or context is None or subscription is None:
        raise PlatformSessionUnavailable("Falta el contexto privado de BioCore")
    if not getattr(identity, "subject", None):
        raise PlatformSessionUnavailable("La identidad autenticada no es válida")
    if not getattr(context, "user_id", None) or not getattr(
        context, "organization_id", None
    ):
        raise PlatformSessionUnavailable("La membresía activa no es válida")
    if not _same_organization(context, subscription):
        raise PlatformSessionUnavailable(
            "La organización activa no coincide con la suscripción"
        )

    # Avoid isinstance checks here: Streamlit can reload imported classes while
    # retaining session values. The validated contract is stable across reloads.
    session = PlatformSession(
        cast(AuthenticatedIdentity, identity),
        cast(UserContext, context),
        cast(SubscriptionSnapshot, subscription),
    )
    store_platform_session(
        state,
        session.identity,
        session.context,
        session.subscription,
    )
    return session


def clear_platform_session(state: MutableMapping[str, Any]) -> None:
    """Remove only BioCore authentication/session keys."""
    for key in (
        PLATFORM_SESSION_KEY,
        "biocore_identity",
        "biocore_user_context",
        "biocore_subscription",
        "biocore_selected_organization_id",
        "organization_id",
        "biocore_central_session_token",
        "biocore_central_session_context",
    ):
        state.pop(key, None)
