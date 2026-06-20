"""
pdfstruct/pdf.py

Módulo especializado en el procesamiento de PDFs.
Combina MarkItDown + PyMuPDF para obtener el mejor resultado posible
(imágenes, páginas, tablas, etc.).
"""

from pathlib import Path
import fitz

from .core import ExtractionResult
from .extractors.markitdown_extractor import MarkItDownExtractor
from .enrichers.page_markers import add_page_markers
from .enrichers.image_handler import extract_and_save_images, create_image_references
from .enrichers.text_cleaner import clean_markdown


class PDFProcessor:
    """
    Procesador especializado para PDFs.

    Combina:
    - MarkItDownExtractor (Markdown base)
    - PyMuPDF (imágenes, páginas, estructura)
    """

    def __init__(self, images_output_dir: str = "pdf_images"):
        self.markitdown = MarkItDownExtractor()
        self.images_output_dir = Path(images_output_dir)

    def extract(self, pdf_path: str | Path) -> ExtractionResult:
        """
        Extrae un PDF combinando MarkItDown + PyMuPDF.

        Abre el PDF una sola vez para evitar I/O redundante en producción.
        """
        pdf_path = Path(pdf_path).resolve()

        if not pdf_path.exists():
            raise FileNotFoundError(f"No se encontró el PDF: {pdf_path}")

        doc = fitz.open(str(pdf_path))
        try:
            page_count = len(doc)
            has_images = any(page.get_images() for page in doc)

            # Markdown base con MarkItDown (MarkItDown abre el archivo por su cuenta)
            markdown_content = self.markitdown.extract(pdf_path)

            # Limpieza de texto: une líneas sueltas en párrafos, quita duplicados, etc.
            try:
                markdown_content = clean_markdown(markdown_content)
            except Exception:
                # Si falla la limpieza, seguimos con el markdown original
                pass

            # Marcadores de página usando el documento ya abierto
            try:
                markdown_content = add_page_markers(markdown_content, doc)
            except Exception:
                # Si falla el enriquecimiento de páginas, no rompemos la extracción
                pass

            # Imágenes
            images_dir: Path | None = None
            images_found = 0
            saved_images: list[dict] = []
            if has_images:
                images_dir = self.images_output_dir / pdf_path.stem
                saved_images = extract_and_save_images(
                    pdf_path, images_dir, doc=doc
                )
                if saved_images:
                    image_section = create_image_references(saved_images, images_dir)
                    markdown_content = markdown_content + image_section
                else:
                    images_dir = None
                images_found = len(saved_images)

            metadata = {
                "source_file": str(pdf_path),
                "file_type": ".pdf",
                "extractor": "markitdown + pymupdf",
                "total_pages": page_count,
                "images_found": images_found,
            }

            return ExtractionResult(
                markdown=markdown_content,
                images_dir=images_dir,
                metadata=metadata,
            )
        finally:
            doc.close()
