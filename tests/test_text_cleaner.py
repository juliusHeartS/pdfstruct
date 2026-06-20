"""
tests/test_text_cleaner.py

Tests para text_cleaner.
"""

from pdfstruct.enrichers.text_cleaner import (
    merge_short_lines,
    remove_duplicate_blocks,
    clean_markdown,
)


def test_merge_short_lines():
    markdown = (
        "La situación de la enfermería\n"
        "en la Región de las Américas\n"
        "Informe final del Foro Regional para el\n"
        "Avance de la Enfermería en América Latina\n\n"
        "Este es otro párrafo completo.\n"
    )
    result = merge_short_lines(markdown)
    assert "La situación de la enfermería en la Región de las Américas" in result
    assert "Informe final del Foro Regional para el Avance de la Enfermería" in result
    assert "Este es otro párrafo completo." in result


def test_merge_does_not_break_headers():
    markdown = "# Título\n\nTexto del\nprimer párrafo.\n\n## Subtítulo\n\nOtro texto."
    result = merge_short_lines(markdown)
    assert "# Título" in result
    assert "## Subtítulo" in result


def test_merge_preserves_lists():
    markdown = "- Item uno\n- Item dos\n- Item tres"
    result = merge_short_lines(markdown)
    assert "- Item uno" in result
    assert "- Item dos" in result


def test_remove_page_numbers():
    markdown = "Texto de prueba\n12\nOtro párrafo.\n\nv\nMás texto."
    result = merge_short_lines(markdown)
    assert "12" not in result
    assert "v\n" not in result
    assert "Otro párrafo." in result


def test_remove_duplicate_blocks():
    markdown = "Bloque único.\n\nBloque único.\n\nOtro bloque."
    result = remove_duplicate_blocks(markdown)
    assert result.count("Bloque único.") == 1
    assert "Otro bloque." in result


def test_clean_markdown_pipeline():
    markdown = (
        "La situación de la enfermería\n"
        "en la Región de las Américas\n\n"
        "La situación de la enfermería\n"
        "en la Región de las Américas\n\n"
        "12\n"
        "Texto final."
    )
    result = clean_markdown(markdown)
    assert "La situación de la enfermería en la Región de las Américas" in result
    assert result.count("La situación de la enfermería en la Región de las Américas") == 1
    assert "12" not in result
    assert "Texto final." in result
