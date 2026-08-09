"""Application service for project-scoped MycoField observations."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from uuid import uuid4

from biocore.domain.mycofield import (
    MycoFieldObservation,
    MycoFieldPhoto,
    ObservationPrivacy,
)
from biocore.repositories.mycofield import MycoFieldRepository
from biocore.repositories.projects import ProjectRepository
from biocore.security.authorization import UserContext, require_permission
from biocore.security.roles import Permission


SAMPLE_CODE_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{1,63}$")
ALLOWED_PHOTO_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
MAX_PHOTO_BYTES = 10 * 1024 * 1024
MAX_PHOTOS = 6


class MycoFieldValidationError(ValueError):
    """Raised when a field record is incomplete or unsafe."""


class MycoFieldConflictError(MycoFieldValidationError):
    """Raised when a sample code already exists inside the project."""


class MycoFieldProjectNotFound(LookupError):
    """Raised when the selected project is not in the active organization."""


@dataclass(frozen=True)
class PhotoUpload:
    filename: str
    content_type: str
    payload: bytes


@dataclass(frozen=True)
class MycoFieldInput:
    sample_code: str
    observed_on: date
    latitude: float
    longitude: float
    privacy: ObservationPrivacy
    tentative_name: str
    substrate: str
    habitat: str
    method: str
    effort: str
    observable_traits: tuple[str, ...] = ()
    notes: str = ""


def _text(value: str, label: str, *, maximum: int, required: bool = True) -> str:
    normalized = " ".join(str(value).split())
    if required and not normalized:
        raise MycoFieldValidationError(f"{label} es obligatorio.")
    if len(normalized) > maximum:
        raise MycoFieldValidationError(
            f"{label} no puede superar {maximum} caracteres."
        )
    return normalized


def _coordinates(latitude: float, longitude: float) -> tuple[float, float]:
    try:
        parsed_latitude = float(latitude)
        parsed_longitude = float(longitude)
    except (TypeError, ValueError) as error:
        raise MycoFieldValidationError(
            "Las coordenadas deben estar expresadas en grados decimales WGS84."
        ) from error
    if not -90 <= parsed_latitude <= 90 or not -180 <= parsed_longitude <= 180:
        raise MycoFieldValidationError(
            "Las coordenadas están fuera del rango válido de latitud o longitud."
        )
    return parsed_latitude, parsed_longitude


def _map_coordinates(
    latitude: float, longitude: float, privacy: ObservationPrivacy
) -> tuple[float | None, float | None]:
    if privacy == ObservationPrivacy.PRIVATE:
        return None, None
    if privacy == ObservationPrivacy.BLURRED:
        return round(latitude, 2), round(longitude, 2)
    return latitude, longitude


class MycoFieldService:
    """Validate, authorize and preserve MycoField records and evidence."""

    def __init__(
        self,
        observations: MycoFieldRepository,
        projects: ProjectRepository,
    ) -> None:
        self._observations = observations
        self._projects = projects

    def _project(self, context: UserContext, project_id: str):
        project = self._projects.get(context.organization_id, project_id)
        if project is None:
            raise MycoFieldProjectNotFound(
                "El proyecto no está disponible en la organización activa."
            )
        return project

    def validate(self, data: MycoFieldInput) -> MycoFieldInput:
        sample_code = data.sample_code.strip().upper()
        if not SAMPLE_CODE_PATTERN.fullmatch(sample_code):
            raise MycoFieldValidationError(
                "El código de muestra debe tener 2 a 64 caracteres y usar letras, "
                "números, punto, guion, barra o guion bajo."
            )
        latitude, longitude = _coordinates(data.latitude, data.longitude)
        observed_on = data.observed_on
        if observed_on > datetime.now(timezone.utc).date():
            raise MycoFieldValidationError(
                "La fecha del hallazgo no puede estar en el futuro."
            )
        traits = tuple(
            dict.fromkeys(
                _text(item, "Cada rasgo", maximum=100)
                for item in data.observable_traits
            )
        )
        return MycoFieldInput(
            sample_code=sample_code,
            observed_on=observed_on,
            latitude=latitude,
            longitude=longitude,
            privacy=ObservationPrivacy(data.privacy),
            tentative_name=_text(
                data.tentative_name or "Por determinar",
                "El nombre tentativo",
                maximum=180,
            ),
            substrate=_text(data.substrate, "El sustrato", maximum=120),
            habitat=_text(data.habitat, "El hábitat", maximum=500),
            method=_text(data.method, "El método", maximum=120),
            effort=_text(data.effort, "El esfuerzo", maximum=120),
            observable_traits=traits,
            notes=_text(data.notes, "Las notas", maximum=3000, required=False),
        )

    def _validated_photos(self, photos: tuple[PhotoUpload, ...]) -> tuple[PhotoUpload, ...]:
        if len(photos) > MAX_PHOTOS:
            raise MycoFieldValidationError(
                f"Puedes adjuntar hasta {MAX_PHOTOS} fotografías por registro."
            )
        validated: list[PhotoUpload] = []
        for photo in photos:
            content_type = photo.content_type.casefold()
            if content_type not in ALLOWED_PHOTO_TYPES:
                raise MycoFieldValidationError(
                    "Las fotografías deben estar en formato JPG, PNG o WEBP."
                )
            if not photo.payload:
                raise MycoFieldValidationError("Una de las fotografías está vacía.")
            if len(photo.payload) > MAX_PHOTO_BYTES:
                raise MycoFieldValidationError(
                    "Cada fotografía debe pesar como máximo 10 MB."
                )
            validated.append(
                PhotoUpload(
                    filename=Path(photo.filename).name or "evidencia",
                    content_type=content_type,
                    payload=photo.payload,
                )
            )
        return tuple(validated)

    def create(
        self,
        context: UserContext,
        project_id: str,
        data: MycoFieldInput,
        photos: tuple[PhotoUpload, ...] = (),
    ) -> MycoFieldObservation:
        require_permission(context, Permission.FIELD_WRITE)
        project = self._project(context, project_id)
        validated = self.validate(data)
        validated_photos = self._validated_photos(photos)
        if self._observations.sample_code_exists(
            context.organization_id, project.id, validated.sample_code
        ):
            raise MycoFieldConflictError(
                "Ya existe una observación con ese código en el proyecto."
            )
        map_latitude, map_longitude = _map_coordinates(
            validated.latitude, validated.longitude, validated.privacy
        )
        now = datetime.now(timezone.utc)
        observation_id = str(uuid4())
        uploaded: list[MycoFieldPhoto] = []
        for position, photo in enumerate(validated_photos, start=1):
            extension = ALLOWED_PHOTO_TYPES[photo.content_type]
            storage_path = (
                f"{context.organization_id}/{project.id}/{observation_id}/"
                f"{position:02d}-{uuid4().hex}{extension}"
            )
            try:
                self._observations.upload_photo(
                    storage_path, photo.payload, photo.content_type
                )
            except Exception:
                for uploaded_photo in uploaded:
                    try:
                        self._observations.delete_photo(uploaded_photo.storage_path)
                    except Exception:
                        pass
                raise
            uploaded.append(
                MycoFieldPhoto(
                    storage_path=storage_path,
                    filename=photo.filename,
                    content_type=photo.content_type,
                    size_bytes=len(photo.payload),
                )
            )
        observation = MycoFieldObservation(
            id=observation_id,
            organization_id=context.organization_id,
            project_id=project.id,
            created_by_user_id=context.user_id,
            sample_code=validated.sample_code,
            observed_on=validated.observed_on,
            latitude=validated.latitude,
            longitude=validated.longitude,
            map_latitude=map_latitude,
            map_longitude=map_longitude,
            privacy=validated.privacy,
            tentative_name=validated.tentative_name,
            substrate=validated.substrate,
            habitat=validated.habitat,
            method=validated.method,
            effort=validated.effort,
            observable_traits=validated.observable_traits,
            notes=validated.notes,
            photos=tuple(uploaded),
            created_at=now,
            updated_at=now,
        )
        try:
            return self._observations.create(observation)
        except Exception:
            for uploaded_photo in uploaded:
                try:
                    self._observations.delete_photo(uploaded_photo.storage_path)
                except Exception:
                    pass
            raise

    def list_observations(
        self, context: UserContext, project_id: str, *, limit: int = 500
    ) -> tuple[MycoFieldObservation, ...]:
        require_permission(context, Permission.FIELD_READ)
        project = self._project(context, project_id)
        return self._observations.list_for_project(
            context.organization_id,
            project.id,
            context.user_id,
            limit=limit,
        )

    def evidence_urls(
        self, context: UserContext, observation: MycoFieldObservation
    ) -> tuple[tuple[MycoFieldPhoto, str], ...]:
        require_permission(context, Permission.FIELD_READ)
        self._project(context, observation.project_id)
        if observation.organization_id != context.organization_id:
            raise MycoFieldProjectNotFound(
                "La observación no pertenece a la organización activa."
            )
        if (
            observation.privacy == ObservationPrivacy.PRIVATE
            and observation.created_by_user_id != context.user_id
        ):
            return ()
        return tuple(
            (
                photo,
                self._observations.signed_photo_url(
                    photo.storage_path, expires_in=300
                ),
            )
            for photo in observation.photos
        )
