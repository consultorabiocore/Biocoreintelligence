from .models import IdentityClaims


class VerificationError(PermissionError):
    pass


def require_verified_email(claims: IdentityClaims) -> None:
    if not claims.email or not claims.email_verified:
        raise VerificationError("A verified email is required")
