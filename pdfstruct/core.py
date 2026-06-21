"""
pdfstruct/core.py

Clase principal PdfStruct.
Actúa como punto de entrada y decide qué procesador utilizar
según el tipo de documento.
"""

from pathlib import Path
from dataclasses import dataclass, field
from typing import Callable, Literal, Optional, TYPE_CHECKING

from .config import Config, GlmOcrConfig
from .exceptions import FileError

if TYPE_CHECKING:
    pass

ProgressCallback = Callable[[str, int, int], None]


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

    Modos de operación:
        - ``soft`` (default): extracción rápida con PyMuPDF4LLM, sin OCR
          enrichment.
        - ``hard``: extracción con GLM-OCR via Ollama para mayor precisión en
          tablas y figuras. Requiere Ollama.
    """

    def __init__(
        self,
        images_output_dir: str | None = None,
        glm_ocr_config: GlmOcrConfig | None = None,
        config_path: str | Path | None = None,
        mode: Literal["soft", "hard"] | None = None,
    ):
        from .document import DocumentProcessor
        from .pdf import PDFProcessor

        config = Config.load(config_path)

        # Los argumentos explícitos tienen prioridad sobre YAML/env.
        self.images_output_dir = (
            images_output_dir
            if images_output_dir is not None
            else str(config.images_output_dir)
        )

        if glm_ocr_config is not None:
            self.glm_ocr_config = glm_ocr_config
        elif mode == "hard":
            self.glm_ocr_config = GlmOcrConfig(enabled=True)
        elif mode == "soft":
            self.glm_ocr_config = GlmOcrConfig(enabled=False)
        else:
            self.glm_ocr_config = config.glm_ocr

        self.pdf_processor = PDFProcessor(
            images_output_dir=self.images_output_dir,
            glm_ocr_config=self.glm_ocr_config,
        )
        self.document_processor = DocumentProcessor()

    def extract(
        self,
        document_path: str | Path,
        output_path: str | Path | None = None,
        max_pages: int | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> ExtractionResult:
        """
        Extrae un documento y devuelve el resultado en formato Markdown.

        Args:
            document_path: Ruta al documento.
            output_path: Ruta opcional donde se guardará el Markdown. Si se
                proporciona, las referencias a imágenes se generan relativas
                a su directorio.
            max_pages: Número máximo de páginas a procesar (solo PDFs).
            progress_callback: Función opcional ``(stage, current, total)``
                que recibe actualizaciones de progreso. ``stage`` describe la
                etapa (p. ej. ``"glm_ocr_page"``).

        Returns:
            ExtractionResult con el markdown generado.
        """
        document_path = Path(document_path).resolve()

        if not document_path.exists():
            raise FileError(f"No se encontró el documento: {document_path}")

        is_pdf = document_path.suffix.lower() == ".pdf"

        if is_pdf:
            return self.pdf_processor.extract(
                document_path,
                output_path=output_path,
                max_pages=max_pages,
                progress_callback=progress_callback,
            )
        else:
            return self.document_processor.extract(document_path)

    def extract_to_file(
        self,
        document_path: str | Path,
        output_path: Optional[str | Path] = None,
        max_pages: int | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> Path:
        """
        Extrae el documento y lo guarda en un archivo Markdown.
        """
        if output_path is None:
            document_path = Path(document_path)
            output_path = document_path.with_suffix(".structured.md")

        output_path = Path(output_path)
        result = self.extract(
            document_path,
            output_path=output_path,
            max_pages=max_pages,
            progress_callback=progress_callback,
        )
        output_path.write_text(result.markdown, encoding="utf-8")
        result.output_path = output_path

        return output_path
