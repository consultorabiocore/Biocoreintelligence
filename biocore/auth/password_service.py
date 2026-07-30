from typing import Protocol


class PasswordIdentityProvider(Protocol):
    """Boundary for a consolidated provider; BioCore never hashes passwords."""

    def request_password_reset(self, email: str, return_to: str) -> None:
        """Ask the identity provider to issue a temporary single-use flow."""

    def close_all_provider_sessions(self, provider_user_id: str) -> None:
        """Revoke identity-provider sessions after a security event."""


class PasswordService:
    def __init__(self, provider: PasswordIdentityProvider) -> None:
        self._provider = provider

    def request_reset(self, email: str, return_to: str) -> None:
        normalized = email.strip().lower()
        if "@" not in normalized:
            raise ValueError("A valid account email is required")
        self._provider.request_password_reset(normalized, return_to)

    def close_provider_sessions(self, provider_user_id: str) -> None:
        self._provider.close_all_provider_sessions(provider_user_id)
