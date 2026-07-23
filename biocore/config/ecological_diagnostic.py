from biocore.domain.ecological_diagnostics import (
    DiagnosticDimension,
    QuestionDefinition,
    QuestionKind,
    ScoringRule,
)
from biocore.domain.subscriptions import ModuleCode


QUESTIONNAIRE_VERSION = "brief-1.0"
RULES_VERSION = "ecological-rules-1.0"

DIAGNOSTIC_NAME = "Diagnóstico Ecológico Digital BioCore"
DIAGNOSTIC_SUBTITLE = (
    "Evaluación preliminar de información sobre flora, vegetación, hongos "
    "y líquenes"
)
DIAGNOSTIC_DESCRIPTION = (
    "Conoce qué información existe sobre la flora, vegetación, hongos y "
    "líquenes de tu proyecto, qué brechas permanecen y qué campañas o "
    "análisis podrían ser necesarios."
)
DIAGNOSTIC_DISCLAIMER = (
    "Este diagnóstico entrega una orientación ecológica preliminar basada en "
    "la información proporcionada por el usuario. No reemplaza una campaña "
    "de terreno, una línea de base, una evaluación ambiental integral, una "
    "certificación ni una revisión normativa."
)
PRELIMINARY_REPORT_LABEL = (
    "Resultado preliminar no revisado profesionalmente"
)


COMPONENT_OPTIONS = (
    ("flora_vascular", "Flora vascular"),
    ("vegetation", "Vegetación o cobertura vegetal"),
    ("fungi", "Hongos"),
    ("lichens", "Líquenes"),
)

SEASON_OPTIONS = (
    ("autumn", "Otoño"),
    ("winter", "Invierno"),
    ("spring", "Primavera"),
    ("summer", "Verano"),
)

RECORD_FIELD_OPTIONS = (
    ("unique_id", "Identificador único"),
    ("date", "Fecha"),
    ("coordinates", "Coordenadas"),
    ("precision", "Precisión"),
    ("observer", "Persona observadora"),
    ("methodology", "Metodología"),
    ("taxon", "Taxón"),
    ("photograph", "Fotografía"),
    ("sample", "Muestra"),
    ("habitat", "Hábitat"),
    ("substrate", "Sustrato"),
    ("campaign", "Campaña"),
    ("validator", "Responsable de validación"),
    ("file_version", "Versión del archivo"),
    ("backup", "Respaldo"),
)

CLIENT_NEED_OPTIONS = (
    "Conocer especies presentes",
    "Organizar información histórica",
    "Preparar una campaña nueva",
    "Comparar campañas",
    "Generar mapas",
    "Digitalizar registros",
    "Validar datos",
    "Generar un informe ecológico",
    "Implementar monitoreo periódico",
    "Utilizar la plataforma BioCore",
)


BRIEF_QUESTIONS = (
    QuestionDefinition(
        "has_area_polygon",
        "Área de estudio",
        "¿Existe un polígono digital del área de estudio?",
        QuestionKind.BOOLEAN,
    ),
    QuestionDefinition(
        "has_coordinates",
        "Área de estudio",
        "¿Existen coordenadas del proyecto, predio u observaciones?",
        QuestionKind.BOOLEAN,
    ),
    QuestionDefinition(
        "has_cartography",
        "Área de estudio",
        "¿Existe cartografía, un mapa o imágenes aéreas disponibles?",
        QuestionKind.BOOLEAN,
    ),
    QuestionDefinition(
        "components_of_interest",
        "Componentes ecológicos",
        "¿Qué componentes necesita comprender o revisar?",
        QuestionKind.MULTIPLE,
        options=COMPONENT_OPTIONS,
    ),
    QuestionDefinition(
        "components_with_records",
        "Componentes ecológicos",
        "¿Para qué componentes existen antecedentes o registros?",
        QuestionKind.MULTIPLE,
        options=COMPONENT_OPTIONS,
    ),
    QuestionDefinition(
        "campaign_seasons",
        "Cobertura temporal",
        "¿En qué estaciones se han realizado campañas o levantamientos?",
        QuestionKind.MULTIPLE,
        options=SEASON_OPTIONS,
    ),
    QuestionDefinition(
        "has_multiple_years",
        "Cobertura temporal",
        "¿Existen antecedentes provenientes de más de un año?",
        QuestionKind.BOOLEAN,
    ),
    QuestionDefinition(
        "has_comparable_methods",
        "Cobertura temporal",
        "¿Las campañas utilizaron metodologías comparables?",
        QuestionKind.BOOLEAN,
    ),
    QuestionDefinition(
        "has_species_lists",
        "Antecedentes",
        "¿Existen listados de especies o taxones?",
        QuestionKind.BOOLEAN,
    ),
    QuestionDefinition(
        "has_photographs",
        "Antecedentes",
        "¿Existen fotografías o evidencias asociadas a los registros?",
        QuestionKind.BOOLEAN,
    ),
    QuestionDefinition(
        "has_georeferenced_records",
        "Antecedentes",
        "¿Existen parcelas, transectos, puntos o registros georreferenciados?",
        QuestionKind.BOOLEAN,
    ),
    QuestionDefinition(
        "has_documented_methodology",
        "Calidad y trazabilidad",
        "¿La metodología de levantamiento está documentada?",
        QuestionKind.BOOLEAN,
    ),
    QuestionDefinition(
        "available_record_fields",
        "Calidad y trazabilidad",
        "¿Qué campos están presentes de manera consistente en los registros?",
        QuestionKind.MULTIPLE,
        options=RECORD_FIELD_OPTIONS,
    ),
    QuestionDefinition(
        "identifications_reviewed",
        "Calidad y trazabilidad",
        "¿Las identificaciones fueron revisadas por una persona especialista?",
        QuestionKind.BOOLEAN,
    ),
    QuestionDefinition(
        "has_prior_report",
        "Documentación",
        "¿Existe un informe ecológico previo?",
        QuestionKind.BOOLEAN,
    ),
)


def boolean_rule(
    key: str,
    weight: float,
    found: str,
    missing: str,
) -> ScoringRule:
    return ScoringRule(key, weight, "boolean", found, missing)


def selection_rule(
    key: str,
    weight: float,
    expected: set[str],
    found: str,
    missing: str,
) -> ScoringRule:
    return ScoringRule(
        key,
        weight,
        "selection_coverage",
        found,
        missing,
        frozenset(expected),
    )


DIMENSION_RULES: dict[DiagnosticDimension, tuple[ScoringRule, ...]] = {
    DiagnosticDimension.DOCUMENT_COMPLETENESS: (
        boolean_rule(
            "has_species_lists",
            20,
            "Existen listados de especies o taxones.",
            "No se informaron listados de especies o taxones.",
        ),
        boolean_rule(
            "has_photographs",
            15,
            "Existen fotografías o evidencias.",
            "Faltan fotografías o evidencias asociadas.",
        ),
        boolean_rule(
            "has_documented_methodology",
            25,
            "La metodología está documentada.",
            "La metodología no está documentada.",
        ),
        boolean_rule(
            "has_prior_report",
            20,
            "Existe un informe ecológico previo.",
            "No se informó un documento ecológico previo.",
        ),
        selection_rule(
            "available_record_fields",
            20,
            {"file_version", "backup", "date", "taxon"},
            "Los registros conservan campos documentales relevantes.",
            "Faltan campos documentales y de respaldo.",
        ),
    ),
    DiagnosticDimension.SPATIAL_COVERAGE: (
        boolean_rule(
            "has_area_polygon",
            25,
            "Existe un polígono del área.",
            "Falta un polígono digital del área.",
        ),
        boolean_rule(
            "has_coordinates",
            25,
            "Existen coordenadas.",
            "No se informaron coordenadas.",
        ),
        boolean_rule(
            "has_cartography",
            20,
            "Existe cartografía o apoyo visual.",
            "Falta cartografía o apoyo visual del área.",
        ),
        boolean_rule(
            "has_georeferenced_records",
            20,
            "Existen registros georreferenciados.",
            "Los registros no están georreferenciados.",
        ),
        selection_rule(
            "available_record_fields",
            10,
            {"coordinates", "precision"},
            "Los registros incluyen ubicación y precisión.",
            "Faltan ubicación o precisión en los registros.",
        ),
    ),
    DiagnosticDimension.TEMPORAL_COVERAGE: (
        ScoringRule(
            "campaign_seasons",
            40,
            "count",
            "Existen antecedentes en más de una estación.",
            "La cobertura estacional es limitada o no está informada.",
            target_count=3,
        ),
        boolean_rule(
            "has_multiple_years",
            20,
            "Existen antecedentes de más de un año.",
            "No se informaron antecedentes de varios años.",
        ),
        boolean_rule(
            "has_comparable_methods",
            25,
            "Las campañas tienen metodologías comparables.",
            "La comparabilidad metodológica no está confirmada.",
        ),
        boolean_rule(
            "has_documented_methodology",
            15,
            "La metodología temporal puede revisarse.",
            "Falta metodología para interpretar la cobertura temporal.",
        ),
    ),
    DiagnosticDimension.TAXONOMIC_COVERAGE: (
        ScoringRule(
            "components_with_records",
            60,
            "component_coverage",
            "Hay antecedentes para los componentes seleccionados.",
            "Existen componentes de interés sin antecedentes informados.",
        ),
        boolean_rule(
            "has_species_lists",
            20,
            "Existen listados taxonómicos.",
            "Faltan listados taxonómicos.",
        ),
        boolean_rule(
            "identifications_reviewed",
            20,
            "Las identificaciones fueron revisadas.",
            "La revisión especialista no está confirmada.",
        ),
    ),
    DiagnosticDimension.RECORD_QUALITY: (
        selection_rule(
            "available_record_fields",
            50,
            {
                "date",
                "coordinates",
                "precision",
                "observer",
                "methodology",
                "taxon",
                "habitat",
                "substrate",
            },
            "Los registros incluyen campos de calidad relevantes.",
            "Faltan campos esenciales para evaluar la calidad.",
        ),
        boolean_rule(
            "has_photographs",
            15,
            "Hay evidencia fotográfica.",
            "Falta evidencia fotográfica.",
        ),
        boolean_rule(
            "has_georeferenced_records",
            15,
            "Los registros están georreferenciados.",
            "Falta georreferenciación consistente.",
        ),
        boolean_rule(
            "identifications_reviewed",
            20,
            "Las identificaciones tienen revisión.",
            "Falta confirmar la revisión de identificaciones.",
        ),
    ),
    DiagnosticDimension.TRACEABILITY: (
        boolean_rule(
            "has_documented_methodology",
            20,
            "La metodología está disponible.",
            "Falta documentar la metodología.",
        ),
        selection_rule(
            "available_record_fields",
            60,
            {
                "unique_id",
                "date",
                "observer",
                "campaign",
                "validator",
                "file_version",
                "backup",
            },
            "Los registros conservan campos de trazabilidad.",
            "Faltan identificadores, responsables, versiones o respaldos.",
        ),
        boolean_rule(
            "has_photographs",
            10,
            "Hay evidencia vinculable.",
            "Falta evidencia vinculable a cada registro.",
        ),
        boolean_rule(
            "has_prior_report",
            10,
            "Existe un producto previo para contrastar.",
            "No existe un informe previo para contrastar.",
        ),
    ),
    DiagnosticDimension.GEOSPATIAL_READINESS: (
        boolean_rule(
            "has_area_polygon",
            25,
            "Existe un polígono utilizable.",
            "Falta delimitar digitalmente el área.",
        ),
        boolean_rule(
            "has_coordinates",
            25,
            "Existen coordenadas.",
            "Faltan coordenadas.",
        ),
        boolean_rule(
            "has_cartography",
            20,
            "Existe cartografía.",
            "Falta una base cartográfica.",
        ),
        boolean_rule(
            "has_georeferenced_records",
            20,
            "Existen observaciones georreferenciadas.",
            "Falta georreferenciar observaciones.",
        ),
        selection_rule(
            "available_record_fields",
            10,
            {"precision"},
            "La precisión espacial está registrada.",
            "Falta registrar precisión espacial.",
        ),
    ),
    DiagnosticDimension.CAMPAIGN_COMPARISON_READINESS: (
        ScoringRule(
            "campaign_seasons",
            25,
            "count",
            "Existen campañas en más de una estación.",
            "Hay una sola estación o no se informó la temporada.",
            target_count=2,
        ),
        boolean_rule(
            "has_multiple_years",
            20,
            "Existen datos de más de un año.",
            "No se informaron datos de varios años.",
        ),
        boolean_rule(
            "has_comparable_methods",
            30,
            "Las metodologías son comparables.",
            "La equivalencia metodológica no está confirmada.",
        ),
        boolean_rule(
            "has_documented_methodology",
            15,
            "La metodología puede ser contrastada.",
            "Falta documentar la metodología.",
        ),
        selection_rule(
            "available_record_fields",
            10,
            {"campaign"},
            "Los registros identifican su campaña.",
            "Falta vincular registros con una campaña.",
        ),
    ),
}


DIMENSION_CONTEXT = {
    DiagnosticDimension.DOCUMENT_COMPLETENESS: (
        "La documentación permite comprender qué antecedentes existen y "
        "conservar su contexto.",
        "Organizar y versionar los antecedentes disponibles.",
        ModuleCode.REPORTS,
    ),
    DiagnosticDimension.SPATIAL_COVERAGE: (
        "La cobertura espacial permite interpretar dónde se levantó la información.",
        "Delimitar el área y georreferenciar los registros disponibles.",
        ModuleCode.INTELLIGENCE,
    ),
    DiagnosticDimension.TEMPORAL_COVERAGE: (
        "La cobertura temporal ayuda a reconocer qué periodos están representados.",
        (
            "Revisar profesionalmente si el objetivo, territorio y grupos "
            "biológicos requieren una campaña complementaria."
        ),
        ModuleCode.FIELD,
    ),
    DiagnosticDimension.TAXONOMIC_COVERAGE: (
        "La cobertura taxonómica muestra qué componentes tienen antecedentes.",
        "Revisar y complementar los componentes ecológicos sin información.",
        ModuleCode.FIELD,
    ),
    DiagnosticDimension.RECORD_QUALITY: (
        "Registros completos sostienen análisis y productos reproducibles.",
        "Estandarizar y validar la estructura de los registros.",
        ModuleCode.DARWINCHECK,
    ),
    DiagnosticDimension.TRACEABILITY: (
        "La trazabilidad conecta cada resultado con su evidencia y responsable.",
        "Asignar identificadores, versiones, responsables y respaldos.",
        ModuleCode.DARWINCHECK,
    ),
    DiagnosticDimension.GEOSPATIAL_READINESS: (
        "La preparación geoespacial permite crear mapas y análisis territoriales.",
        "Preparar capas, coordenadas y precisión para revisión geoespacial.",
        ModuleCode.INTELLIGENCE,
    ),
    DiagnosticDimension.CAMPAIGN_COMPARISON_READINESS: (
        "Comparar campañas exige periodos identificables y métodos compatibles.",
        "Estandarizar campañas antes de realizar comparaciones temporales.",
        ModuleCode.INTELLIGENCE,
    ),
}


DIMENSION_LABELS = {
    DiagnosticDimension.DOCUMENT_COMPLETENESS: "Completitud documental",
    DiagnosticDimension.SPATIAL_COVERAGE: "Cobertura espacial",
    DiagnosticDimension.TEMPORAL_COVERAGE: "Cobertura temporal",
    DiagnosticDimension.TAXONOMIC_COVERAGE: "Cobertura taxonómica",
    DiagnosticDimension.RECORD_QUALITY: "Calidad de los registros",
    DiagnosticDimension.TRACEABILITY: "Trazabilidad",
    DiagnosticDimension.GEOSPATIAL_READINESS: "Preparación geoespacial",
    DiagnosticDimension.CAMPAIGN_COMPARISON_READINESS: (
        "Preparación para comparar campañas"
    ),
}
