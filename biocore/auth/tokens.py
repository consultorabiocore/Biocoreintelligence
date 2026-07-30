import hashlib
import secrets


class OpaqueTokenFactory:
    """Generate high-entropy bearer values and store only their digest."""

    def __init__(self, byte_length: int = 32) -> None:
        if byte_length < 24:
            raise ValueError("Opaque tokens require at least 24 random bytes")
        self._byte_length = byte_length

    def issue(self) -> tuple[str, str]:
        raw = secrets.token_urlsafe(self._byte_length)
        return raw, self.digest(raw)

    @staticmethod
    def digest(raw: str) -> str:
        # SHA-256 is appropriate for random 256-bit tokens. It must never be
        # used as the password hashing strategy.
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()
