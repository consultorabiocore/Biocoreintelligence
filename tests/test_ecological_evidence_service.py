from __future__ import annotations

from dataclasses import replace
from datetime import date
from types import SimpleNamespace

import pytest

from biocore.domain.ecological_evidence import (
    EvidenceFilters,
    EvidenceSource,
    EvidenceType,
    ExternalMediaReference,
    ExternalObservation,
    IdentificationStatus,
    ProfessionalReviewStatus,
    TaxonomicGroup,
)
from biocore.integrations.inaturalist import INaturalistUnavailable
from biocore.security.authorization import AuthorizationError, UserContext
from biocore.security.roles import Role
from biocore.services.ecological_evidence import (
    EcologicalEvidenceService,
    EvidenceConflict,
    EvidenceInput,
    EvidenceNotFound,
    EvidenceUpload,
    EvidenceValidationError,
    ProfessionalReviewInput,
)


class FakeProjectRepository:
    def get(self, organization_id, project_id):
        if organization_id == "org-a" and project_id == "project-a":
            return SimpleNamespace(id="project-a", name="Bosque A")
        return None


class FakeEvidenceRepository:
    def __init__(self) -> None:
        self.records = {}
        self.uploads = {}
        self.history_rows = []

    def create(self, evidence):
        self.records[evidence.id] = evidence
        return evidence

    def update(self, evidence):
        if evidence.id not in self.records:
            raise LookupError
        self.records[evidence.id] = evidence
        return evidence

    def get(self, organization_id, evidence_id):
        record = self.records.get(evidence_id)
        return record if record and record.organization_id == organization_id else None

    def list_for_project(self, organization_id, project_id, filters, *, limit=1000):
        rows = [
            row
            for row in self.records.values()
            if row.organization_id == organization_id
            and row.project_id == project_id
            and (filters.include_archived or row.archived_at is None)
            and (not filters.taxonomic_group or row.taxonomic_group == filters.taxonomic_group)
            and (not filters.identification_status or row.identification_status == filters.identification_status)
            and (not filters.source_type or row.source_type == filters.source_type)
            and (not filters.review_status or row.professional_review_status == filters.review_status)
        ]
        return tuple(rows[:limit])

    def create_media(self, media):
        record = self.records[media.evidence_id]
        self.records[media.evidence_id] = replace(record, media=(*record.media, media))
        return media

    def archive_media(self, organization_id, evidence_id, media_id, archived_at):
        record = self.get(organization_id, evidence_id)
        media = next(item for item in record.media if item.id == media_id)
        archived = replace(media, archived_at=archived_at)
        self.records[evidence_id] = replace(
            record,
            media=tuple(archived if item.id == media_id else item for item in record.media),
        )
        return archived

    def media_hash_exists(self, organization_id, evidence_id, sha256):
        record = self.get(organization_id, evidence_id)
        return bool(record and any(item.sha256 == sha256 for item in record.media))

    def external_id_exists(self, organization_id, source_type, external_id):
        return any(
            row.organization_id == organization_id
            and row.source_type == source_type
            and row.external_id == external_id
            and row.archived_at is None
            for row in self.records.values()
        )

    def upload_media(self, storage_path, payload, content_type):
        self.uploads[storage_path] = (payload, content_type)

    def delete_media_object(self, storage_path):
        self.uploads.pop(storage_path, None)

    def signed_media_url(self, storage_path, *, expires_in):
        return f"https://signed.invalid/{storage_path}?ttl={expires_in}"

    def append_history(self, entry):
        self.history_rows.append(entry)

    def list_history(self, organization_id, evidence_id):
        return tuple(
            row
            for row in reversed(self.history_rows)
            if row.organization_id == organization_id and row.evidence_id == evidence_id
        )


class FakeINaturalist:
    def observation(self, identifier):
        return ExternalObservation(
            external_id="12345",
            source_url="https://www.inaturalist.org/observations/12345",
            observer_name="Loreto Campos",
            observation_date=date(2026, 7, 2),
            observation_time=None,
            latitude=-36.82,
            longitude=-73.03,
            location_accuracy_m=12,
            taxon_proposed="Cyttaria espinosae",
            scientific_name="Cyttaria espinosae",
            common_name="Digueñe",
            taxonomic_group=TaxonomicGroup.FUNGA,
            identification_status=IdentificationStatus.REVIEWED,
            observation_license="cc-by-nc",
            quality_grade="research",
            media=(
                ExternalMediaReference(
                    url="https://static.inaturalist.org/photo.jpg",
                    author_name="Loreto Campos",
                    license="cc-by-nc",
                    attribution="(c) Loreto Campos, CC BY-NC",
                ),
            ),
        )


class FailingINaturalist:
    def observation(self, identifier):
        raise INaturalistUnavailable("Servicio externo temporalmente no disponible.")


def _input(**changes):
    values = {
        "observation_date": date(2026, 8, 1),
        "taxonomic_group": TaxonomicGroup.FUNGA,
        "evidence_type": EvidenceType.OBSERVATION,
        "observation_method": "Búsqueda activa",
        "author_name": "Loreto Campos",
        "license": "Todos los derechos reservados",
        "latitude": -36.82,
        "longitude": -73.03,
        "taxon_proposed": "Cyttaria sp.",
        "identification_status": IdentificationStatus.PROPOSED,
        "notes": "Observado sobre Nothofagus.",
    }
    values.update(changes)
    return EvidenceInput(**values)


def _service(client=None):
    repository = FakeEvidenceRepository()
    return (
        EcologicalEvidenceService(
            repository,
            FakeProjectRepository(),
            client or FakeINaturalist(),
        ),
        repository,
    )


EDITOR = UserContext("user-a", "org-a", frozenset({Role.CLIENT_EDITOR}))
READER = UserContext("reader-a", "org-a", frozenset({Role.CLIENT_READER}))
SPECIALIST = UserContext("specialist", "org-a", frozenset({Role.BIOCORE_SPECIALIST}))


def test_editor_creates_traceable_project_evidence() -> None:
    service, repository = _service()

    saved = service.create(EDITOR, "project-a", _input())

    assert saved.organization_id == "org-a"
    assert saved.project_id == "project-a"
    assert saved.source_type == EvidenceSource.BIOCORE
    assert saved.scientific_name is None
    assert repository.history_rows[-1].event_type == "created"


def test_cross_organization_project_is_rejected() -> None:
    service, repository = _service()
    outsider = UserContext("user-b", "org-b", frozenset({Role.CLIENT_EDITOR}))

    with pytest.raises(EvidenceNotFound):
        service.create(outsider, "project-a", _input())

    assert not repository.records


def test_reader_can_list_but_cannot_create_or_archive() -> None:
    service, _ = _service()
    saved = service.create(EDITOR, "project-a", _input())

    assert service.list(READER, "project-a") == (saved,)
    with pytest.raises(AuthorizationError):
        service.create(READER, "project-a", _input())
    with pytest.raises(AuthorizationError):
        service.archive(READER, saved.id)


@pytest.mark.parametrize(
    "changes",
    [
        {"latitude": 91},
        {"longitude": 181},
        {"latitude": None, "longitude": -73.03},
        {"observation_date": date(2099, 1, 1)},
        {"observation_method": ""},
        {"study_area_id": "area-escrita-manualmente"},
        {"identification_status": IdentificationStatus.PROFESSIONALLY_VALIDATED},
    ],
)
def test_invalid_evidence_is_explained(changes) -> None:
    service, _ = _service()

    with pytest.raises(EvidenceValidationError):
        service.validate(_input(**changes))


def test_multiple_private_photos_keep_author_license_and_hash() -> None:
    service, repository = _service()
    saved = service.create(
        EDITOR,
        "project-a",
        _input(),
        (
            EvidenceUpload("front.jpg", "image/jpeg", b"front", "Loreto", "CC BY 4.0", True),
            EvidenceUpload("back.png", "image/png", b"back", "Loreto", "CC BY 4.0"),
        ),
    )

    assert len(saved.media) == 2
    assert len(repository.uploads) == 2
    assert all(item.author_name == "Loreto" for item in saved.media)
    assert all(item.license == "CC BY 4.0" for item in saved.media)
    assert all(item.storage_path.startswith("org-a/project-a/") for item in saved.media)


def test_duplicate_photo_is_rejected_without_second_upload() -> None:
    service, repository = _service()
    saved = service.create(
        EDITOR,
        "project-a",
        _input(),
        (EvidenceUpload("photo.jpg", "image/jpeg", b"same", "Loreto", "CC BY 4.0"),),
    )

    with pytest.raises(EvidenceConflict):
        service.add_media(
            EDITOR,
            saved.id,
            (EvidenceUpload("copy.jpg", "image/jpeg", b"same", "Loreto", "CC BY 4.0"),),
        )

    assert len(repository.uploads) == 1


def test_photo_archival_is_logical_and_audited() -> None:
    service, repository = _service()
    saved = service.create(
        EDITOR,
        "project-a",
        _input(),
        (EvidenceUpload("photo.jpg", "image/jpeg", b"safe", "Loreto", "CC BY 4.0"),),
    )

    updated = service.archive_media(EDITOR, saved.id, saved.media[0].id)

    assert updated.media[0].archived_at is not None
    assert len(repository.uploads) == 1
    assert repository.history_rows[-1].event_type == "media_archived"


def test_edit_and_archive_are_audited_without_physical_delete() -> None:
    service, repository = _service()
    saved = service.create(EDITOR, "project-a", _input())

    edited = service.update(
        EDITOR,
        saved.id,
        _input(latitude=-36.9, longitude=-73.1, notes="Ubicación revisada."),
    )
    archived = service.archive(EDITOR, edited.id)

    assert edited.latitude == -36.9
    assert archived.archived_at is not None
    assert repository.get("org-a", saved.id) is archived
    assert {row.event_type for row in repository.history_rows} >= {
        "created",
        "coordinates_changed",
        "archived",
    }


def test_inaturalist_import_keeps_attribution_license_and_external_reference() -> None:
    service, repository = _service()

    saved = service.import_from_inaturalist(EDITOR, "project-a", "12345")

    assert saved.source_type == EvidenceSource.INATURALIST
    assert saved.author_name == "Loreto Campos"
    assert saved.license == "cc-by-nc"
    assert saved.identification_status == IdentificationStatus.REVIEWED
    assert len(saved.media) == 1
    assert saved.media[0].storage_path is None
    assert saved.media[0].source_url.startswith("https://static.inaturalist.org/")
    assert saved.media[0].metadata["license_warning"] is True
    assert not repository.uploads


def test_duplicate_inaturalist_observation_is_rejected() -> None:
    service, _ = _service()
    service.import_from_inaturalist(EDITOR, "project-a", "12345")

    with pytest.raises(EvidenceConflict):
        service.import_from_inaturalist(EDITOR, "project-a", "12345")


def test_external_failure_does_not_modify_biocore() -> None:
    service, repository = _service(FailingINaturalist())

    with pytest.raises(INaturalistUnavailable):
        service.import_from_inaturalist(EDITOR, "project-a", "12345")

    assert not repository.records
    assert not repository.uploads


def test_only_specialist_can_professionally_validate() -> None:
    service, repository = _service()
    saved = service.create(EDITOR, "project-a", _input())
    service.request_review(EDITOR, saved.id)
    review = ProfessionalReviewInput(
        status=ProfessionalReviewStatus.APPROVED,
        identification_status=IdentificationStatus.REVIEWED,
        scientific_name="Cyttaria espinosae",
        common_name="Digueñe",
        notes="Se revisaron caracteres diagnósticos documentados.",
    )

    with pytest.raises(AuthorizationError):
        service.review(EDITOR, saved.id, review)
    reviewed = service.review(SPECIALIST, saved.id, review)

    assert reviewed.identification_status == IdentificationStatus.PROFESSIONALLY_VALIDATED
    assert reviewed.reviewed_by_user_id == "specialist"
    assert repository.history_rows[-1].event_type == "professional_reviewed"


def test_quality_summary_is_deterministic_and_not_an_ecological_index() -> None:
    service, _ = _service()
    incomplete = service.create(
        EDITOR,
        "project-a",
        _input(
            latitude=None,
            longitude=None,
            taxon_proposed=None,
            identification_status=IdentificationStatus.UNIDENTIFIED,
        ),
    )
    complete = service.create(EDITOR, "project-a", _input())

    findings = service.quality_findings(incomplete, (incomplete, complete))
    summary = service.summary((incomplete, complete))

    assert {item.code for item in findings} >= {
        "coordinates_missing",
        "identification_pending",
        "media_missing",
    }
    assert summary.total == 2
    assert summary.distinct_taxa == 1
    assert summary.incomplete == 2
