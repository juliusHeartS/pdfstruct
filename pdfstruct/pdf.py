"""
pdfstruct/pdf.py

Módulo especializado en el procesamiento de PDFs.
Actúa como orquestador que combina extracción con PyMuPDF4LLM,
validación cruzada y enriquecimiento.
"""

import fitz
from pathlib import Path
from .core import ExtractionResult
from .extractors.pymupdf4llm_extractor import PyMuPDF4LLMExtractor
from .extractors.marker_extractor import MarkerExtractor
from .extractors.markitdown_extractor import MarkItDownExtractor
from .enrichers.cross_validator import CrossValidator
from .enrichers.table_post_processor import TablePostProcessor
from .utils import clean_ocr_garbage, normalize_text


class PDFProcessor:
    """
    Procesador especializado para PDFs.

    Utiliza PyMuPDF4LLM como extractor principal por defecto, con soporte
    opcional para Marker. Incluye validación cruzada y reparación de tablas.
    """

    def __init__(
        self,
        images_output_dir: str = "pdf_images",
        extractor: str = "pymupdf4llm",
    ):
        self.extractor_name = extractor.lower().strip()
        self.pymupdf_extractor = PyMuPDF4LLMExtractor()
        self.marker_extractor: MarkerExtractor | None = None
        self.markitdown_extractor = MarkItDownExtractor()
        self.cross_validator = CrossValidator()
        self.table_post_processor = TablePostProcessor()
        self.images_output_dir = Path(images_output_dir)

        if self.extractor_name == "marker":
            self.marker_extractor = MarkerExtractor()

    def extract(self, pdf_path: str | Path) -> ExtractionResult:
        """
        Extrae un PDF utilizando el extractor configurado.
        """
        pdf_path = Path(pdf_path).resolve()

        if not pdf_path.exists():
            raise FileNotFoundError(f"No se encontró el PDF: {pdf_path}")

        doc = fitz.open(str(pdf_path))
        total_pages = len(doc)
        doc.close()

        # Extracción principal con marcadores de página
        if self.extractor_name == "marker" and self.marker_extractor is not None:
            markdown_content = self.marker_extractor.extract(pdf_path)
        else:
            markdown_content = self._build_markdown_with_page_markers(pdf_path, total_pages)

        # Limpieza de artefactos de OCR
        markdown_content = clean_ocr_garbage(markdown_content)

        # Normalización de texto
        markdown_content = normalize_text(markdown_content)

        # Reparación conservadora de tablas
        markdown_content = self.table_post_processor.process(markdown_content)

        # Validación cruzada (MarkItDown como referencia)
        try:
            secondary_markdown = self.markitdown_extractor.extract(pdf_path)
            validation_result = self.cross_validator.validate(
                primary_markdown=markdown_content,
                secondary_markdown=secondary_markdown
            )
        except Exception:
            validation_result = None

        images_found, images_dir = self._extract_images(pdf_path)

        metadata = {
            "source_file": str(pdf_path),
            "file_type": ".pdf",
            "extractor": self.extractor_name,
            "is_pdf": True,
            "total_pages": total_pages,
            "images_found": images_found,
        }

        if images_dir is not None:
            metadata["images_dir"] = str(images_dir)

        if validation_result:
            metadata["cross_validation_warnings"] = validation_result.warnings
            metadata["cross_validation"] = validation_result.metadata

        return ExtractionResult(
            markdown=markdown_content,
            images_dir=images_dir,
            metadata=metadata
        )

    def _build_markdown_with_page_markers(self, pdf_path: Path, total_pages: int) -> str:
        """
        Extrae el PDF página por página e inserta un marcador <!-- PAGE: N / total -->
        antes del contenido de cada página.
        """
        if self.extractor_name == "marker" and self.marker_extractor is not None:
            pages = self.marker_extractor.extract_pages(pdf_path)
        else:
            pages = self.pymupdf_extractor.extract_pages(pdf_path)
        parts = []

        for page_number, page_text in enumerate(pages, start=1):
            marker = f"<!-- PAGE: {page_number} / {total_pages} -->"
            if page_text.strip():
                parts.append(f"{marker}\n\n{page_text.strip()}")
            else:
                parts.append(marker)

        return "\n\n".join(parts)

    def _extract_images(self, pdf_path: Path) -> tuple[int, Path | None]:
        """
        Extrae imágenes del PDF si superan un umbral de tamaño.

        Returns:
            (cantidad de imágenes encontradas, directorio de imágenes o None).
        """
        images_dir = self.images_output_dir / pdf_path.stem
        images_dir.mkdir(parents=True, exist_ok=True)

        doc = fitz.open(str(pdf_path))
        images_found = 0

        try:
            for page_index in range(len(doc)):
                page = doc.load_page(page_index)
                image_list = page.get_images(full=True)

                for img_index, img in enumerate(image_list, start=1):
                    xref = img[0]
                    base_image = doc.extract_image(xref)
                    image_bytes = base_image["image"]

                    if len(image_bytes) < 2048:
                        continue

                    ext = base_image["ext"]
                    image_filename = f"page_{page_index + 1}_img_{img_index}.{ext}"
                    image_path = images_dir / image_filename
                    image_path.write_bytes(image_bytes)
                    images_found += 1
        finally:
            doc.close()

        if images_found == 0:
            return 0, None

        return images_found, images_dir
