from biocore.config.navigation import pages_for
from biocore.security.authorization import UserContext
from biocore.security.roles import Role


def test_client_navigation_hides_administration() -> None:
    user = UserContext("u1", "org-a", frozenset({Role.CLIENT_READER}))
    assert "Administración" not in pages_for(user)


def test_superadmin_navigation_includes_administration() -> None:
    user = UserContext("u1", "org-a", frozenset({Role.SUPERADMIN}))
    assert "Administración" in pages_for(user)
