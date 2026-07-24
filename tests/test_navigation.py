from biocore.config.navigation import pages_for
from biocore.domain.subscriptions import SubscriptionSnapshot
from biocore.security.authorization import UserContext
from biocore.security.roles import Role


def test_client_navigation_hides_administration() -> None:
    user = UserContext("u1", "org-a", frozenset({Role.CLIENT_READER}))
    assert "ADMINISTRACIÓN BIOCORE" not in pages_for(user)


def test_superadmin_navigation_includes_administration() -> None:
    user = UserContext("u1", "org-a", frozenset({Role.SUPERADMIN}))
    navigation = pages_for(user)
    assert "ADMINISTRACIÓN BIOCORE" in navigation
    ecosystem_titles = [page.title for page in navigation["MÓDULOS"]]
    assert "BioCore Intelligence" in ecosystem_titles


def test_client_navigation_uses_unrepeated_sections() -> None:
    user = UserContext("u1", "org-a", frozenset({Role.CLIENT_READER}))
    navigation = pages_for(user)
    assert navigation["GENERAL"][0].title == "Inicio"
    assert [page.title for page in navigation["CUENTA"]] == [
        "Suscripción",
        "Usuarios",
        "Configuración",
    ]
    assert [page.title for page in navigation["GESTIÓN AMBIENTAL"]] == [
        "Proyectos",
        "Áreas de estudio",
        "Campañas",
        "Mapas",
        "Informes",
    ]
    module_titles = [page.title for page in navigation["MÓDULOS"]]
    assert module_titles.count("BioCore Intelligence") == 1
    assert module_titles.count("BioCore Reports") == 1


def test_subscription_filters_operational_modules_but_keeps_account() -> None:
    user = UserContext("u1", "org-a", frozenset({Role.CLIENT_READER}))
    current = SubscriptionSnapshot.unconfigured("org-a")
    navigation = pages_for(user, current)
    assert "GENERAL" not in navigation
    assert "MÓDULOS" not in navigation
    assert [page.title for page in navigation["CUENTA"]] == [
        "Suscripción",
        "Usuarios",
        "Configuración",
    ]


def test_core_navigation_keeps_reports_repository_separate_from_reports_module() -> None:
    from datetime import date, timedelta

    from biocore.domain.subscriptions import (
        OrganizationSubscription,
        SubscriptionPlan,
        SubscriptionStatus,
    )

    user = UserContext("u1", "org-a", frozenset({Role.CLIENT_READER}))
    current = SubscriptionSnapshot(
        organization_id="org-a",
        organization_name="Org A",
        subscription=OrganizationSubscription(
            id="s1",
            organization_id="org-a",
            plan=SubscriptionPlan.CORE,
            status=SubscriptionStatus.ACTIVE,
            starts_on=date.today(),
            renews_on=date.today() + timedelta(days=30),
            user_limit=5,
            project_limit=3,
            storage_limit_gb=10,
            support_level="standard",
        ),
    )
    navigation = pages_for(user, current)
    assert "Informes" in [
        page.title for page in navigation["GESTIÓN AMBIENTAL"]
    ]
    assert "BioCore Reports" in [page.title for page in navigation["MÓDULOS"]]
