from typing import Any

from .auth_service import AuthenticationError
from .models import IdentityClaims


class JwtIdentityVerifier:
    """Verify OIDC/Supabase JWTs against the provider's published JWKS."""

    def __init__(
        self,
        *,
        provider: str,
        issuer: str,
        audience: str,
        jwks_url: str,
        algorithms: tuple[str, ...] = ("RS256",),
    ) -> None:
        if not all((provider, issuer, audience, jwks_url)):
            raise ValueError("OIDC verifier settings are incomplete")
        self._provider = provider
        self._issuer = issuer
        self._audience = audience
        self._algorithms = algorithms
        try:
            from jwt import PyJWKClient
        except ImportError as exc:  # pragma: no cover - deployment guard
            raise RuntimeError("PyJWT is required for central authentication") from exc
        self._jwks = PyJWKClient(jwks_url)

    def verify(self, raw_identity_token: str) -> IdentityClaims:
        if not raw_identity_token:
            raise AuthenticationError("Identity token is required")
        try:
            import jwt

            signing_key = self._jwks.get_signing_key_from_jwt(raw_identity_token)
            values: dict[str, Any] = jwt.decode(
                raw_identity_token,
                signing_key.key,
                algorithms=list(self._algorithms),
                audience=self._audience,
                issuer=self._issuer,
                options={"require": ["exp", "iat", "sub", "email"]},
            )
        except Exception as exc:
            raise AuthenticationError("Identity token is invalid") from exc

        verified_value = values.get("email_verified")
        verified = verified_value is True or str(verified_value).lower() == "true"
        return IdentityClaims(
            provider=self._provider,
            subject=str(values["sub"]).strip(),
            email=str(values["email"]).strip().lower(),
            email_verified=verified,
            display_name=(
                str(values.get("name")).strip() if values.get("name") else None
            ),
        )
