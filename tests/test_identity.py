import pytest

from biocore.security.identity import AuthenticatedIdentity, InvalidIdentityError


def test_oidc_identity_requires_subject() -> None:
    with pytest.raises(InvalidIdentityError):
        AuthenticatedIdentity.from_oidc_claims({"email": "user@example.com"})


def test_oidc_identity_normalizes_email() -> None:
    identity = AuthenticatedIdentity.from_oidc_claims(
        {"sub": "provider|123", "email": " USER@Example.COM "}
    )
    assert identity.subject == "provider|123"
    assert identity.email == "user@example.com"


def test_roles_from_token_are_not_accepted_as_authorization() -> None:
    identity = AuthenticatedIdentity.from_oidc_claims(
        {"sub": "provider|123", "roles": ["superadmin"]}
    )
    assert not hasattr(identity, "roles")
