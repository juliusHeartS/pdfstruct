"""
pdfstruct/document.py

Procesador para documentos que no son PDF (DOCX, XLSX, PPTX, etc.).
Utiliza MarkItDownExtractor como motor principal.
"""

from pathlib import Path
from .core import ExtractionResult
from .extractors.markitdown_extractor import MarkItDownExtractor


class DocumentProcessor:
    """
    Procesador para documentos que no son PDF.

    Actualmente utiliza MarkItDown como extractor principal.
    """

    def __init__(self):
        self.extractor = MarkItDownExtractor()

    def extract(self, document_path: str | Path) -> ExtractionResult:
        """
        Extrae un documento que no es PDF y devuelve el resultado.
        """
        document_path = Path(document_path).resolve()

        if not document_path.exists():
            raise FileNotFoundError(f"No se encontró el documento: {document_path}")

        markdown_content = self.extractor.extract(document_path)

        metadata = {
            "source_file": str(document_path),
            "file_type": document_path.suffix.lower(),
            "extractor": "markitdown",
        }

        from .core import ExtractionResult

        return ExtractionResult(markdown=markdown_content, metadata=metadata)
