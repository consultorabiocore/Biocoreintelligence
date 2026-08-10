"""Tenant-scoped persistence and private media for ecological evidence."""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Any, Protocol

from biocore.domain.ecological_evidence import (
    EcologicalEvidence,
    EvidenceFilters,
    EvidenceHistoryEntry,
    EvidenceMedia,
    EvidenceSource,
    EvidenceType,
    IdentificationStatus,
    ProfessionalReviewStatus,
    TaxonomicGroup,
)


ECOLOGICAL_EVIDENCE_BUCKET = "ecological-evidence"


class EcologicalEvidenceRepository(Protocol):
    def create(self, evidence: EcologicalEvidence) -> EcologicalEvidence: ...

    def update(self, evidence: EcologicalEvidence) -> EcologicalEvidence: ...

    def get(
        self, organization_id: str, evidence_id: str
    ) -> EcologicalEvidence | None: ...

    def list_for_project(
        self,
        organization_id: str,
        project_id: str,
        filters: EvidenceFilters,
        *,
        limit: int = 1000,
    ) -> tuple[EcologicalEvidence, ...]: ...

    def create_media(self, media: EvidenceMedia) -> EvidenceMedia: ...

    def archive_media(
        self,
        organization_id: str,
        evidence_id: str,
        media_id: str,
        archived_at: datetime,
    ) -> EvidenceMedia: ...

    def media_hash_exists(
        self, organization_id: str, evidence_id: str, sha256: str
    ) -> bool: ...

    def external_id_exists(
        self,
        organization_id: str,
        source_type: EvidenceSource,
        external_id: str,
    ) -> bool: ...

    def upload_media(
        self, storage_path: str, payload: bytes, content_type: str
    ) -> None: ...

    def delete_media_object(self, storage_path: str) -> None: ...

    def signed_media_url(self, storage_path: str, *, expires_in: int) -> str: ...

    def append_history(self, entry: EvidenceHistoryEntry) -> None: ...

    def list_history(
        self, organization_id: str, evidence_id: str
    ) -> tuple[EvidenceHistoryEntry, ...]: ...


def _parse_date(value: object) -> date:
    return value if isinstance(value, date) else date.fromisoformat(str(value)[:10])


def _parse_time(value: object) -> time | None:
    if value in (None, ""):
        return None
    if isinstance(value, time):
        return value
    return time.fromisoformat(str(value)[:8])


def _parse_datetime(value: object) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def media_from_row(row: dict[str, Any]) -> EvidenceMedia:
    return EvidenceMedia(
        id=str(row["id"]),
        organization_id=str(row["organization_id"]),
        evidence_id=str(row["evidence_id"]),
        storage_path=(str(row["storage_path"]) if row.get("storage_path") else None),
        filename=str(row.get("filename") or "evidencia"),
        content_type=(str(row["content_type"]) if row.get("content_type") else None),
        size_bytes=(int(row["size_bytes"]) if row.get("size_bytes") is not None else None),
        author_name=str(row.get("author_name") or "Autor no informado"),
        license=str(row.get("license") or "no_informada"),
        source_type=EvidenceSource(str(row.get("source_type") or "biocore")),
        source_url=(str(row["source_url"]) if row.get("source_url") else None),
        sha256=(str(row["sha256"]) if row.get("sha256") else None),
        is_primary=bool(row.get("is_primary", False)),
        metadata=dict(row.get("metadata") or {}),
        created_at=_parse_datetime(row.get("created_at")),
        archived_at=_parse_datetime(row.get("archived_at")),
    )


def evidence_from_row(row: dict[str, Any]) -> EcologicalEvidence:
    media_rows = row.get("ecological_evidence_media") or row.get("media") or []
    return EcologicalEvidence(
        id=str(row["id"]),
        organization_id=str(row["organization_id"]),
        project_id=str(row["project_id"]),
        study_area_id=(str(row["study_area_id"]) if row.get("study_area_id") else None),
        created_by_user_id=str(row["created_by_user_id"]),
        observation_date=_parse_date(row["observation_date"]),
        observation_time=_parse_time(row.get("observation_time")),
        latitude=(float(row["latitude"]) if row.get("latitude") is not None else None),
        longitude=(float(row["longitude"]) if row.get("longitude") is not None else None),
        location_accuracy_m=(
            float(row["location_accuracy_m"])
            if row.get("location_accuracy_m") is not None
            else None
        ),
        taxon_proposed=(str(row["taxon_proposed"]) if row.get("taxon_proposed") else None),
        scientific_name=(str(row["scientific_name"]) if row.get("scientific_name") else None),
        common_name=(str(row["common_name"]) if row.get("common_name") else None),
        taxonomic_group=TaxonomicGroup(str(row.get("taxonomic_group") or "other")),
        identification_status=IdentificationStatus(
            str(row.get("identification_status") or "unidentified")
        ),
        evidence_type=EvidenceType(str(row.get("evidence_type") or "observation")),
        observation_method=str(row.get("observation_method") or ""),
        notes=str(row.get("notes") or ""),
        source_type=EvidenceSource(str(row.get("source_type") or "biocore")),
        source_name=str(row.get("source_name") or "BioCore"),
        source_url=(str(row["source_url"]) if row.get("source_url") else None),
        external_id=(str(row["external_id"]) if row.get("external_id") else None),
        license=str(row.get("license") or "no_informada"),
        author_name=str(row.get("author_name") or "Autor no informado"),
        professional_review_status=ProfessionalReviewStatus(
            str(row.get("professional_review_status") or "not_requested")
        ),
        review_notes=str(row.get("review_notes") or ""),
        reviewed_by_user_id=(
            str(row["reviewed_by_user_id"]) if row.get("reviewed_by_user_id") else None
        ),
        reviewed_at=_parse_datetime(row.get("reviewed_at")),
        media=tuple(media_from_row(item) for item in media_rows),
        created_at=_parse_datetime(row.get("created_at")),
        updated_at=_parse_datetime(row.get("updated_at")),
        archived_at=_parse_datetime(row.get("archived_at")),
    )


def evidence_payload(evidence: EcologicalEvidence) -> dict[str, object]:
    return {
        "id": evidence.id,
        "organization_id": evidence.organization_id,
        "project_id": evidence.project_id,
        "study_area_id": evidence.study_area_id,
        "created_by_user_id": evidence.created_by_user_id,
        "observation_date": evidence.observation_date.isoformat(),
        "observation_time": (
            evidence.observation_time.isoformat() if evidence.observation_time else None
        ),
        "latitude": evidence.latitude,
        "longitude": evidence.longitude,
        "location_accuracy_m": evidence.location_accuracy_m,
        "taxon_proposed": evidence.taxon_proposed,
        "scientific_name": evidence.scientific_name,
        "common_name": evidence.common_name,
        "taxonomic_group": evidence.taxonomic_group.value,
        "identification_status": evidence.identification_status.value,
        "evidence_type": evidence.evidence_type.value,
        "observation_method": evidence.observation_method,
        "notes": evidence.notes,
        "source_type": evidence.source_type.value,
        "source_name": evidence.source_name,
        "source_url": evidence.source_url,
        "external_id": evidence.external_id,
        "license": evidence.license,
        "author_name": evidence.author_name,
        "professional_review_status": evidence.professional_review_status.value,
        "review_notes": evidence.review_notes,
        "reviewed_by_user_id": evidence.reviewed_by_user_id,
        "reviewed_at": evidence.reviewed_at.isoformat() if evidence.reviewed_at else None,
        "archived_at": evidence.archived_at.isoformat() if evidence.archived_at else None,
    }


def media_payload(media: EvidenceMedia) -> dict[str, object]:
    return {
        "id": media.id,
        "organization_id": media.organization_id,
        "evidence_id": media.evidence_id,
        "storage_path": media.storage_path,
        "filename": media.filename,
        "content_type": media.content_type,
        "size_bytes": media.size_bytes,
        "author_name": media.author_name,
        "license": media.license,
        "source_type": media.source_type.value,
        "source_url": media.source_url,
        "sha256": media.sha256,
        "is_primary": media.is_primary,
        "metadata": media.metadata,
        "archived_at": media.archived_at.isoformat() if media.archived_at else None,
    }


class SupabaseEcologicalEvidenceRepository:
    """Trusted server repository; every query includes the organization."""

    def __init__(self, client: Any) -> None:
        self._client = client

    def create(self, evidence: EcologicalEvidence) -> EcologicalEvidence:
        response = self._client.table("ecological_evidence").insert(
            evidence_payload(evidence)
        ).execute()
        rows = response.data or []
        return evidence_from_row(rows[0]) if rows else evidence

    def update(self, evidence: EcologicalEvidence) -> EcologicalEvidence:
        response = (
            self._client.table("ecological_evidence")
            .update(evidence_payload(evidence))
            .eq("id", evidence.id)
            .eq("organization_id", evidence.organization_id)
            .execute()
        )
        rows = response.data or []
        if not rows:
            raise LookupError("Evidence not found for organization")
        refreshed = evidence_from_row(rows[0])
        return self.get(evidence.organization_id, refreshed.id) or refreshed

    def get(self, organization_id: str, evidence_id: str) -> EcologicalEvidence | None:
        response = (
            self._client.table("ecological_evidence")
            .select("*, ecological_evidence_media(*)")
            .eq("id", evidence_id)
            .eq("organization_id", organization_id)
            .limit(1)
            .execute()
        )
        rows = response.data or []
        return evidence_from_row(rows[0]) if rows else None

    def list_for_project(
        self,
        organization_id: str,
        project_id: str,
        filters: EvidenceFilters,
        *,
        limit: int = 1000,
    ) -> tuple[EcologicalEvidence, ...]:
        query = (
            self._client.table("ecological_evidence")
            .select("*, ecological_evidence_media(*)")
            .eq("organization_id", organization_id)
            .eq("project_id", project_id)
        )
        if not filters.include_archived:
            query = query.is_("archived_at", "null")
        if filters.taxonomic_group:
            query = query.eq("taxonomic_group", filters.taxonomic_group.value)
        if filters.identification_status:
            query = query.eq("identification_status", filters.identification_status.value)
        if filters.source_type:
            query = query.eq("source_type", filters.source_type.value)
        if filters.review_status:
            query = query.eq("professional_review_status", filters.review_status.value)
        if filters.date_from:
            query = query.gte("observation_date", filters.date_from.isoformat())
        if filters.date_to:
            query = query.lte("observation_date", filters.date_to.isoformat())
        response = (
            query.order("observation_date", desc=True)
            .order("created_at", desc=True)
            .limit(max(1, min(limit, 2000)))
            .execute()
        )
        return tuple(evidence_from_row(row) for row in (response.data or []))

    def create_media(self, media: EvidenceMedia) -> EvidenceMedia:
        response = self._client.table("ecological_evidence_media").insert(
            media_payload(media)
        ).execute()
        rows = response.data or []
        return media_from_row(rows[0]) if rows else media

    def archive_media(
        self,
        organization_id: str,
        evidence_id: str,
        media_id: str,
        archived_at: datetime,
    ) -> EvidenceMedia:
        response = (
            self._client.table("ecological_evidence_media")
            .update({"archived_at": archived_at.isoformat()})
            .eq("id", media_id)
            .eq("evidence_id", evidence_id)
            .eq("organization_id", organization_id)
            .is_("archived_at", "null")
            .execute()
        )
        rows = response.data or []
        if not rows:
            raise LookupError("Evidence media not found for organization")
        return media_from_row(rows[0])

    def media_hash_exists(
        self, organization_id: str, evidence_id: str, sha256: str
    ) -> bool:
        response = (
            self._client.table("ecological_evidence_media")
            .select("id")
            .eq("organization_id", organization_id)
            .eq("evidence_id", evidence_id)
            .eq("sha256", sha256)
            .is_("archived_at", "null")
            .limit(1)
            .execute()
        )
        return bool(response.data or [])

    def external_id_exists(
        self,
        organization_id: str,
        source_type: EvidenceSource,
        external_id: str,
    ) -> bool:
        response = (
            self._client.table("ecological_evidence")
            .select("id")
            .eq("organization_id", organization_id)
            .eq("source_type", source_type.value)
            .eq("external_id", external_id)
            .is_("archived_at", "null")
            .limit(1)
            .execute()
        )
        return bool(response.data or [])

    def upload_media(
        self, storage_path: str, payload: bytes, content_type: str
    ) -> None:
        self._client.storage.from_(ECOLOGICAL_EVIDENCE_BUCKET).upload(
            storage_path,
            payload,
            {"content-type": content_type, "upsert": "false"},
        )

    def delete_media_object(self, storage_path: str) -> None:
        self._client.storage.from_(ECOLOGICAL_EVIDENCE_BUCKET).remove([storage_path])

    def signed_media_url(self, storage_path: str, *, expires_in: int) -> str:
        response = self._client.storage.from_(
            ECOLOGICAL_EVIDENCE_BUCKET
        ).create_signed_url(storage_path, expires_in)
        if isinstance(response, dict):
            return str(response.get("signedURL") or response.get("signedUrl") or "")
        return ""

    def append_history(self, entry: EvidenceHistoryEntry) -> None:
        self._client.table("ecological_evidence_history").insert(
            {
                "id": entry.id,
                "organization_id": entry.organization_id,
                "evidence_id": entry.evidence_id,
                "actor_user_id": entry.actor_user_id,
                "event_type": entry.event_type,
                "changes": entry.changes,
                "created_at": entry.created_at.isoformat(),
            }
        ).execute()

    def list_history(
        self, organization_id: str, evidence_id: str
    ) -> tuple[EvidenceHistoryEntry, ...]:
        response = (
            self._client.table("ecological_evidence_history")
            .select("*")
            .eq("organization_id", organization_id)
            .eq("evidence_id", evidence_id)
            .order("created_at", desc=True)
            .execute()
        )
        return tuple(
            EvidenceHistoryEntry(
                id=str(row["id"]),
                organization_id=str(row["organization_id"]),
                evidence_id=str(row["evidence_id"]),
                actor_user_id=str(row["actor_user_id"]),
                event_type=str(row["event_type"]),
                changes=dict(row.get("changes") or {}),
                created_at=_parse_datetime(row["created_at"]) or datetime.utcnow(),
            )
            for row in (response.data or [])
        )
