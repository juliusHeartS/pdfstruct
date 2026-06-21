"""
pdfstruct/core.py

Clase principal PdfStruct.
Actúa como punto de entrada y decide qué procesador utilizar
según el tipo de documento.
"""

from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .pdf import PDFProcessor
    from .document import DocumentProcessor


@dataclass
class ExtractionResult:
    """Resultado de la extracción de un documento."""
    markdown: str
    output_path: Optional[Path] = None
    images_dir: Optional[Path] = None
    metadata: dict = field(default_factory=dict)


class PdfStruct:
    """
    Extractor principal de documentos a Markdown.

    - Para PDFs: utiliza PDFProcessor (basado en PyMuPDF4LLM).
    - Para otros documentos: utiliza DocumentProcessor.
    """

    def __init__(self, images_output_dir: str = "pdf_images", extractor: str = "pymupdf4llm"):
        self.images_output_dir = images_output_dir
        from .pdf import PDFProcessor
        from .document import DocumentProcessor
        self.pdf_processor = PDFProcessor(images_output_dir=images_output_dir, extractor=extractor)
        self.document_processor = DocumentProcessor()

    def extract(self, document_path: str | Path) -> ExtractionResult:
        """
        Extrae un documento y devuelve el resultado en formato Markdown.

        Args:
            document_path: Ruta al documento.

        Returns:
            ExtractionResult con el markdown generado.
        """
        document_path = Path(document_path).resolve()

        if not document_path.exists():
            raise FileNotFoundError(f"No se encontró el documento: {document_path}")

        is_pdf = document_path.suffix.lower() == ".pdf"

        if is_pdf:
            return self.pdf_processor.extract(document_path)
        else:
            return self.document_processor.extract(document_path)

    def extract_to_file(
        self,
        document_path: str | Path,
        output_path: Optional[str | Path] = None
    ) -> Path:
        """
        Extrae el documento y lo guarda en un archivo Markdown.
        """
        result = self.extract(document_path)

        if output_path is None:
            document_path = Path(document_path)
            output_path = document_path.with_suffix(".structured.md")

        output_path = Path(output_path)
        output_path.write_text(result.markdown, encoding="utf-8")
        result.output_path = output_path

        return output_path
