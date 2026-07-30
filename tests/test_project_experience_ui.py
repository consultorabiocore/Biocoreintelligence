from pathlib import Path


def _source() -> str:
    return Path("platform_pages/projects.py").read_text(encoding="utf-8")


def test_project_list_exposes_customer_status_and_clear_actions() -> None:
    source = _source()
    for label in (
        "Etapa",
        "Avance",
        "Responsable",
        "Actualizado",
        "Próxima actividad",
        '"Abrir"',
        '"Editar"',
        '"Archivar"',
    ):
        assert label in source


def test_project_creation_reviews_before_persisting_and_redirects() -> None:
    source = _source()
    review_position = source.index('"Revisar datos"')
    confirm_position = source.index('"Confirmar y crear"')
    create_position = source.index("service.create(context, draft)")
    assert review_position < confirm_position < create_position
    assert '_go("detail", created.id)' in source


def test_project_dashboard_and_edit_cover_feedback_states() -> None:
    source = _source()
    for copy in (
        "Resumen ejecutivo",
        "Línea de tiempo",
        "Actividad reciente",
        "Documentos y registros recientes",
        "Próximo hito",
        "Tienes cambios sin guardar",
        "Cambios guardados",
        "No pudimos completar la operación",
        "Tu rol no permite",
        "sesión",
    ):
        assert copy in source


def test_archiving_is_explained_and_never_deletes() -> None:
    source = _source()
    assert "Archivar no elimina el proyecto" in source
    assert "service.archive" in source
    assert "service.delete" not in source
