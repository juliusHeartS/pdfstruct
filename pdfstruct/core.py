"""
pdfstruct/core.py

Clase principal PdfStruct con integración real de MarkItDown.
"""

from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

from .extractors.markitdown_extractor import MarkItDownExtractor


@dataclass
class ExtractionResult:
    """Resultado de la extracción de un documento."""
    markdown: str
    output_path: Optional[Path] = None
    images_dir: Optional[Path] = None
    metadata: dict = field(default_factory=dict)


class PdfStruct:
    """
    Extractor de documentos a Markdown.

    - Usa MarkItDownExtractor para documentos generales.
    - Cuando el documento es PDF, usa PDFProcessor (MarkItDown + PyMuPDF).
    """

    def __init__(self, images_output_dir: str = "pdf_images"):
        self.markitdown_extractor = MarkItDownExtractor()
        self.images_output_dir = Path(images_output_dir)
        self._pdf_processor: "PDFProcessor" | None = None

    def _get_pdf_processor(self) -> "PDFProcessor":
        from .pdf import PDFProcessor
        if self._pdf_processor is None:
            self._pdf_processor = PDFProcessor(images_output_dir=str(self.images_output_dir))
        return self._pdf_processor

    def extract(self, document_path: str | Path) -> ExtractionResult:
        """
        Extrae un documento y devuelve Markdown de calidad.

        Args:
            document_path: Ruta al documento (PDF, DOCX, PPTX, etc.)

        Returns:
            ExtractionResult con el markdown generado.
        """
        document_path = Path(document_path).resolve()

        if not document_path.exists():
            raise FileNotFoundError(f"No se encontró el documento: {document_path}")

        is_pdf = document_path.suffix.lower() == ".pdf"

        if is_pdf:
            result = self._get_pdf_processor().extract(document_path)
            result.metadata["is_pdf"] = True
            return result
        else:
            markdown_content = self.markitdown_extractor.extract(document_path)
            metadata = {
                "source_file": str(document_path),
                "file_type": document_path.suffix.lower(),
                "extractor": "markitdown",
                "is_pdf": False,
            }
            return ExtractionResult(markdown=markdown_content, metadata=metadata)
