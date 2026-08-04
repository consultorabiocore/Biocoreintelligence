from __future__ import annotations

import pandas as pd

from biocore.modules.darwincheck.analyzer import (
    COLUMN_INDEX,
    DarwinCheckAnalyzer,
    DarwinCheckValidationError,
    TaxonomyReference,
)


def _source_row(**values: str) -> list[str]:
    row = [""] * 34
    for field, value in values.items():
        source_field = "class" if field == "tax_class" else field
        row[COLUMN_INDEX[source_field]] = value
    return row


def _source(*rows: list[str]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=[f"column_{index}" for index in range(34)])


def _reference() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Reino": "Plantae",
                "Filo o División": "Tracheophyta",
                "Clase": "Magnoliopsida",
                "Orden": "Fagales",
                "Familia": "Nothofagaceae",
                "Género": "Nothofagus",
                "Epíteto específico": "dombeyi",
                "Nombre común": "Coihue",
            }
        ]
    )


def test_analyzer_applies_only_exact_reference_matches_and_parses_gms() -> None:
    analyzer = DarwinCheckAnalyzer(
        TaxonomyReference(dataframe=_reference(), version="test-reference")
    )
    result = analyzer.analyze(
        _source(
            _source_row(
                kingdom="",
                phylum="",
                tax_class="",
                order="",
                family="",
                genus="Nothofagus",
                specific_epithet="dombeyi",
                common_name="",
                value="2",
                latitude='36°48\'00"S',
                longitude='73°03\'00"O',
                start_time="0830",
                record_time="09:15",
            )
        )
    )

    audited = result.audit_dataframe.iloc[0]
    assert audited["scientific_name_reviewed"] == "Nothofagus dombeyi"
    assert audited["family_reviewed"] == "Nothofagaceae"
    assert audited["latitude_reviewed"] == "-36.800000"
    assert audited["longitude_reviewed"] == "-73.050000"
    assert audited["geographic_classification"] == "Chile continental"
    assert result.summary.exact_taxonomy_matches == 1
    assert result.summary.manual_review_rows == 0
    assert result.summary.ecological_indices["total_individuals"] == 2.0
    assert result.reference_version == "test-reference"


def test_unmatched_taxonomy_and_outside_coordinates_are_explainable() -> None:
    analyzer = DarwinCheckAnalyzer(TaxonomyReference(dataframe=_reference()))
    result = analyzer.analyze(
        _source(
            _source_row(
                genus="Ejemplo",
                specific_epithet="desconocido",
                value="no-numérico",
                latitude="40",
                longitude="10",
            )
        )
    )

    assert result.summary.manual_review_rows == 1
    assert result.summary.geographic_issue_rows == 1
    categories = {finding.category for finding in result.findings}
    assert categories == {"Taxonomía", "Geografía", "Estructura"}
    taxonomy = next(
        finding for finding in result.findings if finding.category == "Taxonomía"
    )
    assert "No se modificó" in taxonomy.explanation
    assert result.audit_dataframe.iloc[0]["scientific_name_reviewed"] == (
        "Ejemplo desconocido"
    )


def test_analyzer_rejects_incompatible_workbook_structure() -> None:
    analyzer = DarwinCheckAnalyzer(TaxonomyReference(dataframe=_reference()))
    try:
        analyzer.analyze(pd.DataFrame([["x"]] * 2))
    except DarwinCheckValidationError as error:
        assert "34 columnas" in str(error)
    else:
        raise AssertionError("Expected DarwinCheckValidationError")


def test_analyzer_rejects_workbook_without_occurrence_records() -> None:
    analyzer = DarwinCheckAnalyzer(TaxonomyReference(dataframe=_reference()))
    try:
        analyzer.analyze(_source())
    except DarwinCheckValidationError as error:
        assert "no contiene registros" in str(error)
    else:
        raise AssertionError("Expected DarwinCheckValidationError")
