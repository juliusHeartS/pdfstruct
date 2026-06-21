"""
pdfstruct/pdf.py

Módulo especializado en el procesamiento de PDFs.
Actúa como orquestador que combina extracción con PyMuPDF4LLM,
GLM-OCR via Ollama (opcional), validación cruzada y enriquecimiento.
"""

import fitz
import logging
from pathlib import Path
from typing import Any, Callable

from .config import GlmOcrConfig
from .core import ExtractionResult
from .exceptions import ConfigurationError, ExtractionError, FileError
from .extractors.markitdown_extractor import MarkItDownExtractor
from .extractors.pymupdf4llm_extractor import PyMuPDF4LLMExtractor
from .enrichers.cross_validator import CrossValidator
from .enrichers.ollama_enricher import OllamaEnricher
from .enrichers.table_post_processor import TablePostProcessor
from .utils import clean_ocr_garbage, normalize_text

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[str, int, int], None]


class PDFProcessor:
    """
    Procesador especializado para PDFs.

    Utiliza PyMuPDF4LLM como extractor principal por defecto. Cuando se
    configura GLM-OCR via Ollama, detecta tablas y figuras con PyMuPDF y
    las enriquece con el modelo GLM-OCR. Incluye validación cruzada y
    reparación de tablas.
    """

    def __init__(
        self,
        images_output_dir: str = "pdf_images",
        glm_ocr_config: GlmOcrConfig | None = None,
    ):
        self.extractor_name = "pymupdf4llm"
        self.glm_ocr_config = glm_ocr_config or GlmOcrConfig()
        self.pymupdf_extractor = PyMuPDF4LLMExtractor()
        self.ollama_enricher: OllamaEnricher | None = None
        self.markitdown_extractor = MarkItDownExtractor()
        self.cross_validator = CrossValidator()
        self.table_post_processor = TablePostProcessor()
        self.images_output_dir = Path(images_output_dir)

        if self.glm_ocr_config.enabled:
            self.ollama_enricher = OllamaEnricher(self.glm_ocr_config)
            if not self.ollama_enricher.client.is_available():
                raise ConfigurationError(
                    f"GLM-OCR está habilitado pero Ollama no responde en "
                    f"{self.glm_ocr_config.url}. "
                    f"Asegúrate de que 'ollama serve' esté corriendo y el modelo "
                    f"'{self.glm_ocr_config.model}' esté disponible."
                )

    def extract(
        self,
        pdf_path: str | Path,
        output_path: str | Path | None = None,
        max_pages: int | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> ExtractionResult:
        """
        Extrae un PDF utilizando el extractor configurado.

        Args:
            pdf_path: Ruta al archivo PDF.
            output_path: Ruta opcional donde se guardará el Markdown. Si se
                proporciona, las referencias a imágenes se generan relativas
                a su directorio.
            max_pages: Número máximo de páginas a procesar. Útil para
                procesar solo un prefijo de documentos grandes.
            progress_callback: Función opcional ``(stage, current, total)``
                que recibe actualizaciones de progreso.

        Returns:
            ExtractionResult con el Markdown generado y metadata.

        Raises:
            FileError: Si el archivo no existe.
            ExtractionError: Si ocurre un error durante la extracción.
        """
        pdf_path = Path(pdf_path).resolve()

        if not pdf_path.exists():
            raise FileError(f"No se encontró el PDF: {pdf_path}")

        logger.info("Extrayendo PDF: %s", pdf_path)

        output_dir: Path | None = None
        if output_path is not None:
            output_dir = Path(output_path).resolve().parent

        try:
            doc = fitz.open(str(pdf_path))
            total_pages = len(doc)
            doc.close()
        except Exception as exc:
            raise ExtractionError(f"No se pudo abrir el PDF {pdf_path}: {exc}") from exc

        metadata = {
            "source_file": str(pdf_path),
            "file_type": ".pdf",
            "extractor": self.extractor_name,
            "is_pdf": True,
            "total_pages": total_pages,
            "glm_ocr_enabled": self.glm_ocr_config.enabled,
        }

        # Extracción base con PyMuPDF4LLM y marcadores de página.
        try:
            page_chunks, markdown_content = self._extract_page_chunks(
                pdf_path, max_pages=max_pages
            )
        except Exception as exc:
            raise ExtractionError(
                f"Error en extracción base de {pdf_path}: {exc}"
            ) from exc

        # Enriquecimiento opcional con GLM-OCR via Ollama.
        images_dir: Path | None = None
        if self.ollama_enricher is not None:
            images_dir = self.images_output_dir / pdf_path.stem
            images_dir.mkdir(parents=True, exist_ok=True)
            logger.info("Enriqueciendo con GLM-OCR: %s", pdf_path)
            markdown_content, page_count, figure_count = self.ollama_enricher.enrich(
                pdf_path,
                page_chunks,
                images_dir=images_dir,
                output_dir=output_dir,
                filename_prefix=pdf_path.stem,
                progress_callback=progress_callback,
            )
            metadata["ollama_pages_processed"] = page_count
            metadata["ollama_figures_processed"] = figure_count
            metadata["extractor"] = "ollama+pymupdf"
            logger.info(
                "GLM-OCR procesó %d páginas y %d figuras",
                page_count,
                figure_count,
            )
        else:
            logger.info("Extrayendo imágenes embebidas del PDF")
            images_found, images_dir = self._extract_images(pdf_path)
            metadata["images_found"] = images_found

        # Limpieza de artefactos de OCR.
        markdown_content = clean_ocr_garbage(markdown_content)

        # Normalización de texto.
        markdown_content = normalize_text(markdown_content)

        # Reparación conservadora de tablas.
        markdown_content = self.table_post_processor.process(markdown_content)

        # Validación cruzada opcional (MarkItDown como referencia).
        # Se omite cuando GLM-OCR está activo para evitar el costo de OCR doble.
        validation_result = None
        if not self.glm_ocr_config.enabled:
            try:
                secondary_markdown = self.markitdown_extractor.extract(pdf_path)
                validation_result = self.cross_validator.validate(
                    primary_markdown=markdown_content,
                    secondary_markdown=secondary_markdown,
                )
            except Exception:
                validation_result = None

        if images_dir is not None:
            metadata["images_dir"] = str(images_dir)

        if validation_result:
            metadata["cross_validation_warnings"] = validation_result.warnings
            metadata["cross_validation"] = validation_result.metadata

        return ExtractionResult(
            markdown=markdown_content, images_dir=images_dir, metadata=metadata
        )

    def _extract_page_chunks(
        self,
        pdf_path: Path,
        max_pages: int | None = None,
    ) -> tuple[list[dict[str, Any]], str]:
        """
        Extrae el PDF página por página con PyMuPDF4LLM.

        Args:
            max_pages: Número máximo de páginas a extraer.

        Returns:
            (page_chunks, markdown_completo_con_marcadores)
        """
        page_chunks = self.pymupdf_extractor._extract_page_chunks(pdf_path)
        if max_pages is not None:
            page_chunks = page_chunks[:max_pages]
        total_pages = len(page_chunks)
        parts = []

        for page_number, chunk in enumerate(page_chunks, start=1):
            marker = f"<!-- PAGE: {page_number} / {total_pages} -->"
            text = chunk.get("text", "").strip()
            if text:
                parts.append(f"{marker}\n\n{text}")
            else:
                parts.append(marker)

        return page_chunks, "\n\n".join(parts)

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
