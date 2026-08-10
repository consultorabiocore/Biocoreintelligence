"""Small, read-only iNaturalist API adapter for controlled imports."""

from __future__ import annotations

import re
from datetime import date, time
from typing import Any, Protocol

import requests

from biocore.domain.ecological_evidence import (
    ExternalMediaReference,
    ExternalObservation,
    IdentificationStatus,
    TaxonomicGroup,
)


INATURALIST_API = "https://api.inaturalist.org/v1"
OBSERVATION_ID = re.compile(
    r"^(?:https?://(?:www\.)?inaturalist(?:\.org|\.cl)/observations/)?(?P<id>\d+)(?:[/?#].*)?$",
    re.IGNORECASE,
)


class INaturalistError(RuntimeError):
    """Base error translated by the ecological-evidence UI."""


class INaturalistIdentifierError(INaturalistError):
    """Raised when a URL or observation ID cannot be interpreted."""


class INaturalistUnavailable(INaturalistError):
    """Raised when the optional public API cannot be reached."""


class INaturalistObservationNotFound(INaturalistError):
    """Raised when the public observation does not exist or is unavailable."""


class INaturalistClient(Protocol):
    def observation(self, identifier: str) -> ExternalObservation: ...


def observation_id(identifier: str) -> str:
    match = OBSERVATION_ID.fullmatch(str(identifier).strip())
    if not match:
        raise INaturalistIdentifierError(
            "Ingresa el número de la observación o su URL pública de iNaturalist."
        )
    return match.group("id")


def _date(value: object) -> date:
    text = str(value or "")[:10]
    if not text:
        raise INaturalistUnavailable("La observación externa no informa una fecha.")
    return date.fromisoformat(text)


def _time(value: object) -> time | None:
    text = str(value or "")
    if "T" not in text:
        return None
    try:
        return time.fromisoformat(text.split("T", 1)[1][:8])
    except ValueError:
        return None


def _coordinates(row: dict[str, Any]) -> tuple[float | None, float | None]:
    geojson = row.get("geojson") or {}
    coordinates = geojson.get("coordinates") or []
    if len(coordinates) >= 2:
        return float(coordinates[1]), float(coordinates[0])
    location = str(row.get("location") or "")
    if "," in location:
        latitude, longitude = location.split(",", 1)
        return float(latitude), float(longitude)
    return None, None


def _group(taxon: dict[str, Any]) -> TaxonomicGroup:
    iconic = str(taxon.get("iconic_taxon_name") or "").casefold()
    if iconic == "plantae":
        return TaxonomicGroup.FLORA
    if iconic == "fungi":
        return TaxonomicGroup.FUNGA
    if iconic == "animalia":
        return TaxonomicGroup.FAUNA
    return TaxonomicGroup.OTHER


def _license(value: object) -> str:
    normalized = str(value or "").strip().lower()
    return normalized or "no_informada"


def _photo_url(photo: dict[str, Any]) -> str:
    return str(photo.get("original_url") or photo.get("url") or "")


def observation_from_api(row: dict[str, Any]) -> ExternalObservation:
    taxon = dict(row.get("taxon") or {})
    user = dict(row.get("user") or {})
    observer = str(user.get("name") or user.get("login") or "Autor no informado")
    latitude, longitude = _coordinates(row)
    photos: list[ExternalMediaReference] = []
    for photo in row.get("observation_photos") or []:
        photo_row = dict((photo or {}).get("photo") or {})
        url = _photo_url(photo_row)
        if not url:
            continue
        license_code = _license(photo_row.get("license_code"))
        attribution = str(photo_row.get("attribution") or observer)
        photos.append(
            ExternalMediaReference(
                url=url,
                author_name=observer,
                license=license_code,
                attribution=attribution,
                metadata={
                    "native_photo_id": photo_row.get("id"),
                    "square_url": photo_row.get("url"),
                    "reuse_copied": False,
                },
            )
        )
    quality_grade = str(row.get("quality_grade") or "") or None
    scientific_name = str(taxon.get("name") or "").strip() or None
    common_name = str(taxon.get("preferred_common_name") or "").strip() or None
    return ExternalObservation(
        external_id=str(row["id"]),
        source_url=str(row.get("uri") or f"https://www.inaturalist.org/observations/{row['id']}"),
        observer_name=observer,
        observation_date=_date(row.get("observed_on") or row.get("time_observed_at")),
        observation_time=_time(row.get("time_observed_at")),
        latitude=latitude,
        longitude=longitude,
        location_accuracy_m=(
            float(row["positional_accuracy"])
            if row.get("positional_accuracy") is not None
            else None
        ),
        taxon_proposed=scientific_name,
        scientific_name=scientific_name,
        common_name=common_name,
        taxonomic_group=_group(taxon),
        # iNaturalist quality grades are external context, never a BioCore
        # professional validation.
        identification_status=(
            IdentificationStatus.REVIEWED
            if quality_grade == "research"
            else IdentificationStatus.PROPOSED
            if scientific_name
            else IdentificationStatus.UNIDENTIFIED
        ),
        observation_license=_license(row.get("license_code")),
        quality_grade=quality_grade,
        media=tuple(photos),
    )


class PublicINaturalistClient:
    """Use only documented public API endpoints; never scrape the website."""

    def __init__(self, *, timeout_seconds: float = 8.0) -> None:
        self._timeout = timeout_seconds

    def observation(self, identifier: str) -> ExternalObservation:
        native_id = observation_id(identifier)
        try:
            response = requests.get(
                f"{INATURALIST_API}/observations/{native_id}",
                timeout=self._timeout,
                headers={"Accept": "application/json", "User-Agent": "BioCore/1.0"},
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as error:
            raise INaturalistUnavailable(
                "iNaturalist no respondió. BioCore sigue disponible; inténtalo más tarde."
            ) from error
        rows = payload.get("results") or []
        if not rows:
            raise INaturalistObservationNotFound(
                "No encontramos una observación pública con ese identificador."
            )
        return observation_from_api(dict(rows[0]))
