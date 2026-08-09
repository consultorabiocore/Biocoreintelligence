"""Auditable monitoring workflow for BioCore Intelligence."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from typing import Protocol
from uuid import uuid4

from biocore.domain.intelligence import (
    IntelligenceFinding,
    IntelligenceRun,
    SatelliteMetric,
    SatelliteSnapshot,
)
from biocore.repositories.intelligence import IntelligenceRunRepository
from biocore.repositories.projects import ProjectRepository
from biocore.security.authorization import UserContext, require_permission
from biocore.security.roles import Permission


class SatelliteProvider(Protocol):
    @property
    def configured(self) -> bool: ...

    def analyze(
        self,
        coordinates: list[list[float]],
        baseline_year: int,
        *,
        today: date | None = None,
    ) -> SatelliteSnapshot: ...


class IntelligenceValidationError(ValueError):
    pass


class IntelligenceProjectNotFound(LookupError):
    pass


def parse_polygon_geojson(payload: bytes) -> tuple[dict[str, object], list[list[float]]]:
    if not payload:
        raise IntelligenceValidationError("Selecciona un archivo GeoJSON.")
    if len(payload) > 5 * 1024 * 1024:
        raise IntelligenceValidationError("El GeoJSON supera el límite de 5 MB.")
    try:
        document = json.loads(payload.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise IntelligenceValidationError(
            "El archivo no contiene un GeoJSON válido."
        ) from error
    geometry = document
    if document.get("type") == "FeatureCollection":
        features = document.get("features") or []
        if not features:
            raise IntelligenceValidationError("El GeoJSON no contiene polígonos.")
        geometry = features[0].get("geometry") or {}
    elif document.get("type") == "Feature":
        geometry = document.get("geometry") or {}
    geometry_type = geometry.get("type")
    raw_coordinates = geometry.get("coordinates")
    if geometry_type == "MultiPolygon":
        raw_coordinates = raw_coordinates[0] if raw_coordinates else None
        geometry_type = "Polygon"
    if geometry_type != "Polygon" or not raw_coordinates:
        raise IntelligenceValidationError(
            "BioCore Intelligence requiere un polígono GeoJSON."
        )
    ring = raw_coordinates[0]
    if not isinstance(ring, list) or len(ring) < 4 or len(ring) > 2000:
        raise IntelligenceValidationError(
            "El polígono debe tener entre 4 y 2.000 vértices."
        )
    coordinates: list[list[float]] = []
    for position, coordinate in enumerate(ring, start=1):
        if not isinstance(coordinate, list) or len(coordinate) < 2:
            raise IntelligenceValidationError(
                f"El vértice {position} no tiene longitud y latitud."
            )
        try:
            longitude, latitude = float(coordinate[0]), float(coordinate[1])
        except (TypeError, ValueError) as error:
            raise IntelligenceValidationError(
                f"El vértice {position} contiene valores no numéricos."
            ) from error
        if not -180 <= longitude <= 180 or not -90 <= latitude <= 90:
            raise IntelligenceValidationError(
                f"El vértice {position} está fuera del rango WGS84."
            )
        coordinates.append([longitude, latitude])
    if coordinates[0] != coordinates[-1]:
        coordinates.append(coordinates[0])
    normalized = {"type": "Polygon", "coordinates": [coordinates]}
    return normalized, coordinates


def _finding(metric: SatelliteMetric, image_count: int) -> IntelligenceFinding:
    change = metric.relative_change_percent
    confidence = "media" if image_count >= 3 else "baja"
    limitation = (
        f"Resolución {metric.resolution}; el promedio del polígono puede ocultar "
        "variación local y no determina por sí solo una causa."
    )
    if change is None:
        return IntelligenceFinding(
            dimension=metric.label,
            classification="dato faltante",
            observed="No fue posible calcular una comparación porcentual.",
            rule="La comparación requiere valores actual y de línea base válidos.",
            explanation="No se generó una inferencia con información incompleta.",
            confidence="no aplicable",
            limitation=limitation,
            recommendation="Revisar cobertura temporal y disponibilidad de la fuente.",
        )
    magnitude = abs(change)
    classification = "comparación estable"
    recommendation = "Mantener el seguimiento periódico y contrastar con terreno."
    if magnitude >= 20:
        classification = "cambio marcado"
        recommendation = "Revisar la zona en mapa y contrastar con campaña o evidencia de terreno."
    elif magnitude >= 10:
        classification = "cambio moderado"
        recommendation = "Comparar con fechas intermedias y antecedentes del proyecto."
    return IntelligenceFinding(
        dimension=metric.label,
        classification=classification,
        observed=f"Variación calculada de {change:+.1f}% respecto de la línea base.",
        rule="Cambio marcado ≥20%; moderado ≥10%; estable <10% en valor absoluto.",
        explanation=(
            "La clasificación describe la magnitud de la comparación, no su causa "
            "ni un incumplimiento."
        ),
        confidence=confidence,
        limitation=limitation,
        recommendation=recommendation,
    )


class IntelligenceService:
    def __init__(
        self,
        runs: IntelligenceRunRepository,
        projects: ProjectRepository,
        provider: SatelliteProvider,
    ) -> None:
        self._runs = runs
        self._projects = projects
        self._provider = provider

    @property
    def provider_configured(self) -> bool:
        return self._provider.configured

    def _project(self, context: UserContext, project_id: str):
        project = self._projects.get(context.organization_id, project_id)
        if project is None:
            raise IntelligenceProjectNotFound(
                "El proyecto no está disponible en la organización activa."
            )
        return project

    def run(
        self,
        context: UserContext,
        project_id: str,
        geojson_payload: bytes,
        baseline_year: int,
    ) -> IntelligenceRun:
        require_permission(context, Permission.INTELLIGENCE_WRITE)
        project = self._project(context, project_id)
        current_year = date.today().year
        if baseline_year < 2017 or baseline_year >= current_year:
            raise IntelligenceValidationError(
                f"La línea base debe estar entre 2017 y {current_year - 1}."
            )
        geometry, coordinates = parse_polygon_geojson(geojson_payload)
        snapshot = self._provider.analyze(coordinates, baseline_year)
        findings = tuple(
            _finding(metric, snapshot.recent_image_count)
            for metric in snapshot.metrics
        )
        run = IntelligenceRun(
            id=str(uuid4()),
            organization_id=context.organization_id,
            project_id=project.id,
            created_by_user_id=context.user_id,
            geometry=geometry,
            baseline_year=baseline_year,
            current_period=snapshot.current_period,
            baseline_period=snapshot.baseline_period,
            metrics=tuple(metric.as_dict() for metric in snapshot.metrics),
            findings=tuple(finding.as_dict() for finding in findings),
            provider_version=snapshot.provider_version,
            evidence={
                "recent_image_count": snapshot.recent_image_count,
                "baseline_image_count": snapshot.baseline_image_count,
                "mean_cloud_percent": snapshot.mean_cloud_percent,
            },
            created_at=datetime.now(timezone.utc),
        )
        return self._runs.create(run)

    def list_runs(
        self, context: UserContext, project_id: str, *, limit: int = 50
    ) -> tuple[IntelligenceRun, ...]:
        require_permission(context, Permission.INTELLIGENCE_READ)
        project = self._project(context, project_id)
        return self._runs.list_for_project(
            context.organization_id, project.id, limit=limit
        )
