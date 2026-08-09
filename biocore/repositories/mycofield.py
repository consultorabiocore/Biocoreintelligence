"""Tenant-scoped persistence and private evidence storage for MycoField."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Protocol

from biocore.domain.mycofield import (
    MycoFieldObservation,
    MycoFieldPhoto,
    ObservationPrivacy,
)


EVIDENCE_BUCKET = "mycofield-evidence"


class MycoFieldRepository(Protocol):
    def create(self, observation: MycoFieldObservation) -> MycoFieldObservation:
        """Persist one observation in its trusted organization and project."""

    def update_photos(
        self, observation: MycoFieldObservation
    ) -> MycoFieldObservation:
        """Persist evidence metadata after private object uploads."""

    def sample_code_exists(
        self, organization_id: str, project_id: str, sample_code: str
    ) -> bool:
        """Check project-level sample-code uniqueness."""

    def list_for_project(
        self,
        organization_id: str,
        project_id: str,
        viewer_user_id: str,
        *,
        limit: int = 500,
    ) -> tuple[MycoFieldObservation, ...]:
        """List visible observations for one project."""

    def upload_photo(
        self,
        storage_path: str,
        payload: bytes,
        content_type: str,
    ) -> None:
        """Upload one object to the private evidence bucket."""

    def delete_photo(self, storage_path: str) -> None:
        """Remove an uploaded object during transactional compensation."""

    def signed_photo_url(self, storage_path: str, *, expires_in: int) -> str:
        """Return a short-lived URL for an authorized evidence object."""


def _parse_datetime(value: object) -> datetime:
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


def observation_from_row(row: dict[str, Any]) -> MycoFieldObservation:
    photo_rows = row.get("photos") or []
    return MycoFieldObservation(
        id=str(row["id"]),
        organization_id=str(row["organization_id"]),
        project_id=str(row["project_id"]),
        created_by_user_id=str(row["created_by_user_id"]),
        sample_code=str(row["sample_code"]),
        observed_on=date.fromisoformat(str(row["observed_on"])[:10]),
        latitude=float(row["latitude"]),
        longitude=float(row["longitude"]),
        map_latitude=(
            float(row["map_latitude"])
            if row.get("map_latitude") is not None
            else None
        ),
        map_longitude=(
            float(row["map_longitude"])
            if row.get("map_longitude") is not None
            else None
        ),
        privacy=ObservationPrivacy(str(row.get("privacy") or "private")),
        tentative_name=str(row.get("tentative_name") or "Por determinar"),
        substrate=str(row.get("substrate") or ""),
        habitat=str(row.get("habitat") or ""),
        method=str(row.get("method") or ""),
        effort=str(row.get("effort") or ""),
        observable_traits=tuple(str(item) for item in (row.get("observable_traits") or [])),
        notes=str(row.get("notes") or ""),
        photos=tuple(
            MycoFieldPhoto(
                storage_path=str(item["storage_path"]),
                filename=str(item["filename"]),
                content_type=str(item["content_type"]),
                size_bytes=int(item["size_bytes"]),
            )
            for item in photo_rows
        ),
        created_at=_parse_datetime(row["created_at"]),
        updated_at=_parse_datetime(row["updated_at"]),
    )


def observation_payload(observation: MycoFieldObservation) -> dict[str, object]:
    return {
        "id": observation.id,
        "organization_id": observation.organization_id,
        "project_id": observation.project_id,
        "created_by_user_id": observation.created_by_user_id,
        "sample_code": observation.sample_code,
        "observed_on": observation.observed_on.isoformat(),
        "latitude": observation.latitude,
        "longitude": observation.longitude,
        "map_latitude": observation.map_latitude,
        "map_longitude": observation.map_longitude,
        "privacy": observation.privacy.value,
        "tentative_name": observation.tentative_name,
        "substrate": observation.substrate,
        "habitat": observation.habitat,
        "method": observation.method,
        "effort": observation.effort,
        "observable_traits": list(observation.observable_traits),
        "notes": observation.notes,
        "photos": [photo.as_dict() for photo in observation.photos],
        "created_at": observation.created_at.isoformat(),
        "updated_at": observation.updated_at.isoformat(),
    }


class SupabaseMycoFieldRepository:
    """Trusted-server repository with explicit tenant filters."""

    def __init__(self, client: Any) -> None:
        self._client = client

    def create(self, observation: MycoFieldObservation) -> MycoFieldObservation:
        response = (
            self._client.table("mycofield_observations")
            .insert(observation_payload(observation))
            .execute()
        )
        rows = response.data or []
        return observation_from_row(rows[0]) if rows else observation

    def update_photos(
        self, observation: MycoFieldObservation
    ) -> MycoFieldObservation:
        response = (
            self._client.table("mycofield_observations")
            .update({"photos": [photo.as_dict() for photo in observation.photos]})
            .eq("id", observation.id)
            .eq("organization_id", observation.organization_id)
            .eq("project_id", observation.project_id)
            .execute()
        )
        rows = response.data or []
        return observation_from_row(rows[0]) if rows else observation

    def sample_code_exists(
        self, organization_id: str, project_id: str, sample_code: str
    ) -> bool:
        response = (
            self._client.table("mycofield_observations")
            .select("id")
            .eq("organization_id", organization_id)
            .eq("project_id", project_id)
            .ilike("sample_code", sample_code)
            .limit(1)
            .execute()
        )
        return bool(response.data or [])

    def list_for_project(
        self,
        organization_id: str,
        project_id: str,
        viewer_user_id: str,
        *,
        limit: int = 500,
    ) -> tuple[MycoFieldObservation, ...]:
        response = (
            self._client.table("mycofield_observations")
            .select("*")
            .eq("organization_id", organization_id)
            .eq("project_id", project_id)
            .order("observed_on", desc=True)
            .limit(max(1, min(limit, 2000)))
            .execute()
        )
        rows = (
            row
            for row in (response.data or [])
            if row.get("privacy") != ObservationPrivacy.PRIVATE.value
            or str(row.get("created_by_user_id")) == viewer_user_id
        )
        return tuple(observation_from_row(row) for row in rows)

    def upload_photo(
        self,
        storage_path: str,
        payload: bytes,
        content_type: str,
    ) -> None:
        self._client.storage.from_(EVIDENCE_BUCKET).upload(
            storage_path,
            payload,
            {"content-type": content_type, "upsert": "false"},
        )

    def delete_photo(self, storage_path: str) -> None:
        self._client.storage.from_(EVIDENCE_BUCKET).remove([storage_path])

    def signed_photo_url(self, storage_path: str, *, expires_in: int) -> str:
        response = self._client.storage.from_(EVIDENCE_BUCKET).create_signed_url(
            storage_path,
            expires_in,
        )
        if isinstance(response, dict):
            return str(response.get("signedURL") or response.get("signedUrl") or "")
        return ""
