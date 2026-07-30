from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from biocore.auth.auth_service import (
    AuthService,
    AuthenticationError,
    EmailVerificationRequired,
)
from biocore.auth.invitation_service import InvitationError, InvitationService
from biocore.auth.models import (
    AccessGrant,
    AuthenticatedUser,
    IdentityClaims,
    InvitationRecord,
    LaunchCodeRecord,
    SessionContext,
    SessionRecord,
)
from biocore.auth.module_launch_service import (
    InvalidReturnUrl,
    ModuleAccessDenied,
    ModuleLaunchService,
    ProjectAccessDenied,
    RedirectPolicy,
)
from biocore.auth.session_service import (
    SessionError,
    SessionExpired,
    SessionService,
)


class MutableClock:
    def __init__(self) -> None:
        self.value = datetime(2026, 7, 24, 12, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.value

    def advance(self, delta: timedelta) -> None:
        self.value += delta


class FakeDirectory:
    def __init__(self) -> None:
        self.user = AuthenticatedUser(
            id="user-1",
            email="client@example.com",
            display_name="Client",
            status="active",
            email_verified=True,
        )
        self.organizations = ("org-a",)
        self.grants = {
            "org-a": AccessGrant(
                roles=frozenset({"cliente_administrador"}),
                permissions=frozenset(
                    {
                        "users:invite",
                        "projects:grant_access",
                        "projects:read",
                    }
                ),
                modules=frozenset({"field", "darwincheck"}),
                project_ids=frozenset({"project-a"}),
            )
        }
        self.login_events: list[tuple[str, datetime]] = []

    def get_user(self, user_id: str) -> AuthenticatedUser | None:
        return self.user if user_id == self.user.id else None

    def find_user(self, provider: str, subject: str) -> AuthenticatedUser | None:
        if provider == "supabase" and subject == "subject-1":
            return self.user
        return None

    def organization_ids(self, user_id: str) -> tuple[str, ...]:
        return self.organizations if user_id == self.user.id else ()

    def resolve_access(self, user_id: str, organization_id: str) -> AccessGrant:
        if user_id != self.user.id or organization_id not in self.grants:
            raise PermissionError("Cross-organization access denied")
        return self.grants[organization_id]

    def record_login(self, user_id: str, at: datetime) -> None:
        self.login_events.append((user_id, at))


class FakeRepository:
    def __init__(self, clock: MutableClock) -> None:
        self.clock = clock
        self.sessions_by_hash: dict[str, SessionRecord] = {}
        self.sessions_by_id: dict[str, SessionRecord] = {}
        self.launches: dict[str, LaunchCodeRecord] = {}
        self.invitations: dict[str, InvitationRecord] = {}
        self.memberships: list[tuple[str, str, str]] = []
        self.project_access: list[tuple[str, str]] = []

    def create_session(self, record: SessionRecord, token_hash: str) -> None:
        self.sessions_by_hash[token_hash] = record
        self.sessions_by_id[record.id] = record

    def get_session_by_hash(self, token_hash: str) -> SessionRecord | None:
        return self.sessions_by_hash.get(token_hash)

    def get_session_by_id(self, session_id: str) -> SessionRecord | None:
        return self.sessions_by_id.get(session_id)

    def touch_session(self, session_id: str, at: datetime) -> None:
        return None

    def revoke_session(self, session_id: str, at: datetime, reason: str) -> None:
        pending = [session_id]
        revoked_ids: set[str] = set()
        while pending:
            current_id = pending.pop()
            if current_id in revoked_ids:
                continue
            revoked_ids.add(current_id)
            pending.extend(
                record.id
                for record in self.sessions_by_id.values()
                if record.parent_session_id == current_id
            )
        for current_id in revoked_ids:
            current = self.sessions_by_id[current_id]
            updated = replace(current, revoked_at=at)
            self.sessions_by_id[current_id] = updated
            for token_hash, record in tuple(self.sessions_by_hash.items()):
                if record.id == current_id:
                    self.sessions_by_hash[token_hash] = updated

    def revoke_all_sessions(self, user_id: str, at: datetime, reason: str) -> int:
        count = 0
        for session_id, record in tuple(self.sessions_by_id.items()):
            if record.user_id == user_id and record.revoked_at is None:
                self.revoke_session(session_id, at, reason)
                count += 1
        return count

    def create_launch_code(
        self, record: LaunchCodeRecord, code_hash: str
    ) -> None:
        self.launches[code_hash] = record

    def consume_launch_code(
        self, code_hash: str, module_code: str
    ) -> LaunchCodeRecord | None:
        record = self.launches.get(code_hash)
        if (
            record is None
            or record.used_at is not None
            or record.expires_at <= self.clock()
            or record.module_code != module_code
        ):
            return None
        used = replace(record, used_at=self.clock())
        self.launches[code_hash] = used
        return used

    def create_invitation(
        self, record: InvitationRecord, token_hash: str
    ) -> None:
        self.invitations[token_hash] = record

    def consume_invitation(
        self,
        token_hash: str,
        user_id: str,
        verified_email: str,
    ) -> InvitationRecord | None:
        record = self.invitations.get(token_hash)
        if (
            record is None
            or record.accepted_at is not None
            or record.revoked_at is not None
            or record.expires_at <= self.clock()
            or record.email != verified_email
        ):
            return None
        accepted = replace(record, accepted_at=self.clock())
        self.invitations[token_hash] = accepted
        return accepted

    def activate_membership(
        self, user_id: str, invitation: InvitationRecord
    ) -> None:
        self.memberships.append(
            (user_id, invitation.organization_id, invitation.role)
        )
        self.project_access.extend(
            (user_id, project_id) for project_id in invitation.project_ids
        )


class FakeVerifier:
    def __init__(self, claims: IdentityClaims) -> None:
        self.claims = claims
        self.calls = 0

    def verify(self, raw_identity_token: str) -> IdentityClaims:
        self.calls += 1
        if raw_identity_token != "valid-id-token":
            raise AuthenticationError("Invalid identity token")
        return self.claims


@pytest.fixture
def auth_stack():
    clock = MutableClock()
    directory = FakeDirectory()
    repository = FakeRepository(clock)
    sessions = SessionService(
        repository,
        directory,
        clock=clock,
        session_ttl=timedelta(hours=8),
        module_session_ttl=timedelta(hours=2),
    )
    launches = ModuleLaunchService(
        sessions,
        repository,
        RedirectPolicy(
            frozenset({"field.example.com", "darwin.example.com"})
        ),
        clock=clock,
        launch_ttl=timedelta(minutes=2),
    )
    return clock, directory, repository, sessions, launches


def test_one_central_session_opens_multiple_modules_without_new_login(
    auth_stack,
) -> None:
    _, _, _, sessions, launches = auth_stack
    platform = sessions.issue("user-1", "org-a", auth_method="supabase")

    field_code = launches.issue(
        platform.token,
        "field",
        "https://field.example.com/app",
        "project-a",
    )
    field = launches.exchange(field_code.code, "field")
    darwin_code = launches.issue(
        platform.token,
        "darwincheck",
        "https://darwin.example.com/app",
        "project-a",
    )
    darwin = launches.exchange(darwin_code.code, "darwincheck")

    assert field.context.user_id == darwin.context.user_id == "user-1"
    assert field.context.organization_id == darwin.context.organization_id == "org-a"
    assert field.context.session_id != darwin.context.session_id


def test_launch_code_is_single_use_and_expires(auth_stack) -> None:
    clock, _, _, sessions, launches = auth_stack
    platform = sessions.issue("user-1", "org-a", auth_method="supabase")
    used = launches.issue(
        platform.token, "field", "https://field.example.com/app"
    )
    launches.exchange(used.code, "field")
    with pytest.raises(SessionError):
        launches.exchange(used.code, "field")

    expired = launches.issue(
        platform.token, "field", "https://field.example.com/app"
    )
    clock.advance(timedelta(minutes=3))
    with pytest.raises(SessionError):
        launches.exchange(expired.code, "field")


def test_module_project_and_organization_access_are_enforced(auth_stack) -> None:
    _, _, _, sessions, launches = auth_stack
    platform = sessions.issue("user-1", "org-a", auth_method="supabase")
    with pytest.raises(ModuleAccessDenied):
        launches.issue(
            platform.token,
            "intelligence",
            "https://field.example.com/app",
        )
    with pytest.raises(ProjectAccessDenied):
        launches.issue(
            platform.token,
            "field",
            "https://field.example.com/app",
            "project-b",
        )
    with pytest.raises(PermissionError):
        sessions.issue("user-1", "org-b", auth_method="supabase")
    with pytest.raises(InvalidReturnUrl):
        launches.issue(
            platform.token,
            "field",
            "https://attacker.example/steal",
        )


def test_session_expiration_and_revocation(auth_stack) -> None:
    clock, _, _, sessions, _ = auth_stack
    issued = sessions.issue("user-1", "org-a", auth_method="supabase")
    sessions.revoke(issued.token)
    with pytest.raises(SessionError):
        sessions.validate(issued.token)

    fresh = sessions.issue("user-1", "org-a", auth_method="supabase")
    clock.advance(timedelta(hours=9))
    with pytest.raises(SessionExpired):
        sessions.validate(fresh.token)


def test_revoking_platform_session_also_revokes_module_children(
    auth_stack,
) -> None:
    _, _, _, sessions, launches = auth_stack
    platform = sessions.issue("user-1", "org-a", auth_method="supabase")
    code = launches.issue(
        platform.token,
        "field",
        "https://field.example.com/app",
        "project-a",
    )
    child = launches.exchange(code.code, "field")

    sessions.revoke(platform.token)

    with pytest.raises(SessionError):
        sessions.validate(child.token, expected_audience="field")


def test_verified_identity_starts_one_central_session(auth_stack) -> None:
    _, directory, _, sessions, _ = auth_stack
    verifier = FakeVerifier(
        IdentityClaims(
            provider="supabase",
            subject="subject-1",
            email="client@example.com",
            email_verified=True,
        )
    )
    issued = AuthService(verifier, directory, sessions).exchange(
        "valid-id-token"
    )
    assert issued.context.user_id == "user-1"
    assert verifier.calls == 1
    assert len(directory.login_events) == 1


def test_unverified_email_cannot_authenticate(auth_stack) -> None:
    _, directory, _, sessions, _ = auth_stack
    verifier = FakeVerifier(
        IdentityClaims(
            provider="supabase",
            subject="subject-1",
            email="client@example.com",
            email_verified=False,
        )
    )
    with pytest.raises(EmailVerificationRequired):
        AuthService(verifier, directory, sessions).exchange("valid-id-token")


def _inviter(repository: FakeRepository) -> SessionContext:
    return SessionContext(
        session_id="session-1",
        user_id="admin-1",
        organization_id="org-a",
        roles=frozenset({"cliente_administrador"}),
        permissions=frozenset(
            {"users:invite", "projects:grant_access"}
        ),
        modules=frozenset(),
        project_ids=frozenset({"project-a"}),
        audience="platform",
        started_at=repository.clock(),
        expires_at=repository.clock() + timedelta(hours=8),
    )


def test_invitation_is_single_use_email_bound_and_scoped(auth_stack) -> None:
    _, _, repository, _, _ = auth_stack
    service = InvitationService(repository)
    issued = service.create(
        _inviter(repository),
        "New.User@Example.com",
        "cliente_editor",
        ("project-a",),
    )
    with pytest.raises(InvitationError):
        service.accept(issued.token, "user-2", "other@example.com")

    accepted = service.accept(
        issued.token, "user-2", "new.user@example.com"
    )
    assert accepted.organization_id == "org-a"
    assert repository.memberships == [
        ("user-2", "org-a", "cliente_editor")
    ]
    assert repository.project_access == [("user-2", "project-a")]
    with pytest.raises(InvitationError):
        service.accept(
            issued.token, "user-2", "new.user@example.com"
        )


def test_client_admin_cannot_invite_privileged_role(auth_stack) -> None:
    _, _, repository, _, _ = auth_stack
    with pytest.raises(InvitationError):
        InvitationService(repository).create(
            _inviter(repository),
            "new@example.com",
            "administradora_biocore",
        )


def test_invitation_expires(auth_stack) -> None:
    clock, _, repository, _, _ = auth_stack
    service = InvitationService(repository, clock=clock)
    issued = service.create(
        _inviter(repository),
        "new@example.com",
        "cliente_lector",
    )
    clock.advance(timedelta(days=8))
    with pytest.raises(InvitationError):
        service.accept(issued.token, "user-2", "new@example.com")
