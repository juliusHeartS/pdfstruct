"""
tests/test_marker_extractor.py

Tests para el extractor de Marker (métodos auxiliares que no requieren
modelos descargados).
"""

import pytest

from pdfstruct.extractors.marker_extractor import MarkerExtractor


def test_replace_page_spans_inserts_markers():
    text = (
        "Inicio\n\n"
        '<span id="page-7-0"></span>\nSección 7\n\n'
        '<span id="page-8-0"></span>\nSección 8'
    )
    result = MarkerExtractor._replace_page_spans(text)
    assert "<!-- PAGE: 7 / 8 -->" in result
    assert "<!-- PAGE: 8 / 8 -->" in result
    assert '<span id="page-' not in result


def test_replace_page_spans_without_spans_returns_text():
    text = "Documento sin anclas de página."
    assert MarkerExtractor._replace_page_spans(text) == text


def test_split_by_page_spans():
    text = (
        "Portada\n\n"
        '<span id="page-2-0"></span>\nPágina 2\n\n'
        '<span id="page-3-0"></span>\nPágina 3'
    )
    pages = MarkerExtractor._split_by_page_spans(text)
    # La lista es 0-indexada: índice 0 = página 1.
    assert pages[0] == "Portada"
    assert pages[1] == "Página 2"
    assert pages[2] == "Página 3"


def test_split_by_page_spans_without_spans():
    text = "Documento completo."
    assert MarkerExtractor._split_by_page_spans(text) == [text]
