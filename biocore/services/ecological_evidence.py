"""Application rules for traceable, project-scoped ecological evidence."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, replace
from datetime import date, datetime, time, timezone
from pathlib import Path
from uuid import UUID, uuid4

from biocore.domain.ecological_evidence import (
    EcologicalEvidence,
    EvidenceFilters,
    EvidenceHistoryEntry,
    EvidenceMedia,
    EvidenceQualityFinding,
    EvidenceSource,
    EvidenceSummary,
    EvidenceType,
    IdentificationStatus,
    ProfessionalReviewStatus,
    TaxonomicGroup,
)
from biocore.integrations.inaturalist import INaturalistClient
from biocore.repositories.ecological_evidence import EcologicalEvidenceRepository
from biocore.repositories.projects import ProjectRepository
from biocore.security.authorization import UserContext, require_permission
from biocore.security.roles import Permission


ALLOWED_MEDIA_TYPES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}
MAX_MEDIA_BYTES = 15 * 1024 * 1024
MAX_MEDIA_PER_OPERATION = 10


class EvidenceValidationError(ValueError):
    """Raised when evidence is incomplete or internally inconsistent."""


class EvidenceNotFound(LookupError):
    """Raised when a record is outside the active organization or project."""


class EvidenceConflict(EvidenceValidationError):
    """Raised for duplicate media or external observations."""


@dataclass(frozen=True)
class EvidenceInput:
    observation_date: date
    taxonomic_group: TaxonomicGroup
    evidence_type: EvidenceType
    observation_method: str
    author_name: str
    license: str
    observation_time: time | None = None
    study_area_id: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    location_accuracy_m: float | None = None
    taxon_proposed: str | None = None
    scientific_name: str | None = None
    common_name: str | None = None
    identification_status: IdentificationStatus = IdentificationStatus.UNIDENTIFIED
    notes: str = ""


@dataclass(frozen=True)
class EvidenceUpload:
    filename: str
    content_type: str
    payload: bytes
    author_name: str
    license: str
    is_primary: bool = False


@dataclass(frozen=True)
class ProfessionalReviewInput:
    status: ProfessionalReviewStatus
    identification_status: IdentificationStatus
    scientific_name: str | None
    common_name: str | None
    notes: str


def _clean(
    value: object,
    label: str,
    *,
    maximum: int,
    required: bool = False,
) -> str:
    normalized = " ".join(str(value or "").split())
    if required and not normalized:
        raise EvidenceValidationError(f"{label} es obligatorio.")
    if len(normalized) > maximum:
        raise EvidenceValidationError(
            f"{label} no puede superar {maximum} caracteres."
        )
    return normalized


def _coordinates(
    latitude: float | None, longitude: float | None
) -> tuple[float | None, float | None]:
    if latitude is None and longitude is None:
        return None, None
    if latitude is None or longitude is None:
        raise EvidenceValidationError(
            "Latitud y longitud deben informarse juntas o dejarse ambas vacías."
        )
    try:
        parsed_latitude = float(latitude)
        parsed_longitude = float(longitude)
    except (TypeError, ValueError) as error:
        raise EvidenceValidationError(
            "Las coordenadas deben expresarse en grados decimales WGS84."
        ) from error
    if not -90 <= parsed_latitude <= 90 or not -180 <= parsed_longitude <= 180:
        raise EvidenceValidationError(
            "Las coordenadas están fuera del rango válido de latitud o longitud."
        )
    return parsed_latitude, parsed_longitude


class EcologicalEvidenceService:
    """Authorize, validate and audit every ecological-evidence operation."""

    def __init__(
        self,
        repository: EcologicalEvidenceRepository,
        projects: ProjectRepository,
        inaturalist: INaturalistClient,
    ) -> None:
        self._repository = repository
        self._projects = projects
        self._inaturalist = inaturalist

    def _project(self, context: UserContext, project_id: str):
        project = self._projects.get(context.organization_id, project_id)
        if project is None:
            raise EvidenceNotFound(
                "El proyecto no está disponible en la organización activa."
            )
        return project

    def _evidence(self, context: UserContext, evidence_id: str) -> EcologicalEvidence:
        evidence = self._repository.get(context.organization_id, evidence_id)
        if evidence is None:
            raise EvidenceNotFound(
                "La evidencia no existe o no pertenece a la organización activa."
            )
        self._project(context, evidence.project_id)
        return evidence

    def _history(
        self,
        context: UserContext,
        evidence_id: str,
        event_type: str,
        changes: dict[str, object],
    ) -> None:
        self._repository.append_history(
            EvidenceHistoryEntry(
                id=str(uuid4()),
                organization_id=context.organization_id,
                evidence_id=evidence_id,
                actor_user_id=context.user_id,
                event_type=event_type,
                changes=changes,
                created_at=datetime.now(timezone.utc),
            )
        )

    def validate(
        self,
        data: EvidenceInput,
        *,
        allow_professional_validation: bool = False,
    ) -> EvidenceInput:
        if data.observation_date > datetime.now(timezone.utc).date():
            raise EvidenceValidationError(
                "La fecha de observación no puede estar en el futuro."
            )
        latitude, longitude = _coordinates(data.latitude, data.longitude)
        accuracy = data.location_accuracy_m
        if accuracy is not None:
            try:
                accuracy = float(accuracy)
            except (TypeError, ValueError) as error:
                raise EvidenceValidationError(
                    "La precisión de ubicación debe expresarse en metros."
                ) from error
            if accuracy < 0:
                raise EvidenceValidationError(
                    "La precisión de ubicación no puede ser negativa."
                )
        proposed = _clean(data.taxon_proposed, "Taxón propuesto", maximum=220) or None
        scientific = _clean(data.scientific_name, "Nombre científico", maximum=220) or None
        common = _clean(data.common_name, "Nombre común", maximum=220) or None
        status = IdentificationStatus(data.identification_status)
        if (
            status == IdentificationStatus.PROFESSIONALLY_VALIDATED
            and not allow_professional_validation
        ):
            raise EvidenceValidationError(
                "La validación profesional solo puede registrarse mediante una revisión."
            )
        if status != IdentificationStatus.UNIDENTIFIED and not (proposed or scientific):
            raise EvidenceValidationError(
                "Indica el taxón propuesto o conserva el estado Sin identificar."
            )
        study_area_id = _clean(
            data.study_area_id, "Área de estudio", maximum=120
        ) or None
        if study_area_id:
            try:
                study_area_id = str(UUID(study_area_id))
            except ValueError as error:
                raise EvidenceValidationError(
                    "El área de estudio vinculada no tiene un identificador válido."
                ) from error
        return EvidenceInput(
            observation_date=data.observation_date,
            observation_time=data.observation_time,
            study_area_id=study_area_id,
            latitude=latitude,
            longitude=longitude,
            location_accuracy_m=accuracy,
            taxon_proposed=proposed,
            scientific_name=scientific,
            common_name=common,
            taxonomic_group=TaxonomicGroup(data.taxonomic_group),
            identification_status=status,
            evidence_type=EvidenceType(data.evidence_type),
            observation_method=_clean(
                data.observation_method,
                "Método de observación",
                maximum=180,
                required=True,
            ),
            notes=_clean(data.notes, "Notas", maximum=5000),
            author_name=_clean(
                data.author_name, "Autor u observador", maximum=220, required=True
            ),
            license=_clean(data.license, "Condición de uso", maximum=120, required=True),
        )

    def create(
        self,
        context: UserContext,
        project_id: str,
        data: EvidenceInput,
        uploads: tuple[EvidenceUpload, ...] = (),
    ) -> EcologicalEvidence:
        require_permission(context, Permission.EVIDENCE_WRITE)
        project = self._project(context, project_id)
        validated = self.validate(data)
        now = datetime.now(timezone.utc)
        evidence = EcologicalEvidence(
            id=str(uuid4()),
            organization_id=context.organization_id,
            project_id=project.id,
            study_area_id=validated.study_area_id,
            created_by_user_id=context.user_id,
            observation_date=validated.observation_date,
            observation_time=validated.observation_time,
            latitude=validated.latitude,
            longitude=validated.longitude,
            location_accuracy_m=validated.location_accuracy_m,
            taxon_proposed=validated.taxon_proposed,
            scientific_name=validated.scientific_name,
            common_name=validated.common_name,
            taxonomic_group=validated.taxonomic_group,
            identification_status=validated.identification_status,
            evidence_type=validated.evidence_type,
            observation_method=validated.observation_method,
            notes=validated.notes,
            source_type=EvidenceSource.BIOCORE,
            source_name="BioCore",
            source_url=None,
            external_id=None,
            license=validated.license,
            author_name=validated.author_name,
            professional_review_status=ProfessionalReviewStatus.NOT_REQUESTED,
            created_at=now,
            updated_at=now,
        )
        saved = self._repository.create(evidence)
        self._history(context, saved.id, "created", {"source_type": "biocore"})
        if uploads:
            saved = self.add_media(context, saved.id, uploads)
        return saved

    def update(
        self, context: UserContext, evidence_id: str, data: EvidenceInput
    ) -> EcologicalEvidence:
        require_permission(context, Permission.EVIDENCE_WRITE)
        current = self._evidence(context, evidence_id)
        if current.archived_at:
            raise EvidenceValidationError(
                "La evidencia archivada se conserva en modo de consulta."
            )
        validated = self.validate(
            data,
            allow_professional_validation=(
                current.identification_status
                == IdentificationStatus.PROFESSIONALLY_VALIDATED
                and data.identification_status
                == IdentificationStatus.PROFESSIONALLY_VALIDATED
            ),
        )
        editable = (
            "study_area_id",
            "observation_date",
            "observation_time",
            "latitude",
            "longitude",
            "location_accuracy_m",
            "taxon_proposed",
            "scientific_name",
            "common_name",
            "taxonomic_group",
            "identification_status",
            "evidence_type",
            "observation_method",
            "notes",
            "license",
            "author_name",
        )
        changes = {
            field: {
                "before": str(getattr(current, field) or ""),
                "after": str(getattr(validated, field) or ""),
            }
            for field in editable
            if getattr(current, field) != getattr(validated, field)
        }
        if not changes:
            return current
        updated = replace(
            current,
            **{field: getattr(validated, field) for field in editable},
            updated_at=datetime.now(timezone.utc),
        )
        saved = self._repository.update(updated)
        event = (
            "identification_changed"
            if any(name in changes for name in ("taxon_proposed", "scientific_name", "identification_status"))
            else "coordinates_changed"
            if any(name in changes for name in ("latitude", "longitude", "location_accuracy_m"))
            else "updated"
        )
        self._history(context, saved.id, event, changes)
        return saved

    def archive(self, context: UserContext, evidence_id: str) -> EcologicalEvidence:
        require_permission(context, Permission.EVIDENCE_WRITE)
        current = self._evidence(context, evidence_id)
        if current.archived_at:
            return current
        archived = replace(
            current,
            archived_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        saved = self._repository.update(archived)
        self._history(context, saved.id, "archived", {"archived": True})
        return saved

    def list(
        self,
        context: UserContext,
        project_id: str,
        filters: EvidenceFilters | None = None,
    ) -> tuple[EcologicalEvidence, ...]:
        require_permission(context, Permission.EVIDENCE_READ)
        project = self._project(context, project_id)
        return self._repository.list_for_project(
            context.organization_id, project.id, filters or EvidenceFilters()
        )

    def add_media(
        self,
        context: UserContext,
        evidence_id: str,
        uploads: tuple[EvidenceUpload, ...],
    ) -> EcologicalEvidence:
        require_permission(context, Permission.EVIDENCE_WRITE)
        evidence = self._evidence(context, evidence_id)
        if evidence.archived_at:
            raise EvidenceValidationError(
                "No se pueden agregar archivos a una evidencia archivada."
            )
        if not uploads or len(uploads) > MAX_MEDIA_PER_OPERATION:
            raise EvidenceValidationError(
                f"Adjunta entre 1 y {MAX_MEDIA_PER_OPERATION} fotografías por operación."
            )
        created: list[EvidenceMedia] = []
        uploaded_paths: list[str] = []
        for position, upload in enumerate(uploads, start=1):
            content_type = str(upload.content_type or "").casefold()
            if content_type not in ALLOWED_MEDIA_TYPES:
                raise EvidenceValidationError(
                    "Las fotografías deben estar en formato JPG, PNG o WEBP."
                )
            if not upload.payload or len(upload.payload) > MAX_MEDIA_BYTES:
                raise EvidenceValidationError(
                    "Cada fotografía debe contener datos y pesar como máximo 15 MB."
                )
            author = _clean(
                upload.author_name, "Autor de la fotografía", maximum=220, required=True
            )
            license_name = _clean(
                upload.license, "Licencia de la fotografía", maximum=120, required=True
            )
            digest = hashlib.sha256(upload.payload).hexdigest()
            if self._repository.media_hash_exists(
                context.organization_id, evidence.id, digest
            ):
                raise EvidenceConflict(
                    f"La fotografía {Path(upload.filename).name} ya está vinculada a esta evidencia."
                )
            media_id = str(uuid4())
            extension = ALLOWED_MEDIA_TYPES[content_type]
            storage_path = (
                f"{context.organization_id}/{evidence.project_id}/{evidence.id}/"
                f"{media_id}{extension}"
            )
            try:
                self._repository.upload_media(storage_path, upload.payload, content_type)
                uploaded_paths.append(storage_path)
                media = self._repository.create_media(
                    EvidenceMedia(
                        id=media_id,
                        organization_id=context.organization_id,
                        evidence_id=evidence.id,
                        storage_path=storage_path,
                        filename=Path(upload.filename).name or f"evidencia-{position}",
                        content_type=content_type,
                        size_bytes=len(upload.payload),
                        author_name=author,
                        license=license_name,
                        source_type=EvidenceSource.BIOCORE,
                        sha256=digest,
                        is_primary=upload.is_primary or (not evidence.media and position == 1),
                        metadata={"original_filename": Path(upload.filename).name},
                        created_at=datetime.now(timezone.utc),
                    )
                )
                created.append(media)
            except Exception:
                for path in uploaded_paths:
                    try:
                        self._repository.delete_media_object(path)
                    except Exception:
                        pass
                raise
        self._history(
            context,
            evidence.id,
            "media_added",
            {"media_ids": [item.id for item in created], "count": len(created)},
        )
        return self._evidence(context, evidence.id)

    def import_from_inaturalist(
        self, context: UserContext, project_id: str, identifier: str
    ) -> EcologicalEvidence:
        require_permission(context, Permission.EVIDENCE_WRITE)
        project = self._project(context, project_id)
        external = self._inaturalist.observation(identifier)
        if self._repository.external_id_exists(
            context.organization_id, EvidenceSource.INATURALIST, external.external_id
        ):
            raise EvidenceConflict(
                "Esta observación de iNaturalist ya fue referenciada por la organización."
            )
        now = datetime.now(timezone.utc)
        evidence = EcologicalEvidence(
            id=str(uuid4()),
            organization_id=context.organization_id,
            project_id=project.id,
            study_area_id=None,
            created_by_user_id=context.user_id,
            observation_date=external.observation_date,
            observation_time=external.observation_time,
            latitude=external.latitude,
            longitude=external.longitude,
            location_accuracy_m=external.location_accuracy_m,
            taxon_proposed=external.taxon_proposed,
            scientific_name=external.scientific_name,
            common_name=external.common_name,
            taxonomic_group=external.taxonomic_group,
            identification_status=external.identification_status,
            evidence_type=EvidenceType.OBSERVATION,
            observation_method="Registro externo referenciado desde iNaturalist",
            notes=(
                f"Calidad informada por iNaturalist: {external.quality_grade or 'no informada'}. "
                "Este estado externo no equivale a validación profesional BioCore."
            ),
            source_type=EvidenceSource.INATURALIST,
            source_name="iNaturalist",
            source_url=external.source_url,
            external_id=external.external_id,
            license=external.observation_license,
            author_name=external.observer_name,
            professional_review_status=ProfessionalReviewStatus.NOT_REQUESTED,
            created_at=now,
            updated_at=now,
        )
        saved = self._repository.create(evidence)
        for position, reference in enumerate(external.media, start=1):
            # External photographs remain references in this MVP. This avoids
            # copying media whose commercial reuse is restricted or uncertain.
            self._repository.create_media(
                EvidenceMedia(
                    id=str(uuid4()),
                    organization_id=context.organization_id,
                    evidence_id=saved.id,
                    storage_path=None,
                    filename=f"iNaturalist-{external.external_id}-{position}",
                    content_type=None,
                    size_bytes=None,
                    author_name=reference.author_name,
                    license=reference.license,
                    source_type=EvidenceSource.INATURALIST,
                    source_url=reference.url,
                    is_primary=position == 1,
                    metadata={
                        **reference.metadata,
                        "attribution": reference.attribution,
                        "license_warning": reference.license in {"", "no_informada", "none"}
                        or "nc" in reference.license.casefold(),
                    },
                    created_at=now,
                )
            )
        self._history(
            context,
            saved.id,
            "external_imported",
            {
                "source_type": EvidenceSource.INATURALIST.value,
                "external_id": external.external_id,
                "media_referenced": len(external.media),
                "files_copied": 0,
            },
        )
        return self._evidence(context, saved.id)

    def archive_media(
        self, context: UserContext, evidence_id: str, media_id: str
    ) -> EcologicalEvidence:
        require_permission(context, Permission.EVIDENCE_WRITE)
        evidence = self._evidence(context, evidence_id)
        media = next(
            (
                item
                for item in evidence.media
                if item.id == media_id and item.archived_at is None
            ),
            None,
        )
        if media is None:
            raise EvidenceNotFound(
                "La fotografía no existe o no pertenece a esta evidencia."
            )
        archived_at = datetime.now(timezone.utc)
        self._repository.archive_media(
            context.organization_id,
            evidence.id,
            media.id,
            archived_at,
        )
        self._history(
            context,
            evidence.id,
            "media_archived",
            {
                "media_id": media.id,
                "filename": media.filename,
                "storage_object_preserved": bool(media.storage_path),
            },
        )
        return self._evidence(context, evidence.id)

    def request_review(
        self, context: UserContext, evidence_id: str
    ) -> EcologicalEvidence:
        require_permission(context, Permission.EVIDENCE_WRITE)
        current = self._evidence(context, evidence_id)
        updated = replace(
            current,
            professional_review_status=ProfessionalReviewStatus.REQUESTED,
            identification_status=(
                IdentificationStatus.REVIEW_REQUIRED
                if current.identification_status
                != IdentificationStatus.PROFESSIONALLY_VALIDATED
                else current.identification_status
            ),
            updated_at=datetime.now(timezone.utc),
        )
        saved = self._repository.update(updated)
        self._history(context, saved.id, "review_requested", {"status": "requested"})
        return saved

    def review(
        self,
        context: UserContext,
        evidence_id: str,
        data: ProfessionalReviewInput,
    ) -> EcologicalEvidence:
        require_permission(context, Permission.EVIDENCE_REVIEW)
        current = self._evidence(context, evidence_id)
        status = ProfessionalReviewStatus(data.status)
        if status not in {
            ProfessionalReviewStatus.APPROVED,
            ProfessionalReviewStatus.CORRECTED,
            ProfessionalReviewStatus.UNCERTAIN,
        }:
            raise EvidenceValidationError(
                "La revisión debe aprobar, corregir o declarar incertidumbre."
            )
        scientific = _clean(data.scientific_name, "Nombre científico", maximum=220) or None
        common = _clean(data.common_name, "Nombre común", maximum=220) or None
        notes = _clean(
            data.notes, "Observaciones de revisión", maximum=5000, required=True
        )
        identification = IdentificationStatus(data.identification_status)
        if status in {
            ProfessionalReviewStatus.APPROVED,
            ProfessionalReviewStatus.CORRECTED,
        }:
            identification = IdentificationStatus.PROFESSIONALLY_VALIDATED
            if not scientific:
                raise EvidenceValidationError(
                    "Una validación profesional debe informar el nombre científico."
                )
        elif status == ProfessionalReviewStatus.UNCERTAIN:
            identification = IdentificationStatus.UNCERTAIN
        reviewed_at = datetime.now(timezone.utc)
        saved = self._repository.update(
            replace(
                current,
                scientific_name=scientific,
                common_name=common,
                identification_status=identification,
                professional_review_status=status,
                review_notes=notes,
                reviewed_by_user_id=context.user_id,
                reviewed_at=reviewed_at,
                updated_at=reviewed_at,
            )
        )
        self._history(
            context,
            saved.id,
            "professional_reviewed",
            {
                "review_status": status.value,
                "identification_status": identification.value,
                "scientific_name": scientific,
            },
        )
        return saved

    def history(
        self, context: UserContext, evidence_id: str
    ) -> tuple[EvidenceHistoryEntry, ...]:
        require_permission(context, Permission.EVIDENCE_READ)
        self._evidence(context, evidence_id)
        return self._repository.list_history(context.organization_id, evidence_id)

    def media_urls(
        self, context: UserContext, evidence_id: str
    ) -> tuple[tuple[EvidenceMedia, str], ...]:
        require_permission(context, Permission.EVIDENCE_READ)
        evidence = self._evidence(context, evidence_id)
        return tuple(
            (
                media,
                self._repository.signed_media_url(media.storage_path, expires_in=300)
                if media.storage_path
                else str(media.source_url or ""),
            )
            for media in evidence.media
            if media.archived_at is None
        )

    @staticmethod
    def quality_findings(
        evidence: EcologicalEvidence,
        peers: tuple[EcologicalEvidence, ...] = (),
    ) -> tuple[EvidenceQualityFinding, ...]:
        findings: list[EvidenceQualityFinding] = []
        if evidence.latitude is None or evidence.longitude is None:
            findings.append(
                EvidenceQualityFinding(
                    "coordinates_missing",
                    "warning",
                    "Faltan coordenadas.",
                    "coordinates",
                    "Latitud o longitud sin informar.",
                    "Una evidencia se considera georreferenciada solo cuando conserva ambas coordenadas WGS84.",
                    "Incorpora las coordenadas observadas o documenta por qué no están disponibles.",
                )
            )
        if evidence.source_type != EvidenceSource.BIOCORE and not evidence.source_url:
            findings.append(
                EvidenceQualityFinding(
                    "source_unknown",
                    "error",
                    "El registro externo no conserva su URL de origen.",
                    "source_url",
                    f"Fuente declarada: {evidence.source_name}; URL ausente.",
                    "Todo registro externo debe mantener un enlace verificable a su procedencia.",
                    "Completa la URL original antes de reutilizar este antecedente.",
                )
            )
        if evidence.identification_status in {
            IdentificationStatus.UNIDENTIFIED,
            IdentificationStatus.PROPOSED,
            IdentificationStatus.REVIEW_REQUIRED,
        }:
            findings.append(
                EvidenceQualityFinding(
                    "identification_pending",
                    "info",
                    "La identificación está pendiente de revisión profesional.",
                    "identification_status",
                    f"Estado actual: {evidence.identification_status.value}.",
                    "Los estados sin identificar, propuesto o requiere revisión no equivalen a una validación profesional.",
                    "Solicita revisión cuando existan antecedentes suficientes.",
                )
            )
        if not evidence.media:
            findings.append(
                EvidenceQualityFinding(
                    "media_missing",
                    "info",
                    "No hay fotografías vinculadas.",
                    "media",
                    "Número de fotografías activas: 0.",
                    "La regla alerta cuando un registro no conserva respaldo visual; no invalida por sí sola la observación.",
                    "Adjunta fotografías si existen y registra siempre autoría y licencia.",
                )
            )
        for media in evidence.media:
            if not media.author_name or media.author_name == "Autor no informado":
                findings.append(
                    EvidenceQualityFinding(
                        "media_author_missing",
                        "warning",
                        f"{media.filename} no informa autor.",
                        "author_name",
                        f"Archivo revisado: {media.filename}.",
                        "Cada fotografía debe conservar una atribución verificable.",
                        "Documenta el autor antes de publicar o reutilizar el archivo.",
                    )
                )
            if not media.license or media.license == "no_informada":
                findings.append(
                    EvidenceQualityFinding(
                        "media_license_missing",
                        "warning",
                        f"{media.filename} no informa licencia.",
                        "license",
                        f"Archivo revisado: {media.filename}; licencia ausente o no informada.",
                        "Una fotografía sin condición de uso documentada no se considera preparada para reutilización.",
                        "Confirma la licencia con el autor y regístrala antes de reutilizarla.",
                    )
                )
        if any(
            peer.id != evidence.id
            and peer.source_type == evidence.source_type
            and peer.external_id
            and peer.external_id == evidence.external_id
            for peer in peers
        ):
            findings.append(
                EvidenceQualityFinding(
                    "possible_duplicate",
                    "warning",
                    "Existe otro registro con el mismo identificador externo.",
                    "external_id",
                    f"Fuente: {evidence.source_type.value}; identificador: {evidence.external_id}.",
                    "Dos registros activos con la misma fuente y el mismo identificador se marcan como posible duplicado.",
                    "Compara la procedencia antes de conservar ambos registros.",
                )
            )
        return tuple(findings)

    @classmethod
    def summary(
        cls, evidence: tuple[EcologicalEvidence, ...]
    ) -> EvidenceSummary:
        taxa = {
            item.scientific_name or item.taxon_proposed
            for item in evidence
            if item.scientific_name or item.taxon_proposed
        }
        incomplete = sum(bool(cls.quality_findings(item, evidence)) for item in evidence)
        return EvidenceSummary(
            total=len(evidence),
            own_records=sum(item.source_type == EvidenceSource.BIOCORE for item in evidence),
            external_records=sum(item.source_type != EvidenceSource.BIOCORE for item in evidence),
            distinct_taxa=len(taxa),
            validated=sum(
                item.identification_status == IdentificationStatus.PROFESSIONALLY_VALIDATED
                for item in evidence
            ),
            pending_review=sum(
                item.professional_review_status
                in {
                    ProfessionalReviewStatus.REQUESTED,
                    ProfessionalReviewStatus.UNDER_REVIEW,
                }
                for item in evidence
            ),
            georeferenced=sum(
                item.latitude is not None and item.longitude is not None
                for item in evidence
            ),
            incomplete=incomplete,
        )
