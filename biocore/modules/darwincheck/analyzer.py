"""Deterministic and explainable Darwin Core/SMA spreadsheet analysis."""

from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from .domain import (
    DarwinCheckAnalysis,
    DarwinCheckFinding,
    DarwinCheckSummary,
)


MINIMUM_COLUMNS = 34
MAXIMUM_ROWS = 100_000
REFERENCE_NAME = "SIMBIO Especies"
REFERENCE_VERSION = "2026-02-19"

# Posiciones de la plantilla SMA utilizada por DarwinCheck (base cero).
COLUMN_INDEX = {
    "start_time": 7,
    "kingdom": 14,
    "phylum": 15,
    "class": 16,
    "order": 17,
    "family": 18,
    "genus": 19,
    "specific_epithet": 21,
    "common_name": 23,
    "value": 29,
    "latitude": 31,
    "longitude": 32,
    "record_time": 33,
}

REFERENCE_COLUMN_CANDIDATES = {
    "kingdom": ("reino",),
    "phylum": ("filo o division", "filo division", "filo", "division"),
    "class": ("clase",),
    "order": ("orden",),
    "family": ("familia",),
    "genus": ("genero",),
    "specific_epithet": ("epiteto especifico", "epiteto"),
    "scientific_name": ("nombre cientifico",),
    "common_name": ("nombre comun",),
}


class DarwinCheckValidationError(ValueError):
    """Raised when an input cannot be audited safely."""


def _safe_text(value: object) -> str:
    if value is None:
        return ""
    try:
        if bool(pd.isna(value)):
            return ""
    except (TypeError, ValueError):
        pass
    text = str(value).strip()
    if text.casefold() in {"", "na", "nan", "none", "null"}:
        return ""
    return text


def _normalized(value: object) -> str:
    text = _safe_text(value)
    decomposed = unicodedata.normalize("NFD", text)
    without_accents = "".join(
        character
        for character in decomposed
        if unicodedata.category(character) != "Mn"
    )
    return " ".join(without_accents.casefold().split())


def _normalized_header(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", " ", _normalized(value)).strip()


def _format_time(value: object) -> str:
    text = _safe_text(value)
    if not text:
        return ""
    for pattern in (
        "%H:%M:%S",
        "%H:%M",
        "%H%M%S",
        "%H%M",
        "%H:%M:%S.%f",
        "%I:%M:%S %p",
    ):
        try:
            return datetime.strptime(text, pattern).strftime("%H:%M:%S")
        except ValueError:
            continue
    return text


def _parse_coordinate(value: object) -> float | None:
    """Parse decimal or degrees/minutes/seconds while preserving hemisphere."""

    text = _safe_text(value)
    if not text:
        return None
    candidate = text.replace(",", ".")
    try:
        decimal = float(candidate)
        return decimal if -180 <= decimal <= 180 else None
    except ValueError:
        pass

    hemisphere_match = re.search(r"([NSEWO])", candidate.upper())
    hemisphere = hemisphere_match.group(1) if hemisphere_match else ""
    numbers = re.findall(r"[-+]?\d+(?:\.\d+)?", candidate)
    if not numbers:
        return None
    try:
        degrees = float(numbers[0])
        minutes = abs(float(numbers[1])) if len(numbers) > 1 else 0.0
        seconds = abs(float(numbers[2])) if len(numbers) > 2 else 0.0
    except ValueError:
        return None
    if minutes >= 60 or seconds >= 60:
        return None
    decimal = abs(degrees) + minutes / 60 + seconds / 3600
    if degrees < 0 or hemisphere in {"S", "W", "O"}:
        decimal = -decimal
    if hemisphere in {"N", "E"}:
        decimal = abs(decimal)
    return decimal if -180 <= decimal <= 180 else None


def _coordinate_location(latitude: float | None, longitude: float | None) -> str:
    if latitude is None or longitude is None:
        return "Coordenadas no interpretables"
    if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
        return "Fuera del rango geográfico global"
    if -56.0 <= latitude <= -17.5 and -76.0 <= longitude <= -66.0:
        return "Chile continental"
    if math.hypot(latitude + 27.1, longitude + 109.4) <= 0.5:
        return "Rapa Nui"
    if math.hypot(latitude + 33.6, longitude + 78.8) <= 0.5:
        return "Juan Fernández"
    return "Fuera del rango de referencia de Chile"


def _is_header_row(row: pd.Series) -> bool:
    values = {
        _normalized_header(row.iloc[position])
        for position in (
            COLUMN_INDEX["kingdom"],
            COLUMN_INDEX["phylum"],
            COLUMN_INDEX["class"],
            COLUMN_INDEX["order"],
            COLUMN_INDEX["family"],
            COLUMN_INDEX["genus"],
        )
    }
    keywords = {"reino", "filo", "division", "clase", "orden", "familia", "genero"}
    return bool(values & keywords)


@dataclass(frozen=True)
class _ReferenceMatch:
    status: str
    values: dict[str, str]


class TaxonomyReference:
    """Lazy, exact-match SIMBIO reference with deterministic behavior."""

    def __init__(
        self,
        path: Path | None = None,
        *,
        dataframe: pd.DataFrame | None = None,
        name: str = REFERENCE_NAME,
        version: str = REFERENCE_VERSION,
    ) -> None:
        self.path = path
        self._provided_dataframe = dataframe
        self.name = name
        self.version = version
        self._index: dict[str, tuple[dict[str, str], ...]] | None = None

    def _find_column(
        self, normalized_columns: dict[str, str], field: str
    ) -> str | None:
        for candidate in REFERENCE_COLUMN_CANDIDATES[field]:
            if candidate in normalized_columns:
                return normalized_columns[candidate]
        return None

    def _load(self) -> None:
        if self._index is not None:
            return
        if self._provided_dataframe is not None:
            source = self._provided_dataframe.copy()
        elif self.path is not None and self.path.is_file():
            source = pd.read_excel(self.path, sheet_name="Especies", dtype=str)
        else:
            source = pd.DataFrame()

        normalized_columns = {
            _normalized_header(column): str(column) for column in source.columns
        }
        resolved = {
            field: self._find_column(normalized_columns, field)
            for field in REFERENCE_COLUMN_CANDIDATES
        }
        genus_column = resolved["genus"]
        epithet_column = resolved["specific_epithet"]
        scientific_name_column = resolved["scientific_name"]
        if source.empty or (
            (genus_column is None or epithet_column is None)
            and scientific_name_column is None
        ):
            self._index = {}
            return

        index: dict[str, list[dict[str, str]]] = {}
        for _, row in source.iterrows():
            scientific_name = (
                _safe_text(row.get(scientific_name_column))
                if scientific_name_column
                else ""
            )
            name_parts = scientific_name.split()
            genus = (
                _safe_text(row.get(genus_column))
                if genus_column
                else (name_parts[0] if name_parts else "")
            )
            epithet = (
                _safe_text(row.get(epithet_column))
                if epithet_column
                else (name_parts[1] if len(name_parts) > 1 else "")
            )
            key = _normalized(f"{genus} {epithet}")
            if not key:
                continue
            values = {
                field: _safe_text(row.get(column)) if column else ""
                for field, column in resolved.items()
            }
            values["genus"] = genus
            values["specific_epithet"] = epithet
            index.setdefault(key, []).append(values)
        self._index = {key: tuple(values) for key, values in index.items()}

    def match(self, genus: str, epithet: str) -> _ReferenceMatch:
        self._load()
        if not genus or not epithet:
            return _ReferenceMatch("incomplete", {})
        matches = (self._index or {}).get(_normalized(f"{genus} {epithet}"), ())
        if len(matches) == 1:
            return _ReferenceMatch("exact", dict(matches[0]))
        if len(matches) > 1:
            return _ReferenceMatch("ambiguous", {})
        return _ReferenceMatch("not_found", {})


def _ecological_indices(records: list[tuple[str, float]]) -> dict[str, float]:
    grouped: dict[str, float] = {}
    for species, abundance in records:
        if not species or abundance <= 0:
            continue
        grouped[species] = grouped.get(species, 0.0) + abundance
    abundances = np.array(list(grouped.values()), dtype=float)
    if abundances.size == 0 or float(abundances.sum()) <= 0:
        return {
            "total_individuals": 0.0,
            "richness": 0.0,
            "shannon": 0.0,
            "simpson": 0.0,
            "pielou": 0.0,
            "margalef": 0.0,
            "chao1": 0.0,
            "representativeness_percent": 0.0,
        }
    total = float(abundances.sum())
    proportions = abundances / total
    richness = int(abundances.size)
    shannon = float(-np.sum(proportions * np.log(proportions)))
    simpson = float(np.sum(proportions**2))
    pielou = shannon / math.log(richness) if richness > 1 else 0.0
    margalef = (richness - 1) / math.log(total) if total > 1 else 0.0
    singletons = int(np.sum(abundances == 1))
    doubletons = int(np.sum(abundances == 2))
    chao1 = (
        richness + (singletons**2) / (2 * doubletons)
        if doubletons > 0
        else richness + (singletons * (singletons - 1)) / 2
    )
    representativeness = richness / chao1 * 100 if chao1 > 0 else 0.0
    return {
        "total_individuals": round(total, 4),
        "richness": float(richness),
        "shannon": round(shannon, 6),
        "simpson": round(simpson, 6),
        "pielou": round(pielou, 6),
        "margalef": round(margalef, 6),
        "chao1": round(float(chao1), 4),
        "representativeness_percent": round(representativeness, 2),
    }


def _accumulation_curve(species_sequence: list[str]) -> tuple[dict[str, float], ...]:
    observed: set[str] = set()
    points: list[dict[str, float]] = []
    for position, species in enumerate(species_sequence, start=1):
        if species:
            observed.add(species)
        points.append({"records": float(position), "observed_richness": float(len(observed))})
    if len(points) <= 100:
        return tuple(points)
    selected = np.linspace(0, len(points) - 1, 100, dtype=int)
    return tuple(points[index] for index in selected)


class DarwinCheckAnalyzer:
    """Apply versioned rules without Streamlit or generative AI."""

    def __init__(self, reference: TaxonomyReference) -> None:
        self.reference = reference

    def analyze(self, dataframe: pd.DataFrame) -> DarwinCheckAnalysis:
        if dataframe.shape[1] < MINIMUM_COLUMNS:
            raise DarwinCheckValidationError(
                "La hoja Ocurrencia debe contener al menos 34 columnas para "
                "la plantilla Darwin Core/SMA utilizada por DarwinCheck."
            )
        if dataframe.shape[0] > MAXIMUM_ROWS:
            raise DarwinCheckValidationError(
                "La hoja Ocurrencia supera los 100.000 registros permitidos "
                "por revisión. Divide la planilla en archivos más pequeños."
            )
        source = dataframe.copy().reset_index(drop=True).fillna("")
        source.columns = [str(column).strip() for column in source.columns]
        records: list[dict[str, Any]] = []
        findings: list[DarwinCheckFinding] = []
        ecological_records: list[tuple[str, float]] = []
        species_sequence: list[str] = []
        header_rows = exact_matches = corrected_rows = 0
        manual_rows: set[int] = set()
        geographic_rows: set[int] = set()
        completeness_present = 0
        completeness_expected = 0

        for dataframe_index, row in source.iterrows():
            spreadsheet_row = int(dataframe_index) + 2
            if _is_header_row(row):
                header_rows += 1
                continue

            original = {
                field: _safe_text(row.iloc[position])
                for field, position in COLUMN_INDEX.items()
            }
            genus = original["genus"]
            epithet = original["specific_epithet"]
            latitude = _parse_coordinate(original["latitude"])
            longitude = _parse_coordinate(original["longitude"])
            location = _coordinate_location(latitude, longitude)
            taxonomy = self.reference.match(genus, epithet)
            corrected = dict(original)
            correction_applied = False

            if taxonomy.status == "exact":
                exact_matches += 1
                for field in (
                    "kingdom",
                    "phylum",
                    "class",
                    "order",
                    "family",
                    "genus",
                    "specific_epithet",
                    "common_name",
                ):
                    reference_value = taxonomy.values.get(field, "")
                    if reference_value and reference_value != corrected[field]:
                        corrected[field] = reference_value
                        correction_applied = True
                taxonomy_source = f"{self.reference.name} {self.reference.version} (coincidencia exacta)"
            else:
                manual_rows.add(spreadsheet_row)
                taxonomy_source = {
                    "incomplete": "Taxonomía incompleta",
                    "ambiguous": "Más de una coincidencia exacta en la referencia",
                    "not_found": "Sin coincidencia exacta en la referencia",
                }[taxonomy.status]
                finding_rule = {
                    "incomplete": "El género y el epíteto específico deben estar informados.",
                    "ambiguous": "Una corrección automática requiere una única coincidencia exacta.",
                    "not_found": "DarwinCheck solo corrige cuando existe una coincidencia exacta y única.",
                }[taxonomy.status]
                findings.append(
                    DarwinCheckFinding(
                        row_number=spreadsheet_row,
                        category="Taxonomía",
                        severity="warning",
                        observed=f"{genus} {epithet}".strip() or "Nombre científico ausente",
                        rule=finding_rule,
                        explanation=(
                            "No se modificó el nombre. El resultado requiere revisión "
                            "profesional y no representa una identificación taxonómica."
                        ),
                        recommendation="Revisar el registro y documentar la fuente taxonómica antes de publicarlo.",
                    )
                )

            formatted_start = _format_time(original["start_time"])
            formatted_record = _format_time(original["record_time"])
            if formatted_start != original["start_time"]:
                corrected["start_time"] = formatted_start
                correction_applied = True
            if formatted_record != original["record_time"]:
                corrected["record_time"] = formatted_record
                correction_applied = True
            corrected["latitude"] = "" if latitude is None else f"{latitude:.6f}"
            corrected["longitude"] = "" if longitude is None else f"{longitude:.6f}"
            if corrected["latitude"] != original["latitude"] or corrected["longitude"] != original["longitude"]:
                correction_applied = True

            if location in {
                "Coordenadas no interpretables",
                "Fuera del rango geográfico global",
                "Fuera del rango de referencia de Chile",
            }:
                geographic_rows.add(spreadsheet_row)
                findings.append(
                    DarwinCheckFinding(
                        row_number=spreadsheet_row,
                        category="Geografía",
                        severity="error" if latitude is None or longitude is None else "warning",
                        observed=(
                            f"Latitud: {original['latitude'] or 'vacía'}; "
                            f"longitud: {original['longitude'] or 'vacía'}"
                        ),
                        rule="Las coordenadas deben ser interpretables y ubicarse dentro del rango geográfico declarado.",
                        explanation=(
                            f"Clasificación calculada: {location}. Esta clasificación es "
                            "una comprobación geométrica, no una determinación administrativa."
                        ),
                        recommendation="Confirmar el sistema de coordenadas, hemisferio y ubicación del punto.",
                    )
                )

            abundance_text = original["value"].replace(",", ".")
            try:
                abundance = float(abundance_text) if abundance_text else 0.0
            except ValueError:
                abundance = 0.0
                findings.append(
                    DarwinCheckFinding(
                        row_number=spreadsheet_row,
                        category="Estructura",
                        severity="warning",
                        observed=f"Valor de abundancia: {original['value']}",
                        rule="La abundancia debe ser numérica para calcular índices ecológicos.",
                        explanation="El valor se excluyó de los cálculos; no fue reemplazado por una inferencia.",
                        recommendation="Corregir el valor y volver a ejecutar la auditoría.",
                    )
                )

            scientific_name = " ".join(
                value for value in (corrected["genus"], corrected["specific_epithet"]) if value
            )
            ecological_records.append((scientific_name, abundance))
            species_sequence.append(scientific_name)
            if correction_applied:
                corrected_rows += 1

            key_values = (genus, epithet, original["latitude"], original["longitude"], original["value"])
            completeness_expected += len(key_values)
            completeness_present += sum(bool(value) for value in key_values)
            records.append(
                {
                    "spreadsheet_row": spreadsheet_row,
                    "scientific_name_original": f"{genus} {epithet}".strip(),
                    "scientific_name_reviewed": scientific_name,
                    "kingdom_reviewed": corrected["kingdom"],
                    "phylum_reviewed": corrected["phylum"],
                    "class_reviewed": corrected["class"],
                    "order_reviewed": corrected["order"],
                    "family_reviewed": corrected["family"],
                    "genus_reviewed": corrected["genus"],
                    "specific_epithet_reviewed": corrected["specific_epithet"],
                    "common_name_reviewed": corrected["common_name"],
                    "latitude_reviewed": corrected["latitude"],
                    "longitude_reviewed": corrected["longitude"],
                    "start_time_reviewed": corrected["start_time"],
                    "record_time_reviewed": corrected["record_time"],
                    "geographic_classification": location,
                    "taxonomy_source": taxonomy_source,
                    "requires_professional_review": spreadsheet_row in manual_rows,
                    "correction_applied": correction_applied,
                }
            )

        if not records:
            raise DarwinCheckValidationError(
                "La hoja Ocurrencia no contiene registros para revisar. "
                "Agrega al menos un registro de biodiversidad y vuelve a intentarlo."
            )

        audit_dataframe = pd.DataFrame.from_records(records)
        completeness = (
            completeness_present / completeness_expected * 100
            if completeness_expected
            else 0.0
        )
        summary = DarwinCheckSummary(
            input_rows=len(source),
            analyzed_rows=len(records),
            header_rows=header_rows,
            exact_taxonomy_matches=exact_matches,
            corrected_rows=corrected_rows,
            manual_review_rows=len(manual_rows),
            geographic_issue_rows=len(geographic_rows),
            completeness_percent=round(completeness, 2),
            ecological_indices=_ecological_indices(ecological_records),
            accumulation_curve=_accumulation_curve(species_sequence),
        )
        return DarwinCheckAnalysis(
            original_dataframe=source,
            audit_dataframe=audit_dataframe,
            summary=summary,
            findings=tuple(findings),
            reference_name=self.reference.name,
            reference_version=self.reference.version,
        )
