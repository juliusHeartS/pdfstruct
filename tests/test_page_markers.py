"""
tests/test_page_markers.py

Tests básicos para page_markers.
"""

import fitz
from pathlib import Path
from pdfstruct.enrichers.page_markers import add_page_markers


def _create_multi_page_pdf(output_path: Path, pages_texts: list[str]) -> Path:
    """Crea un PDF de prueba con varias páginas y texto específico."""
    doc = fitz.open()
    for text in pages_texts:
        page = doc.new_page(width=300, height=200)
        page.insert_text((20, 20), text)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(output_path))
    doc.close()
    return output_path


def test_add_page_markers(tmp_path: Path):
    pdf_path = tmp_path / "test_pages.pdf"
    pages = ["Página uno del documento", "Página dos del documento"]
    _create_multi_page_pdf(pdf_path, pages)

    markdown = "# Introducción\n\nPágina uno del documento\n\n## Siguiente\n\nPágina dos del documento"
    enriched = add_page_markers(markdown, pdf_path)

    assert "<!-- PAGE: 1 -->" in enriched
    assert "<!-- PAGE: 2 -->" in enriched
