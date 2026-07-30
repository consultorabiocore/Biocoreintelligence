from collections.abc import Callable
from datetime import timedelta
from uuid import uuid4

from .models import (
    InvitationRecord,
    IssuedInvitation,
    SessionContext,
)
from .repositories import InvitationRepository
from .session_service import utc_now
from .tokens import OpaqueTokenFactory


class InvitationError(PermissionError):
    pass


class InvitationService:
    def __init__(
        self,
        repository: InvitationRepository,
        *,
        token_factory: OpaqueTokenFactory | None = None,
        invitation_ttl: timedelta = timedelta(days=7),
        clock: Callable = utc_now,
    ) -> None:
        self._repository = repository
        self._tokens = token_factory or OpaqueTokenFactory()
        self._invitation_ttl = invitation_ttl
        self._clock = clock

    def create(
        self,
        inviter: SessionContext,
        email: str,
        role: str,
        project_ids: tuple[str, ...] = (),
    ) -> IssuedInvitation:
        if not inviter.has_permission("users:invite"):
            raise InvitationError("User cannot invite organization members")
        assignable_roles = {
            "superadmin": {
                "superadmin",
                "administradora_biocore",
                "especialista_biocore",
                "cliente_administrador",
                "cliente_editor",
                "cliente_lector",
            },
            "administradora_biocore": {
                "especialista_biocore",
                "cliente_administrador",
                "cliente_editor",
                "cliente_lector",
            },
            "cliente_administrador": {
                "cliente_editor",
                "cliente_lector",
            },
        }
        allowed = {
            candidate
            for inviter_role in inviter.roles
            for candidate in assignable_roles.get(inviter_role, set())
        }
        if role not in allowed:
            raise InvitationError("Role cannot be assigned by this user")
        normalized_email = email.strip().lower()
        if "@" not in normalized_email:
            raise ValueError("A valid invitation email is required")
        if (
            "superadmin" not in inviter.roles
            and any(
                project_id not in inviter.project_ids
                for project_id in project_ids
            )
        ):
            raise InvitationError("Cannot grant an unauthorized project")
        now = self._clock()
        token, token_hash = self._tokens.issue()
        record = InvitationRecord(
            id=str(uuid4()),
            organization_id=inviter.organization_id,
            email=normalized_email,
            role=role,
            project_ids=project_ids,
            invited_by_user_id=inviter.user_id,
            expires_at=now + self._invitation_ttl,
        )
        self._repository.create_invitation(record, token_hash)
        return IssuedInvitation(token, record)

    def accept(
        self,
        raw_token: str,
        user_id: str,
        verified_email: str,
    ) -> InvitationRecord:
        invitation = self._repository.consume_invitation(
            self._tokens.digest(raw_token),
            user_id,
            verified_email.strip().lower(),
        )
        if invitation is None:
            raise InvitationError("Invitation is invalid, expired or used")
        self._repository.activate_membership(user_id, invitation)
        return invitation
