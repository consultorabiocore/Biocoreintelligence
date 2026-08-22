from __future__ import annotations

from datetime import date

import pytest

from biocore.modules.intelligence.copernicus import (
    CATALOG_URL,
    EVALSCRIPT,
    STATISTICS_URL,
    TOKEN_URL,
    CopernicusProvider,
    CopernicusQuotaExceeded,
    CopernicusUnavailable,
)


COORDINATES = [
    [-73.10, -36.90],
    [-73.00, -36.90],
    [-73.00, -36.80],
    [-73.10, -36.80],
    [-73.10, -36.90],
]


class FakeResponse:
    def __init__(self, status_code: int, document: dict[str, object]) -> None:
        self.status_code = status_code
        self._document = document

    def json(self):
        return self._document


def _catalog(day: str, cloud: float) -> dict[str, object]:
    return {
        "features": [
            {
                "properties": {
                    "datetime": f"{day}T14:22:00Z",
                    "eo:cloud_cover": cloud,
                }
            }
        ],
        "context": {"returned": 1},
    }


def _statistics(values: dict[str, float]) -> dict[str, object]:
    return {
        "data": [
            {
                "outputs": {
                    "indices": {
                        "bands": {
                            code: {
                                "stats": {
                                    "mean": value,
                                    "sampleCount": 120,
                                    "noDataCount": 20,
                                }
                            }
                            for code, value in values.items()
                        }
                    }
                }
            }
        ],
        "status": "OK",
    }


class FakeHttp:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []
        self.catalog_documents = [
            _catalog("2026-07-01", 12.0),
            _catalog("2024-07-03", 18.0),
        ]
        self.statistics_documents = [
            _statistics(
                {
                    "ndvi": 0.48,
                    "evi": 0.31,
                    "savi": 0.42,
                    "ndwi": -0.18,
                    "ndmi": 0.22,
                    "ndsi": -0.25,
                    "swir1": 0.12,
                    "swir_ratio": 1.15,
                    "vegetation_cover": 64.0,
                }
            ),
            _statistics(
                {
                    "ndvi": 0.55,
                    "evi": 0.35,
                    "savi": 0.48,
                    "ndwi": -0.12,
                    "ndmi": 0.28,
                    "ndsi": -0.19,
                    "swir1": 0.10,
                    "swir_ratio": 1.05,
                    "vegetation_cover": 71.0,
                }
            ),
        ]

    def post(self, url: str, **kwargs):
        self.calls.append((url, kwargs))
        if url == TOKEN_URL:
            return FakeResponse(200, {"access_token": "token-real", "expires_in": 600})
        if url == CATALOG_URL:
            return FakeResponse(200, self.catalog_documents.pop(0))
        if url == STATISTICS_URL:
            return FakeResponse(200, self.statistics_documents.pop(0))
        raise AssertionError(f"Unexpected URL: {url}")


def test_copernicus_provider_returns_real_source_and_auditable_metadata() -> None:
    http = FakeHttp()
    provider = CopernicusProvider("client-id", "client-secret", http=http, clock=lambda: 5.0)

    snapshot = provider.analyze(
        COORDINATES,
        2024,
        today=date(2026, 8, 16),
    )

    assert snapshot.provider_version == "copernicus-cdse-sentinel-2-l2a-v2"
    assert snapshot.current_period == "2026-05-19 / 2026-08-16"
    assert snapshot.baseline_period == "2024-05-19 / 2024-08-16"
    assert snapshot.recent_image_count == 1
    assert snapshot.baseline_image_count == 1
    assert snapshot.mean_cloud_percent == 12.0
    assert snapshot.metadata["provider"] == "Copernicus Data Space Ecosystem"
    assert snapshot.metadata["data_nature"] == "observed_and_calculated"
    assert snapshot.metadata["current_valid_pixel_samples"] == 100
    assert [metric.code for metric in snapshot.metrics] == [
        "ndvi",
        "evi",
        "savi",
        "ndwi",
        "ndmi",
        "ndsi",
        "swir1",
        "swir_ratio",
        "vegetation_cover",
    ]
    assert snapshot.metrics[0].current == 0.48
    assert snapshot.metrics[0].baseline == 0.55
    assert all("Copernicus Data Space" in metric.source for metric in snapshot.metrics)

    token_calls = [call for call in http.calls if call[0] == TOKEN_URL]
    assert len(token_calls) == 1
    assert token_calls[0][1]["data"] == {
        "grant_type": "client_credentials",
        "client_id": "client-id",
        "client_secret": "client-secret",
    }
    statistics_payload = next(
        call[1]["json"] for call in http.calls if call[0] == STATISTICS_URL
    )
    assert statistics_payload["input"]["bounds"]["geometry"]["coordinates"] == [
        COORDINATES
    ]
    assert statistics_payload["aggregation"]["aggregationInterval"] == {"of": "P90D"}
    assert statistics_payload["aggregation"]["evalscript"] == EVALSCRIPT


def test_missing_credentials_never_calls_external_service() -> None:
    http = FakeHttp()
    provider = CopernicusProvider(None, None, http=http)

    assert provider.configured is False
    with pytest.raises(CopernicusUnavailable):
        provider.analyze(COORDINATES, 2024, today=date(2026, 8, 16))

    assert http.calls == []


class QuotaHttp(FakeHttp):
    def post(self, url: str, **kwargs):
        if url == TOKEN_URL:
            return FakeResponse(200, {"access_token": "token", "expires_in": 600})
        return FakeResponse(429, {"error": "rate_limit"})


def test_quota_error_is_explicit_and_does_not_return_partial_data() -> None:
    provider = CopernicusProvider("client", "secret", http=QuotaHttp())

    with pytest.raises(CopernicusQuotaExceeded, match="cuota gratuita"):
        provider.analyze(COORDINATES, 2024, today=date(2026, 8, 16))
