"""
tests/test_integration.py

Tests de integración con PDFs reales del corpus paho_pdfs.

Estos tests requieren que el directorio ``paho_pdfs`` exista en la raíz del
proyecto. Los tests con GLM-OCR se saltan automáticamente si Ollama no está
disponible.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pdfstruct import PdfStruct
from pdfstruct.config import GlmOcrConfig
from pdfstruct.extractors.ollama_glm_ocr_client import OllamaGlmOcrClient


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PAHO_DIR = PROJECT_ROOT / "paho_pdfs"

# Corpus representativo: políticas, libros técnicos, informes de país,
# descripciones organizacionales e informes en español y portugués.
SELECTED_PDFS = [
    "PDF_ENG/doc_02_link.1_politica-ingles-2030-english-final.pdf",
    "PDF_ENG/doc_03_link.1_01_9789275129708_eng.pdf",
    "PDF_ENG/doc_04_link.1_sub1_01_guatemala.pdf",
    "PDF_ENG/doc_05_link.1_iris3_01_9789275129791_eng.pdf",
    "doc_05_link.1_sub2_01_org-chart-may-20-2026.pdf",
    "PDF_SPA/doc_06_link_01_OPSHSSHR250010_spa.pdf",
    "PDF_SPA/doc_07_link_01_OPSHSSHR250007_spa.pdf",
    "PDF_SPA/doc_08_link_01_OPSHSSHR250009_spa.pdf",
    "PDF_SPA/doc_09_link_01_OPSHSSHR250008_spa.pdf",
    "PDF_POR/doc_18_link.2_01_9789275720035_por.pdf",
]

GLM_OCR_PDFS = [
    "PDF_SPA/doc_03_link_01_9789275329702_spa.pdf",
    "PDF_ENG/doc_03_link.1_01_9789275129708_eng.pdf",
    "doc_05_link.1_sub2_01_org-chart-may-20-2026.pdf",
]


def _pdf_paths() -> list[Path]:
    paths = [PAHO_DIR / rel for rel in SELECTED_PDFS]
    return [p for p in paths if p.exists()]


def _glm_ocr_pdf_paths() -> list[Path]:
    paths = [PAHO_DIR / rel for rel in GLM_OCR_PDFS]
    return [p for p in paths if p.exists()]


def _ollama_available() -> bool:
    return OllamaGlmOcrClient(GlmOcrConfig()).is_available()


@pytest.mark.integration
@pytest.mark.parametrize("pdf_path", _pdf_paths(), ids=lambda p: p.name)
def test_extract_paho_pdf_without_ocr(pdf_path: Path, tmp_path: Path):
    """La extracción base debe funcionar para todos los PDFs seleccionados."""
    struct = PdfStruct(images_output_dir=str(tmp_path / "images"))
    result = struct.extract(pdf_path, output_path=tmp_path / "out.md", max_pages=2)

    assert result.markdown.strip()
    assert result.metadata["file_type"] == ".pdf"
    assert result.metadata["is_pdf"] is True
    assert result.metadata["total_pages"] >= 1
    assert result.metadata["glm_ocr_enabled"] is False


@pytest.mark.integration
@pytest.mark.parametrize("pdf_path", _glm_ocr_pdf_paths(), ids=lambda p: p.name)
def test_extract_paho_pdf_with_glm_ocr(pdf_path: Path, tmp_path: Path):
    """GLM-OCR debe enriquecer tablas y figuras cuando Ollama está disponible."""
    if not _ollama_available():
        pytest.skip("Ollama no está disponible")

    config = GlmOcrConfig(enabled=True)
    struct = PdfStruct(
        images_output_dir=str(tmp_path / "images"),
        glm_ocr_config=config,
    )
    result = struct.extract(pdf_path, output_path=tmp_path / "out.md", max_pages=1)

    assert result.markdown.strip()
    assert result.metadata["glm_ocr_enabled"] is True
    assert result.metadata["ollama_pages_processed"] >= 1
    assert "<!-- PAGE:" in result.markdown
