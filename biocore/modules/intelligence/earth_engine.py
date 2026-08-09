"""Google Earth Engine provider isolated from Streamlit and business rules."""

from __future__ import annotations

import calendar
import json
from datetime import date, timedelta
from typing import Any

from biocore.domain.intelligence import SatelliteMetric, SatelliteSnapshot


PROVIDER_VERSION = "earth-engine-s2-modis-era5-v1"


class EarthEngineUnavailable(RuntimeError):
    """Raised when Earth Engine credentials or runtime are unavailable."""


class EarthEngineAnalysisError(RuntimeError):
    """Raised when satellite sources cannot produce an auditable result."""


def _same_day(year: int, value: date) -> date:
    return date(year, value.month, min(value.day, calendar.monthrange(year, value.month)[1]))


class EarthEngineProvider:
    """Calculate explicit ecological indicators from documented public datasets."""

    def __init__(self, credentials_json: str | None) -> None:
        self._credentials_json = credentials_json
        self._ee: Any | None = None

    @property
    def configured(self) -> bool:
        return bool(self._credentials_json)

    def _client(self):
        if self._ee is not None:
            return self._ee
        if not self._credentials_json:
            raise EarthEngineUnavailable(
                "Google Earth Engine no está configurado para esta instalación."
            )
        try:
            import ee

            credentials = json.loads(self._credentials_json)
            account = credentials["client_email"]
            key = credentials["private_key"]
            project = credentials.get("project_id")
            ee.Initialize(
                ee.ServiceAccountCredentials(account, key_data=key),
                project=project,
            )
            self._ee = ee
            return ee
        except Exception as error:
            raise EarthEngineUnavailable(
                "No pudimos iniciar la conexión segura con Google Earth Engine."
            ) from error

    @staticmethod
    def _metric(
        code: str,
        label: str,
        current: object,
        baseline: object,
        unit: str,
        source: str,
        resolution: str,
    ) -> SatelliteMetric:
        def number(value: object) -> float | None:
            if value is None:
                return None
            try:
                return round(float(value), 6)
            except (TypeError, ValueError):
                return None

        return SatelliteMetric(
            code=code,
            label=label,
            current=number(current),
            baseline=number(baseline),
            unit=unit,
            source=source,
            resolution=resolution,
        )

    def analyze(
        self,
        coordinates: list[list[float]],
        baseline_year: int,
        *,
        today: date | None = None,
    ) -> SatelliteSnapshot:
        ee = self._client()
        current_end = today or date.today()
        current_start = current_end - timedelta(days=90)
        baseline_end = _same_day(baseline_year, current_end)
        baseline_start = baseline_end - timedelta(days=90)
        geometry = ee.Geometry.Polygon(coordinates)

        def mask_s2(image):
            scl = image.select("SCL")
            clear = (
                scl.neq(3)
                .And(scl.neq(8))
                .And(scl.neq(9))
                .And(scl.neq(10))
                .And(scl.neq(11))
            )
            return image.updateMask(clear)

        def s2_collection(start: date, end: date):
            return (
                ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
                .filterBounds(geometry)
                .filterDate(start.isoformat(), (end + timedelta(days=1)).isoformat())
                .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 60))
                .map(mask_s2)
            )

        def optical_stats(collection):
            image = collection.median()
            nir = image.select("B8").multiply(0.0001)
            red = image.select("B4").multiply(0.0001)
            blue = image.select("B2").multiply(0.0001)
            swir = image.select("B11").multiply(0.0001)
            ndvi = nir.subtract(red).divide(nir.add(red)).rename("ndvi")
            evi = (
                nir.subtract(red)
                .multiply(2.5)
                .divide(nir.add(red.multiply(6)).subtract(blue.multiply(7.5)).add(1))
                .rename("evi")
            )
            ndmi = nir.subtract(swir).divide(nir.add(swir)).rename("ndmi")
            cover = ndvi.gt(0.3).multiply(100).rename("vegetation_cover")
            return (
                ee.Image.cat([ndvi, evi, ndmi, cover])
                .reduceRegion(
                    reducer=ee.Reducer.mean(),
                    geometry=geometry,
                    scale=30,
                    maxPixels=1e9,
                    bestEffort=True,
                )
                .getInfo()
            )

        current_collection = s2_collection(current_start, current_end)
        baseline_collection = s2_collection(baseline_start, baseline_end)
        try:
            current_count = int(current_collection.size().getInfo() or 0)
            baseline_count = int(baseline_collection.size().getInfo() or 0)
            if current_count == 0:
                raise EarthEngineAnalysisError(
                    "No encontramos imágenes Sentinel-2 utilizables en los últimos 90 días."
                )
            if baseline_count == 0:
                raise EarthEngineAnalysisError(
                    "No encontramos imágenes Sentinel-2 para la línea base seleccionada."
                )
            current = optical_stats(current_collection)
            baseline = optical_stats(baseline_collection)
            cloud = current_collection.aggregate_mean(
                "CLOUDY_PIXEL_PERCENTAGE"
            ).getInfo()

            def temperature(start: date, end: date) -> object:
                image = (
                    ee.ImageCollection("MODIS/061/MOD11A2")
                    .filterBounds(geometry)
                    .filterDate(start.isoformat(), (end + timedelta(days=1)).isoformat())
                    .select("LST_Day_1km")
                    .mean()
                    .multiply(0.02)
                    .subtract(273.15)
                )
                return image.reduceRegion(
                    ee.Reducer.mean(), geometry, 1000, bestEffort=True, maxPixels=1e9
                ).get("LST_Day_1km").getInfo()

            def soil_moisture(start: date, end: date) -> object:
                image = (
                    ee.ImageCollection("ECMWF/ERA5_LAND/DAILY_AGGR")
                    .filterBounds(geometry)
                    .filterDate(start.isoformat(), (end + timedelta(days=1)).isoformat())
                    .select("volumetric_soil_water_layer_1")
                    .mean()
                )
                return image.reduceRegion(
                    ee.Reducer.mean(), geometry, 11132, bestEffort=True, maxPixels=1e9
                ).get("volumetric_soil_water_layer_1").getInfo()

            current_temperature = temperature(current_start, current_end)
            baseline_temperature = temperature(baseline_start, baseline_end)
            current_moisture = soil_moisture(current_start, current_end)
            baseline_moisture = soil_moisture(baseline_start, baseline_end)
        except EarthEngineAnalysisError:
            raise
        except Exception as error:
            raise EarthEngineAnalysisError(
                "Las fuentes satelitales no pudieron completar el cálculo para este polígono."
            ) from error

        metrics = (
            self._metric("ndvi", "NDVI", current.get("ndvi"), baseline.get("ndvi"), "índice", "Sentinel-2 SR", "30 m"),
            self._metric("evi", "EVI", current.get("evi"), baseline.get("evi"), "índice", "Sentinel-2 SR", "30 m"),
            self._metric("ndmi", "Humedad de vegetación (NDMI)", current.get("ndmi"), baseline.get("ndmi"), "índice", "Sentinel-2 SR", "30 m"),
            self._metric("vegetation_cover", "Cobertura vegetal estimada", current.get("vegetation_cover"), baseline.get("vegetation_cover"), "% del polígono", "Sentinel-2 SR · NDVI > 0,3", "30 m"),
            self._metric("surface_temperature", "Temperatura superficial diurna", current_temperature, baseline_temperature, "°C", "MODIS MOD11A2", "1 km"),
            self._metric("soil_moisture", "Humedad volumétrica superficial", current_moisture, baseline_moisture, "m³/m³", "ERA5-Land", "~11 km"),
        )
        return SatelliteSnapshot(
            metrics=metrics,
            current_period=f"{current_start.isoformat()} / {current_end.isoformat()}",
            baseline_period=f"{baseline_start.isoformat()} / {baseline_end.isoformat()}",
            recent_image_count=current_count,
            baseline_image_count=baseline_count,
            mean_cloud_percent=(round(float(cloud), 2) if cloud is not None else None),
            provider_version=PROVIDER_VERSION,
        )
