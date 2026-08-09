from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from biocore.domain.intelligence import SatelliteMetric, SatelliteSnapshot
from biocore.security.authorization import AuthorizationError, UserContext
from biocore.security.roles import Role
from biocore.services.intelligence import (
    IntelligenceProjectNotFound,
    IntelligenceService,
    IntelligenceValidationError,
    parse_polygon_geojson,
)


POLYGON = {
    "type": "Feature",
    "properties": {"name": "Área A"},
    "geometry": {
        "type": "Polygon",
        "coordinates": [[[-73.1, -36.9], [-73.0, -36.9], [-73.0, -36.8], [-73.1, -36.9]]],
    },
}


class FakeProjectRepository:
    def get(self, organization_id, project_id):
        if organization_id == "org-a" and project_id == "project-a":
            return SimpleNamespace(id="project-a", name="Bosque A")
        return None


class FakeRunRepository:
    def __init__(self) -> None:
        self.saved = []

    def create(self, run):
        self.saved.append(run)
        return run

    def list_for_project(self, organization_id, project_id, *, limit=50):
        return tuple(
            run
            for run in reversed(self.saved)
            if run.organization_id == organization_id and run.project_id == project_id
        )[:limit]


class FakeProvider:
    configured = True

    def __init__(self) -> None:
        self.calls = []

    def analyze(self, coordinates, baseline_year, *, today=None):
        self.calls.append((coordinates, baseline_year))
        return SatelliteSnapshot(
            metrics=(
                SatelliteMetric(
                    code="ndvi",
                    label="NDVI",
                    current=0.44,
                    baseline=0.55,
                    unit="índice",
                    source="Sentinel-2 SR",
                    resolution="30 m",
                ),
            ),
            current_period="2026-05-01 / 2026-08-01",
            baseline_period="2024-05-01 / 2024-08-01",
            recent_image_count=5,
            baseline_image_count=7,
            mean_cloud_percent=12.5,
            provider_version="fake-v1",
        )


def _payload(value=POLYGON) -> bytes:
    return json.dumps(value).encode("utf-8")


def _service():
    runs = FakeRunRepository()
    provider = FakeProvider()
    return IntelligenceService(runs, FakeProjectRepository(), provider), runs, provider


def test_geojson_parser_normalizes_polygon_and_closes_ring() -> None:
    document = {
        "type": "Polygon",
        "coordinates": [[[-73.1, -36.9], [-73.0, -36.9], [-73.0, -36.8], [-73.1, -36.8]]],
    }
    geometry, coordinates = parse_polygon_geojson(_payload(document))
    assert geometry["type"] == "Polygon"
    assert coordinates[0] == coordinates[-1]
    assert len(coordinates) == 5


@pytest.mark.parametrize(
    "document",
    [
        {"type": "Point", "coordinates": [-73, -36]},
        {"type": "FeatureCollection", "features": []},
        {"type": "Polygon", "coordinates": [[[200, -36], [201, -36], [201, -35], [200, -36]]]},
    ],
)
def test_geojson_parser_rejects_unsupported_or_unsafe_geometry(document) -> None:
    with pytest.raises(IntelligenceValidationError):
        parse_polygon_geojson(_payload(document))


def test_specialist_run_is_persisted_with_sources_and_explainable_finding() -> None:
    service, runs, provider = _service()
    context = UserContext("user-a", "org-a", frozenset({Role.BIOCORE_SPECIALIST}))
    run = service.run(context, "project-a", _payload(), 2024)
    assert run.organization_id == "org-a"
    assert run.project_id == "project-a"
    assert run.created_by_user_id == "user-a"
    assert run.provider_version == "fake-v1"
    assert run.evidence["recent_image_count"] == 5
    assert run.metrics[0]["source"] == "Sentinel-2 SR"
    assert run.findings[0]["classification"] == "cambio marcado"
    assert "no su causa" in run.findings[0]["explanation"]
    assert runs.saved == [run]
    assert provider.calls[0][1] == 2024


def test_reader_can_view_history_but_cannot_start_monitoring() -> None:
    service, _, _ = _service()
    reader = UserContext("reader", "org-a", frozenset({Role.CLIENT_READER}))
    assert service.list_runs(reader, "project-a") == ()
    with pytest.raises(AuthorizationError):
        service.run(reader, "project-a", _payload(), 2024)


def test_cross_organization_project_is_rejected_before_provider_call() -> None:
    service, runs, provider = _service()
    context = UserContext("user-b", "org-b", frozenset({Role.BIOCORE_SPECIALIST}))
    with pytest.raises(IntelligenceProjectNotFound):
        service.run(context, "project-a", _payload(), 2024)
    assert not provider.calls
    assert not runs.saved


def test_baseline_year_must_be_supported_and_historical() -> None:
    service, _, provider = _service()
    context = UserContext("user-a", "org-a", frozenset({Role.BIOCORE_SPECIALIST}))
    with pytest.raises(IntelligenceValidationError):
        service.run(context, "project-a", _payload(), 2016)
    assert not provider.calls
