from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

from biocore.domain.mycofield import ObservationPrivacy
from biocore.security.authorization import AuthorizationError, UserContext
from biocore.security.roles import Role
from biocore.services.mycofield import (
    MycoFieldConflictError,
    MycoFieldInput,
    MycoFieldProjectNotFound,
    MycoFieldService,
    MycoFieldValidationError,
    PhotoUpload,
)


class FakeProjectRepository:
    def get(self, organization_id, project_id):
        if organization_id == "org-a" and project_id == "project-a":
            return SimpleNamespace(id="project-a", name="Bosque A")
        return None


class FakeObservationRepository:
    def __init__(self) -> None:
        self.saved = []
        self.uploads = {}
        self.deleted = []

    def create(self, observation):
        self.saved.append(observation)
        return observation

    def update_photos(self, observation):
        return observation

    def sample_code_exists(self, organization_id, project_id, sample_code):
        return any(
            item.organization_id == organization_id
            and item.project_id == project_id
            and item.sample_code.casefold() == sample_code.casefold()
            for item in self.saved
        )

    def list_for_project(
        self, organization_id, project_id, viewer_user_id, *, limit=500
    ):
        return tuple(
            item
            for item in reversed(self.saved)
            if item.organization_id == organization_id
            and item.project_id == project_id
            and (
                item.privacy != ObservationPrivacy.PRIVATE
                or item.created_by_user_id == viewer_user_id
            )
        )[:limit]

    def upload_photo(self, storage_path, payload, content_type):
        self.uploads[storage_path] = (payload, content_type)

    def delete_photo(self, storage_path):
        self.deleted.append(storage_path)
        self.uploads.pop(storage_path, None)

    def signed_photo_url(self, storage_path, *, expires_in):
        return f"https://signed.invalid/{storage_path}?ttl={expires_in}"


def _input(**changes) -> MycoFieldInput:
    values = {
        "sample_code": "bio-001",
        "observed_on": date(2026, 8, 1),
        "latitude": -36.82,
        "longitude": -73.03,
        "privacy": ObservationPrivacy.BLURRED,
        "tentative_name": "Por determinar",
        "substrate": "Madera muerta",
        "habitat": "Bosque nativo",
        "method": "Búsqueda activa",
        "effort": "2 personas · 60 minutos",
        "observable_traits": ("Poros",),
        "notes": "Cambio de color observado.",
    }
    values.update(changes)
    return MycoFieldInput(**values)


def _service():
    observations = FakeObservationRepository()
    return MycoFieldService(observations, FakeProjectRepository()), observations


def test_editor_creates_project_scoped_observation_with_private_evidence() -> None:
    service, repository = _service()
    context = UserContext("user-a", "org-a", frozenset({Role.CLIENT_EDITOR}))

    saved = service.create(
        context,
        "project-a",
        _input(),
        (
            PhotoUpload("../frente.JPG", "image/jpeg", b"photo-bytes"),
        ),
    )

    assert saved.organization_id == "org-a"
    assert saved.project_id == "project-a"
    assert saved.created_by_user_id == "user-a"
    assert saved.sample_code == "BIO-001"
    assert saved.map_latitude == -36.82
    assert saved.map_longitude == -73.03
    assert len(saved.photos) == 1
    assert saved.photos[0].filename == "frente.JPG"
    assert saved.photos[0].storage_path.startswith(
        "org-a/project-a/"
    )
    assert repository.saved == [saved]


def test_private_observation_never_exposes_map_coordinates() -> None:
    service, _ = _service()
    context = UserContext("user-a", "org-a", frozenset({Role.CLIENT_EDITOR}))

    saved = service.create(
        context,
        "project-a",
        _input(privacy=ObservationPrivacy.PRIVATE),
    )

    assert saved.map_latitude is None
    assert saved.map_longitude is None


def test_cross_organization_project_is_rejected_before_upload() -> None:
    service, repository = _service()
    context = UserContext("user-b", "org-b", frozenset({Role.CLIENT_EDITOR}))

    with pytest.raises(MycoFieldProjectNotFound):
        service.create(
            context,
            "project-a",
            _input(),
            (PhotoUpload("evidence.jpg", "image/jpeg", b"safe"),),
        )

    assert not repository.saved
    assert not repository.uploads


def test_reader_can_list_but_cannot_create() -> None:
    service, _ = _service()
    reader = UserContext("reader", "org-a", frozenset({Role.CLIENT_READER}))

    assert service.list_observations(reader, "project-a") == ()
    with pytest.raises(AuthorizationError):
        service.create(reader, "project-a", _input())


def test_duplicate_sample_code_is_rejected_per_project() -> None:
    service, _ = _service()
    context = UserContext("user-a", "org-a", frozenset({Role.CLIENT_EDITOR}))
    service.create(context, "project-a", _input())

    with pytest.raises(MycoFieldConflictError):
        service.create(context, "project-a", _input(sample_code="BIO-001"))


@pytest.mark.parametrize(
    "changes",
    [
        {"sample_code": "!"},
        {"latitude": 91},
        {"longitude": 181},
        {"observed_on": date(2099, 1, 1)},
        {"habitat": ""},
    ],
)
def test_invalid_field_data_is_explained(changes) -> None:
    service, _ = _service()

    with pytest.raises(MycoFieldValidationError):
        service.validate(_input(**changes))


def test_photo_validation_happens_before_any_upload() -> None:
    service, repository = _service()
    context = UserContext("user-a", "org-a", frozenset({Role.CLIENT_EDITOR}))

    with pytest.raises(MycoFieldValidationError):
        service.create(
            context,
            "project-a",
            _input(),
            (PhotoUpload("unsafe.svg", "image/svg+xml", b"<svg/>"),),
        )

    assert not repository.saved
    assert not repository.uploads


def test_private_observations_are_visible_only_to_creator() -> None:
    service, _ = _service()
    creator = UserContext("user-a", "org-a", frozenset({Role.CLIENT_EDITOR}))
    colleague = UserContext("user-b", "org-a", frozenset({Role.CLIENT_READER}))
    service.create(
        creator,
        "project-a",
        _input(privacy=ObservationPrivacy.PRIVATE),
    )

    assert len(service.list_observations(creator, "project-a")) == 1
    assert service.list_observations(colleague, "project-a") == ()
