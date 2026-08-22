"""Versioned, explainable PDF reports for native BioCore Intelligence runs."""

from __future__ import annotations

from typing import Any, Iterable

from fpdf import FPDF

from biocore.domain.intelligence import IntelligenceRun


REPORT_VERSION = "biocore-intelligence-report-v1"


def _pdf_text(value: Any) -> str:
    """Keep reports compatible with FPDF core fonts without hiding content."""

    text = str(value if value is not None else "No disponible")
    translations = {
        "–": "-",
        "—": "-",
        "·": "-",
        "“": '"',
        "”": '"',
        "’": "'",
        "≥": ">=",
        "≤": "<=",
        "→": "->",
    }
    for source, target in translations.items():
        text = text.replace(source, target)
    return text.encode("latin-1", "replace").decode("latin-1")


def _number(value: Any, *, decimals: int = 3) -> str:
    try:
        return f"{float(value):.{decimals}f}"
    except (TypeError, ValueError):
        return "No disponible"


class BioCoreIntelligencePDF(FPDF):
    def header(self) -> None:
        self.set_text_color(15, 74, 55)
        self.set_font("Helvetica", "B", 15)
        self.cell(0, 9, "BioCore Intelligence", new_x="LMARGIN", new_y="NEXT")
        self.set_draw_color(197, 149, 49)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(4)

    def footer(self) -> None:
        self.set_y(-13)
        self.set_text_color(95, 113, 105)
        self.set_font("Helvetica", size=7.5)
        self.cell(
            0,
            6,
            _pdf_text(f"{REPORT_VERSION} | Pagina {self.page_no()}/{{nb}}"),
            align="C",
        )


def _section(pdf: FPDF, title: str) -> None:
    pdf.ln(2)
    pdf.set_text_color(15, 74, 55)
    pdf.set_font("Helvetica", "B", 11)
    pdf.multi_cell(0, 6, _pdf_text(title))
    pdf.set_text_color(28, 48, 39)


def _paragraph(pdf: FPDF, text: Any, *, bold: bool = False) -> None:
    pdf.set_font("Helvetica", "B" if bold else "", 8.6)
    pdf.multi_cell(0, 4.8, _pdf_text(text))


def _key_value(pdf: FPDF, key: str, value: Any) -> None:
    pdf.set_font("Helvetica", "B", 8.4)
    pdf.cell(45, 5, _pdf_text(key))
    pdf.set_font("Helvetica", size=8.4)
    pdf.multi_cell(0, 5, _pdf_text(value))


def _findings(pdf: FPDF, findings: Iterable[dict[str, Any]]) -> None:
    for index, finding in enumerate(findings, start=1):
        pdf.set_fill_color(239, 247, 242)
        pdf.set_font("Helvetica", "B", 8.8)
        pdf.multi_cell(
            0,
            5,
            _pdf_text(
                f"{index}. {finding.get('dimension')} - "
                f"{finding.get('classification')}"
            ),
            fill=True,
        )
        _paragraph(pdf, f"Dato comparado: {finding.get('observed')}")
        _paragraph(pdf, f"Regla: {finding.get('rule')}")
        _paragraph(pdf, f"Interpretacion: {finding.get('explanation')}")
        _paragraph(pdf, f"Confianza: {finding.get('confidence')}")
        _paragraph(pdf, f"Limitacion: {finding.get('limitation')}")
        _paragraph(pdf, f"Siguiente accion: {finding.get('recommendation')}")
        pdf.ln(2)


def build_intelligence_pdf(
    run: IntelligenceRun,
    *,
    project_name: str,
    project_code: str,
    technical: bool = False,
) -> bytes:
    """Build an executive or technical report from one immutable run."""

    pdf = BioCoreIntelligencePDF(format="A4")
    pdf.alias_nb_pages()
    pdf.set_auto_page_break(auto=True, margin=17)
    pdf.set_margins(16, 16, 16)
    pdf.add_page()

    pdf.set_text_color(22, 48, 38)
    pdf.set_font("Helvetica", "B", 17)
    report_name = "Informe tecnico" if technical else "Informe ejecutivo"
    pdf.multi_cell(0, 8, _pdf_text(report_name))
    pdf.set_font("Helvetica", size=9)
    pdf.multi_cell(
        0,
        5,
        _pdf_text(
            "Vigilancia ecologica satelital explicable, vinculada al proyecto y "
            "conservada en su historial."
        ),
    )

    _section(pdf, "Identificacion")
    _key_value(pdf, "Proyecto", f"{project_name} ({project_code})")
    _key_value(pdf, "Ejecucion", run.id)
    _key_value(pdf, "Generado", run.created_at.isoformat())
    _key_value(pdf, "Periodo actual", run.current_period)
    _key_value(pdf, "Linea base", run.baseline_period)
    _key_value(pdf, "Motor y reglas", run.provider_version)

    _section(pdf, "Alcance del resultado")
    _paragraph(
        pdf,
        "Resultado calculado y preliminar. Describe observaciones y comparaciones "
        "satelitales; no determina causas, no confirma impactos, no acredita "
        "cumplimiento y no reemplaza antecedentes ni verificacion de terreno.",
        bold=True,
    )

    _section(pdf, "Indicadores")
    for metric in run.metrics:
        change = metric.get("relative_change_percent")
        change_text = (
            f"{float(change):+.1f}%" if change is not None else "No disponible"
        )
        _paragraph(
            pdf,
            (
                f"{metric.get('label')}: actual {_number(metric.get('current'))}; "
                f"base {_number(metric.get('baseline'))}; cambio {change_text}."
            ),
            bold=True,
        )
        if technical:
            _paragraph(
                pdf,
                f"Fuente: {metric.get('source')}. Resolucion: {metric.get('resolution')}. "
                f"Unidad: {metric.get('unit') or 'indice'}.",
            )

    _section(pdf, "Hallazgos explicables")
    _findings(pdf, run.findings)

    if technical:
        evidence = run.evidence
        _section(pdf, "Fuentes y trazabilidad")
        _key_value(pdf, "Proveedor", evidence.get("provider"))
        _key_value(pdf, "Coleccion", evidence.get("collection"))
        _key_value(pdf, "Composicion", evidence.get("composite_rule"))
        _key_value(pdf, "Fechas actuales", evidence.get("recent_image_count"))
        _key_value(pdf, "Fechas de base", evidence.get("baseline_image_count"))
        _key_value(pdf, "Nubosidad media", evidence.get("mean_cloud_percent"))
        _key_value(
            pdf,
            "Muestras validas actuales",
            evidence.get("current_valid_pixel_samples"),
        )
        _key_value(
            pdf,
            "Muestras validas de base",
            evidence.get("baseline_valid_pixel_samples"),
        )
        coordinates = run.geometry.get("coordinates", [[]])
        ring = coordinates[0] if isinstance(coordinates, list) and coordinates else []
        _key_value(pdf, "Geometria", f"Poligono WGS84 con {len(ring)} vertices")
        _key_value(pdf, "Naturaleza", evidence.get("data_nature"))

    _section(pdf, "Que hacer ahora")
    _paragraph(
        pdf,
        "Revise los cambios junto con fechas intermedias, antecedentes del proyecto "
        "y evidencia de terreno. Si una senal requiere interpretacion especializada, "
        "solicite revision profesional BioCore antes de tomar decisiones.",
    )

    output = pdf.output(dest="S")
    return bytes(output)
