"""
pdfstruct/document.py

Módulo base para manejo general de documentos.
Actualmente es una capa delgada. Sirve como punto de extensión
para lógica común entre diferentes tipos de documentos.
"""

from pathlib import Path
from typing import Optional
from .core import ExtractionResult
from .extractors.markitdown_extractor import MarkItDownExtractor


class DocumentProcessor:
    """
    Procesador genérico de documentos (no PDF).

    Por ahora simplemente usa MarkItDownExtractor.
    En el futuro puede contener lógica común (limpieza de texto,
    normalización, metadata estándar, etc.).
    """

    def __init__(self):
        self.extractor = MarkItDownExtractor()

    def extract(self, document_path: str | Path) -> ExtractionResult:
        """
        Extrae un documento genérico (DOCX, PPTX, XLSX, HTML, etc.).
        """
        document_path = Path(document_path).resolve()

        if not document_path.exists():
            raise FileNotFoundError(f"No se encontró el documento: {document_path}")

        markdown_content = self.extractor.extract(document_path)

        metadata = {
            "source_file": str(document_path),
            "file_type": document_path.suffix.lower(),
            "extractor": "markitdown",
            "is_pdf": False,
        }

        return ExtractionResult(
            markdown=markdown_content,
            metadata=metadata,
        )