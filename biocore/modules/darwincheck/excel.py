"""Safe workbook input and explainable DarwinCheck export."""

from __future__ import annotations

from io import BytesIO
from typing import Mapping

import pandas as pd

from .analyzer import COLUMN_INDEX, MINIMUM_COLUMNS
from .domain import DarwinCheckAnalysis


class DarwinCheckWorkbookError(ValueError):
    """Raised when a workbook does not match the supported audit contract."""


def read_occurrence_workbook(payload: bytes) -> pd.DataFrame:
    if not payload:
        raise DarwinCheckWorkbookError("El archivo está vacío.")
    try:
        workbook = pd.ExcelFile(BytesIO(payload))
    except Exception as error:
        raise DarwinCheckWorkbookError(
            "No pudimos abrir el archivo como libro de Excel."
        ) from error
    occurrence_sheet = next(
        (
            sheet
            for sheet in workbook.sheet_names
            if str(sheet).strip().casefold() == "ocurrencia"
        ),
        None,
    )
    if occurrence_sheet is None:
        raise DarwinCheckWorkbookError(
            "El libro debe contener una hoja llamada “Ocurrencia”."
        )
    try:
        dataframe = pd.read_excel(
            workbook,
            sheet_name=occurrence_sheet,
            dtype=str,
        )
    except Exception as error:
        raise DarwinCheckWorkbookError(
            "No pudimos leer la hoja Ocurrencia. Revisa que no esté protegida o dañada."
        ) from error
    dataframe.columns = [str(column).strip() for column in dataframe.columns]
    if dataframe.shape[1] < MINIMUM_COLUMNS:
        raise DarwinCheckWorkbookError(
            f"La hoja Ocurrencia tiene {dataframe.shape[1]} columnas; "
            "DarwinCheck necesita al menos 34 para esta plantilla SMA."
        )
    return dataframe.fillna("")


def _replace_reviewed_values(analysis: DarwinCheckAnalysis) -> pd.DataFrame:
    exported = analysis.original_dataframe.copy()
    audited = analysis.audit_dataframe
    if audited.empty:
        return exported
    audit_by_row = {
        int(row["spreadsheet_row"]): row for _, row in audited.iterrows()
    }
    mapping = {
        "kingdom_reviewed": "kingdom",
        "phylum_reviewed": "phylum",
        "class_reviewed": "class",
        "order_reviewed": "order",
        "family_reviewed": "family",
        "genus_reviewed": "genus",
        "specific_epithet_reviewed": "specific_epithet",
        "common_name_reviewed": "common_name",
        "latitude_reviewed": "latitude",
        "longitude_reviewed": "longitude",
        "start_time_reviewed": "start_time",
        "record_time_reviewed": "record_time",
    }
    for dataframe_index in exported.index:
        spreadsheet_row = int(dataframe_index) + 2
        audit_row = audit_by_row.get(spreadsheet_row)
        if audit_row is None:
            continue
        for audit_column, source_field in mapping.items():
            exported.iat[
                exported.index.get_loc(dataframe_index),
                COLUMN_INDEX[source_field],
            ] = audit_row[audit_column]
    return exported


def export_audit_workbook(
    analysis: DarwinCheckAnalysis,
    *,
    organization_id: str,
    organization_name: str,
    project_id: str,
    project_name: str,
    user_id: str,
    run_id: str,
) -> bytes:
    output = BytesIO()
    corrected = _replace_reviewed_values(analysis)
    corrected["DARWINCHECK_CLASIFICACION_GEOGRAFICA"] = ""
    corrected["DARWINCHECK_FUENTE_TAXONOMICA"] = ""
    corrected["DARWINCHECK_REQUIERE_REVISION"] = False
    audit_by_row = {
        int(row["spreadsheet_row"]): row
        for _, row in analysis.audit_dataframe.iterrows()
    }
    for dataframe_index in corrected.index:
        audit = audit_by_row.get(int(dataframe_index) + 2)
        if audit is None:
            continue
        corrected.at[
            dataframe_index, "DARWINCHECK_CLASIFICACION_GEOGRAFICA"
        ] = audit["geographic_classification"]
        corrected.at[
            dataframe_index, "DARWINCHECK_FUENTE_TAXONOMICA"
        ] = audit["taxonomy_source"]
        corrected.at[
            dataframe_index, "DARWINCHECK_REQUIERE_REVISION"
        ] = bool(audit["requires_professional_review"])

    summary_rows = [
        {"indicador": key, "valor": value}
        for key, value in analysis.summary.as_dict().items()
        if key not in {"ecological_indices", "accumulation_curve"}
    ]
    summary_rows.extend(
        {
            "indicador": f"indice_{key}",
            "valor": value,
        }
        for key, value in analysis.summary.ecological_indices.items()
    )
    findings = pd.DataFrame(
        [finding.as_dict() for finding in analysis.findings]
    )
    if findings.empty:
        findings = pd.DataFrame(
            columns=(
                "row_number",
                "category",
                "severity",
                "observed",
                "rule",
                "explanation",
                "recommendation",
            )
        )
    context: Mapping[str, object] = {
        "organization_id": organization_id,
        "organization_name": organization_name,
        "project_id": project_id,
        "project_name": project_name,
        "user_id": user_id,
        "darwincheck_run_id": run_id,
        "reference_name": analysis.reference_name,
        "reference_version": analysis.reference_version,
        "method": "Reglas deterministas DarwinCheck; sin IA generativa",
        "limitation": (
            "Auditoría preliminar de estructura, taxonomía y coordenadas. "
            "No certifica cumplimiento ni reemplaza revisión profesional."
        ),
    }

    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        corrected.to_excel(writer, sheet_name="Ocurrencia", index=False)
        pd.DataFrame(summary_rows).to_excel(
            writer, sheet_name="Resumen DarwinCheck", index=False
        )
        findings.to_excel(writer, sheet_name="Hallazgos", index=False)
        analysis.audit_dataframe.to_excel(
            writer, sheet_name="Trazabilidad", index=False
        )
        pd.DataFrame([context]).to_excel(
            writer, sheet_name="Contexto BioCore", index=False
        )
        for worksheet in writer.book.worksheets:
            worksheet.freeze_panes = "A2"
            worksheet.auto_filter.ref = worksheet.dimensions
            for column_cells in worksheet.columns:
                values = [str(cell.value or "") for cell in column_cells[:100]]
                width = min(max((len(value) for value in values), default=8) + 2, 55)
                worksheet.column_dimensions[column_cells[0].column_letter].width = width
    return output.getvalue()
