from __future__ import annotations

from datetime import datetime, timezone

from biocore.domain.intelligence import IntelligenceRun
from biocore.modules.intelligence.reporting import (
    REPORT_VERSION,
    build_intelligence_pdf,
)


def _run() -> IntelligenceRun:
    return IntelligenceRun(
        id="run-auditable",
        organization_id="org-a",
        project_id="project-a",
        created_by_user_id="user-a",
        geometry={
            "type": "Polygon",
            "coordinates": [[[-73.1, -36.9], [-73.0, -36.9], [-73.0, -36.8], [-73.1, -36.9]]],
        },
        baseline_year=2024,
        current_period="2026-05-01 / 2026-08-01",
        baseline_period="2024-05-01 / 2024-08-01",
        metrics=(
            {
                "code": "ndvi",
                "label": "NDVI",
                "current": 0.42,
                "baseline": 0.51,
                "unit": "índice",
                "source": "Copernicus Data Space · Sentinel-2 L2A",
                "resolution": "20 m",
                "relative_change_percent": -17.6,
            },
        ),
        findings=(
            {
                "dimension": "NDVI",
                "classification": "cambio moderado",
                "observed": "Variación calculada de -17,6%.",
                "rule": "Moderado desde 10%.",
                "explanation": "La comparación no determina su causa.",
                "confidence": "media",
                "limitation": "El promedio puede ocultar variación local.",
                "recommendation": "Contrastar con terreno.",
            },
        ),
        provider_version="copernicus-cdse-sentinel-2-l2a-v2",
        evidence={
            "provider": "Copernicus Data Space Ecosystem",
            "collection": "Sentinel-2 L2A",
            "composite_rule": "least-cloud mosaic",
            "recent_image_count": 4,
            "baseline_image_count": 5,
            "mean_cloud_percent": 12.4,
            "current_valid_pixel_samples": 100,
            "baseline_valid_pixel_samples": 110,
            "data_nature": "observed_and_calculated",
        },
        created_at=datetime(2026, 8, 21, 12, 0, tzinfo=timezone.utc),
    )


def test_executive_and_technical_reports_are_valid_versioned_pdfs() -> None:
    executive = build_intelligence_pdf(
        _run(), project_name="Laja", project_code="LAJA-01"
    )
    technical = build_intelligence_pdf(
        _run(), project_name="Laja", project_code="LAJA-01", technical=True
    )

    assert executive.startswith(b"%PDF")
    assert technical.startswith(b"%PDF")
    assert len(technical) > len(executive)
    assert REPORT_VERSION == "biocore-intelligence-report-v1"
