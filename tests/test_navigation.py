from biocore.config.navigation import pages_for
from biocore.domain.subscriptions import SubscriptionSnapshot
from biocore.security.authorization import UserContext
from biocore.security.roles import Role


def test_client_navigation_hides_administration() -> None:
    user = UserContext("u1", "org-a", frozenset({Role.CLIENT_READER}))
    assert "Sistema" not in pages_for(user)


def test_superadmin_navigation_includes_administration() -> None:
    user = UserContext("u1", "org-a", frozenset({Role.SUPERADMIN}))
    navigation = pages_for(user)
    assert "Sistema" in navigation
    ecosystem_titles = [page.title for page in navigation["Ecosistema"]]
    assert "BioCore Intelligence" in ecosystem_titles


def test_client_navigation_uses_unrepeated_sections() -> None:
    user = UserContext("u1", "org-a", frozenset({Role.CLIENT_READER}))
    navigation = pages_for(user)
    assert navigation["BioCore"][0].title == "Inicio"
    assert [page.title for page in navigation["Cuenta"]] == [
        "Suscripción",
        "Módulos",
    ]


def test_subscription_filters_operational_modules_but_keeps_account() -> None:
    user = UserContext("u1", "org-a", frozenset({Role.CLIENT_READER}))
    current = SubscriptionSnapshot.unconfigured("org-a")
    navigation = pages_for(user, current)
    assert "BioCore" not in navigation
    assert "Ecosistema" not in navigation
    assert [page.title for page in navigation["Cuenta"]] == [
        "Suscripción",
        "Módulos",
    ]
