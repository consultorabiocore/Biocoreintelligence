"""Cost-controlled Copernicus Data Space provider for BioCore Intelligence."""

from __future__ import annotations

import calendar
import time
from datetime import date, timedelta
from typing import Any, Callable

import requests

from biocore.domain.intelligence import SatelliteMetric, SatelliteSnapshot


TOKEN_URL = (
    "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/"
    "protocol/openid-connect/token"
)
STATISTICS_URL = "https://sh.dataspace.copernicus.eu/statistics/v1"
CATALOG_URL = "https://sh.dataspace.copernicus.eu/catalog/v1/search"
PROVIDER_VERSION = "copernicus-cdse-sentinel-2-l2a-v1"
WINDOW_DAYS = 90
MAX_CLOUD_COVER = 60


class CopernicusUnavailable(RuntimeError):
    """Raised when CDSE credentials or connectivity are unavailable."""


class CopernicusAnalysisError(RuntimeError):
    """Raised when real Sentinel data cannot produce an auditable result."""


class CopernicusQuotaExceeded(CopernicusAnalysisError):
    """Raised when the free monthly or short-term quota has been reached."""


def _same_day(year: int, value: date) -> date:
    return date(
        year,
        value.month,
        min(value.day, calendar.monthrange(year, value.month)[1]),
    )


EVALSCRIPT = """//VERSION=3
function setup() {
  return {
    input: [{
      bands: ["B02", "B04", "B08", "B11", "SCL", "dataMask"]
    }],
    output: [
      {
        id: "indices",
        bands: ["ndvi", "evi", "ndmi", "vegetation_cover"],
        sampleType: "FLOAT32"
      },
      { id: "dataMask", bands: 1 }
    ]
  };
}

function evaluatePixel(sample) {
  const excludedScl = [1, 3, 7, 8, 9, 10, 11];
  const clear = sample.dataMask === 1 && excludedScl.indexOf(sample.SCL) === -1;
  const ndviDenominator = sample.B08 + sample.B04;
  const ndmiDenominator = sample.B08 + sample.B11;
  const eviDenominator = sample.B08 + 6 * sample.B04 - 7.5 * sample.B02 + 1;
  const valid = clear && Math.abs(ndviDenominator) > 0.000001 &&
    Math.abs(ndmiDenominator) > 0.000001 && Math.abs(eviDenominator) > 0.000001;
  if (!valid) {
    return { indices: [0, 0, 0, 0], dataMask: [0] };
  }
  const ndvi = (sample.B08 - sample.B04) / ndviDenominator;
  const evi = 2.5 * (sample.B08 - sample.B04) / eviDenominator;
  const ndmi = (sample.B08 - sample.B11) / ndmiDenominator;
  return {
    indices: [ndvi, evi, ndmi, ndvi > 0.3 ? 100 : 0],
    dataMask: [1]
  };
}
"""


class CopernicusProvider:
    """Calculate real Sentinel-2 indicators through the free CDSE API tier.

    The provider uses OAuth client credentials kept server-side. It never sends
    BioCore user identity or project metadata to CDSE; only the requested
    geometry, period and deterministic evalscript leave the application.
    """

    def __init__(
        self,
        client_id: str | None,
        client_secret: str | None,
        *,
        http: Any | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._client_id = str(client_id or "").strip()
        self._client_secret = str(client_secret or "").strip()
        self._http = http or requests.Session()
        self._clock = clock
        self._access_token: str | None = None
        self._token_expires_at = 0.0

    @property
    def configured(self) -> bool:
        return bool(self._client_id and self._client_secret)

    def _response_json(self, response: Any, *, purpose: str) -> dict[str, Any]:
        status = int(getattr(response, "status_code", 0) or 0)
        if status == 429:
            raise CopernicusQuotaExceeded(
                "La cuota gratuita de Copernicus está temporalmente agotada. "
                "No se guardó ningún resultado; inténtalo nuevamente cuando se renueve."
            )
        if status in {401, 403}:
            raise CopernicusUnavailable(
                "Copernicus rechazó las credenciales de BioCore. "
                "Un administrador debe revisar el Client ID y el Client Secret."
            )
        if status < 200 or status >= 300:
            raise CopernicusAnalysisError(
                f"Copernicus no pudo completar {purpose}. No se guardó un resultado parcial."
            )
        try:
            document = response.json()
        except (TypeError, ValueError) as error:
            raise CopernicusAnalysisError(
                f"Copernicus devolvió una respuesta inválida durante {purpose}."
            ) from error
        if not isinstance(document, dict):
            raise CopernicusAnalysisError(
                f"Copernicus devolvió una respuesta incompleta durante {purpose}."
            )
        return document

    def _token(self, *, force_refresh: bool = False) -> str:
        if not self.configured:
            raise CopernicusUnavailable(
                "La conexión gratuita con Copernicus Data Space aún no está configurada."
            )
        now = self._clock()
        if (
            not force_refresh
            and self._access_token
            and now < self._token_expires_at
        ):
            return self._access_token
        try:
            response = self._http.post(
                TOKEN_URL,
                data={
                    "grant_type": "client_credentials",
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=20,
            )
        except requests.RequestException as error:
            raise CopernicusUnavailable(
                "No pudimos conectar con Copernicus Data Space. Reintenta en unos minutos."
            ) from error
        document = self._response_json(response, purpose="la autenticación")
        token = document.get("access_token")
        if not isinstance(token, str) or not token:
            raise CopernicusUnavailable(
                "Copernicus no entregó una sesión válida para BioCore."
            )
        try:
            expires_in = max(120.0, float(document.get("expires_in", 600)))
        except (TypeError, ValueError):
            expires_in = 600.0
        self._access_token = token
        self._token_expires_at = now + expires_in - 60.0
        return token

    def _authorized_post(
        self,
        url: str,
        payload: dict[str, Any],
        *,
        purpose: str,
    ) -> dict[str, Any]:
        for attempt in range(2):
            token = self._token(force_refresh=attempt == 1)
            try:
                response = self._http.post(
                    url,
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Accept": "application/json",
                        "Content-Type": "application/json",
                    },
                    timeout=60,
                )
            except requests.RequestException as error:
                raise CopernicusUnavailable(
                    "Se interrumpió la conexión con Copernicus. "
                    "No se guardó ningún resultado; puedes reintentar."
                ) from error
            if int(getattr(response, "status_code", 0) or 0) == 401 and attempt == 0:
                self._access_token = None
                continue
            return self._response_json(response, purpose=purpose)
        raise CopernicusUnavailable(
            "No pudimos renovar la sesión segura con Copernicus Data Space."
        )

    @staticmethod
    def _geometry(coordinates: list[list[float]]) -> dict[str, Any]:
        return {"type": "Polygon", "coordinates": [coordinates]}

    def _catalog_evidence(
        self,
        geometry: dict[str, Any],
        start: date,
        end: date,
    ) -> tuple[int, float | None]:
        payload: dict[str, Any] = {
            "collections": ["sentinel-2-l2a"],
            "datetime": (
                f"{start.isoformat()}T00:00:00Z/{end.isoformat()}T23:59:59Z"
            ),
            "intersects": geometry,
            "filter": f"eo:cloud_cover <= {MAX_CLOUD_COVER}",
            "filter-lang": "cql2-text",
            "limit": 100,
        }
        acquisition_days: set[str] = set()
        cloud_values: list[float] = []
        for _ in range(5):
            document = self._authorized_post(
                CATALOG_URL,
                payload,
                purpose="la búsqueda de imágenes Sentinel-2",
            )
            for feature in document.get("features") or []:
                if not isinstance(feature, dict):
                    continue
                properties = feature.get("properties") or {}
                timestamp = properties.get("datetime")
                if isinstance(timestamp, str) and len(timestamp) >= 10:
                    acquisition_days.add(timestamp[:10])
                cloud = properties.get("eo:cloud_cover")
                try:
                    if cloud is not None:
                        cloud_values.append(float(cloud))
                except (TypeError, ValueError):
                    pass
            next_page = (document.get("context") or {}).get("next")
            if next_page is None:
                break
            payload["next"] = next_page
        mean_cloud = (
            round(sum(cloud_values) / len(cloud_values), 2)
            if cloud_values
            else None
        )
        return len(acquisition_days), mean_cloud

    def _period_statistics(
        self,
        geometry: dict[str, Any],
        start: date,
        end: date,
    ) -> tuple[dict[str, float], int]:
        payload = {
            "input": {
                "bounds": {
                    "geometry": geometry,
                    "properties": {
                        "crs": "http://www.opengis.net/def/crs/OGC/1.3/CRS84"
                    },
                },
                "data": [
                    {
                        "type": "sentinel-2-l2a",
                        "dataFilter": {
                            "mosaickingOrder": "leastCC",
                            "maxCloudCoverage": MAX_CLOUD_COVER,
                        },
                    }
                ],
            },
            "aggregation": {
                "timeRange": {
                    "from": f"{start.isoformat()}T00:00:00Z",
                    "to": f"{(end + timedelta(days=1)).isoformat()}T00:00:00Z",
                },
                "aggregationInterval": {"of": f"P{WINDOW_DAYS}D"},
                "evalscript": EVALSCRIPT,
                "resx": 20,
                "resy": 20,
            },
        }
        document = self._authorized_post(
            STATISTICS_URL,
            payload,
            purpose="el cálculo de indicadores Sentinel-2",
        )
        rows = document.get("data") or []
        weighted_sums = {
            "ndvi": 0.0,
            "evi": 0.0,
            "ndmi": 0.0,
            "vegetation_cover": 0.0,
        }
        weights = {code: 0 for code in weighted_sums}
        for row in rows:
            try:
                bands = row["outputs"]["indices"]["bands"]
            except (KeyError, TypeError):
                continue
            for code in weighted_sums:
                stats = (bands.get(code) or {}).get("stats") or {}
                try:
                    sample_count = int(stats.get("sampleCount") or 0)
                    no_data_count = int(stats.get("noDataCount") or 0)
                    valid_count = max(0, sample_count - no_data_count)
                    mean = float(stats["mean"])
                except (KeyError, TypeError, ValueError):
                    continue
                if valid_count:
                    weighted_sums[code] += mean * valid_count
                    weights[code] += valid_count
        missing = [code for code, weight in weights.items() if weight == 0]
        if missing:
            raise CopernicusAnalysisError(
                "No encontramos píxeles Sentinel-2 despejados suficientes para "
                "calcular todos los indicadores en este período."
            )
        values = {
            code: round(weighted_sums[code] / weights[code], 6)
            for code in weighted_sums
        }
        return values, min(weights.values())

    @staticmethod
    def _metric(
        code: str,
        label: str,
        current: float,
        baseline: float,
        unit: str,
        source: str,
    ) -> SatelliteMetric:
        return SatelliteMetric(
            code=code,
            label=label,
            current=current,
            baseline=baseline,
            unit=unit,
            source=source,
            resolution="20 m de análisis (bandas nativas de 10–20 m)",
        )

    def analyze(
        self,
        coordinates: list[list[float]],
        baseline_year: int,
        *,
        today: date | None = None,
    ) -> SatelliteSnapshot:
        current_end = today or date.today()
        current_start = current_end - timedelta(days=WINDOW_DAYS - 1)
        baseline_end = _same_day(baseline_year, current_end)
        baseline_start = baseline_end - timedelta(days=WINDOW_DAYS - 1)
        geometry = self._geometry(coordinates)

        current_scene_count, current_cloud = self._catalog_evidence(
            geometry, current_start, current_end
        )
        baseline_scene_count, _ = self._catalog_evidence(
            geometry, baseline_start, baseline_end
        )
        if current_scene_count == 0:
            raise CopernicusAnalysisError(
                "No encontramos imágenes Sentinel-2 utilizables en los últimos 90 días."
            )
        if baseline_scene_count == 0:
            raise CopernicusAnalysisError(
                "No encontramos imágenes Sentinel-2 para la línea base seleccionada."
            )
        current, current_valid_pixels = self._period_statistics(
            geometry, current_start, current_end
        )
        baseline, baseline_valid_pixels = self._period_statistics(
            geometry, baseline_start, baseline_end
        )

        source = "Copernicus Data Space · Sentinel-2 L2A"
        metrics = (
            self._metric("ndvi", "NDVI", current["ndvi"], baseline["ndvi"], "índice", source),
            self._metric("evi", "EVI", current["evi"], baseline["evi"], "índice", source),
            self._metric(
                "ndmi",
                "Humedad de vegetación (NDMI)",
                current["ndmi"],
                baseline["ndmi"],
                "índice",
                source,
            ),
            self._metric(
                "vegetation_cover",
                "Cobertura vegetal estimada",
                current["vegetation_cover"],
                baseline["vegetation_cover"],
                "% del polígono con NDVI > 0,3",
                source,
            ),
        )
        return SatelliteSnapshot(
            metrics=metrics,
            current_period=f"{current_start.isoformat()} / {current_end.isoformat()}",
            baseline_period=f"{baseline_start.isoformat()} / {baseline_end.isoformat()}",
            recent_image_count=current_scene_count,
            baseline_image_count=baseline_scene_count,
            mean_cloud_percent=current_cloud,
            provider_version=PROVIDER_VERSION,
            metadata={
                "provider": "Copernicus Data Space Ecosystem",
                "collection": "Sentinel-2 L2A",
                "window_days": WINDOW_DAYS,
                "max_scene_cloud_percent": MAX_CLOUD_COVER,
                "composite_rule": "least-cloud mosaic for each 90-day window",
                "current_valid_pixel_samples": current_valid_pixels,
                "baseline_valid_pixel_samples": baseline_valid_pixels,
                "external_processing": True,
                "data_nature": "observed_and_calculated",
            },
        )
