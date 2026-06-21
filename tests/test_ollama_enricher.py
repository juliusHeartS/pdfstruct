"""
tests/test_ollama_enricher.py

Tests para el enriquecedor Ollama (OCR de página completa + figuras).
"""

import fitz
from pathlib import Path
from unittest.mock import Mock


from pdfstruct.config import GlmOcrConfig
from pdfstruct.enrichers.ollama_enricher import (
    OllamaEnricher,
    _convert_html_tables_to_markdown,
)


def _create_pdf_with_table_and_image(tmp_path: Path) -> Path:
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)

    # Tabla simple.
    table = [["Año", "Valor"], ["2022", "100"], ["2023", "150"]]
    cw, ch = 120, 30
    sx, sy = 100, 150
    for i, row in enumerate(table):
        for j, cell in enumerate(row):
            rect = fitz.Rect(
                sx + j * cw, sy + i * ch, sx + (j + 1) * cw, sy + (i + 1) * ch
            )
            page.draw_rect(rect, color=(0, 0, 0), width=1)
            page.insert_text((rect.x0 + 5, rect.y0 + 20), cell, fontsize=12)

    # Imagen roja.
    w, h = 50, 50
    samples = b"".join(
        __import__("struct").pack(">BBB", 255, 0, 0) for _ in range(w * h)
    )
    pixmap = fitz.Pixmap(fitz.csRGB, w, h, samples, 0)
    page.insert_image(fitz.Rect(100, 300, 200, 400), pixmap=pixmap)

    pdf_path = tmp_path / "mixed.pdf"
    doc.save(str(pdf_path))
    doc.close()
    return pdf_path


def test_convert_html_tables_to_markdown():
    html = "<table><tr><td>A</td><td>B</td></tr><tr><td>1</td><td>2</td></tr></table>"
    result = _convert_html_tables_to_markdown(html)
    assert "| A | B |" in result
    assert "| 1 | 2 |" in result


def test_enrich_uses_ollama_page_ocr(tmp_path: Path):
    pdf_path = _create_pdf_with_table_and_image(tmp_path)
    config = GlmOcrConfig(enabled=True)
    enricher = OllamaEnricher(config)

    # Simular respuesta de OCR de página completa.
    enricher.client.generate = Mock(
        return_value="# Reporte\n\n| Año | Ventas |\n|---|---|\n| 2022 | $100 |"
    )
    enricher.client.describe_figure = Mock(return_value="Figura roja")

    page_chunks = [{"text": "baseline", "metadata": {"page": 1}}]

    markdown, pages, figures = enricher.enrich(
        pdf_path,
        page_chunks,
        images_dir=tmp_path / "images",
        filename_prefix="test",
    )

    assert pages == 1
    assert "<!-- PAGE: 1 / 1 -->" in markdown
    assert "# Reporte" in markdown
    assert "| Año | Ventas |" in markdown
    enricher.client.generate.assert_called_once()


def test_enrich_with_empty_chunks_returns_empty(tmp_path: Path):
    pdf_path = _create_pdf_with_table_and_image(tmp_path)
    config = GlmOcrConfig(enabled=True)
    enricher = OllamaEnricher(config)

    enricher.client.generate = Mock(return_value="")
    enricher.client.describe_figure = Mock(return_value="")

    markdown, pages, figures = enricher.enrich(
        pdf_path,
        page_chunks=[],
        images_dir=tmp_path / "images",
        filename_prefix="test",
    )

    assert markdown == ""
    assert pages == 0
    assert figures == 0


def test_enrich_figures_use_relative_paths_when_output_dir_given(tmp_path: Path):
    pdf_path = _create_pdf_with_table_and_image(tmp_path)
    config = GlmOcrConfig(enabled=True)
    enricher = OllamaEnricher(config)

    enricher.client.generate = Mock(
        return_value="# Reporte\n\n**==> picture [50 x 50] intentionally omitted <==**"
    )
    enricher.client.describe_figure = Mock(return_value="Figura roja")

    images_dir = tmp_path / "images"
    output_dir = tmp_path / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    markdown, pages, figures = enricher.enrich(
        pdf_path,
        page_chunks=[{"text": "baseline", "metadata": {"page": 1}}],
        images_dir=images_dir,
        output_dir=output_dir,
        filename_prefix="test",
    )

    assert figures == 1
    expected_reference = "../images/test_figure_0001.png"
    assert expected_reference in markdown
