"""
pdfstruct/enrichers/ollama_enricher.py

Enriquece el Markdown generado por PyMuPDF4LLM usando GLM-OCR via Ollama.

La estrategia actual es enviar cada página completa como imagen a Ollama.
GLM-OCR demuestra ser muy capaz extrayendo texto nativo de PDFs cuando
ve la página completa, incluyendo tablas complejas que PyMuPDF4LLM
fragmenta. Las tablas que Ollama devuelve en HTML se convierten a
Markdown con markdownify.
"""

from __future__ import annotations

import fitz
import logging
import re
import tempfile
import os
from pathlib import Path
from typing import Any

from markdownify import markdownify as md

from ..config import GlmOcrConfig
from ..exceptions import OcrError
from ..extractors.ollama_glm_ocr_client import OllamaGlmOcrClient
from ..utils import ensure_dir

logger = logging.getLogger(__name__)


# Placeholder que PyMuPDF4LLM usa para imágenes omitidas.
_PICTURE_PLACEHOLDER_RE = re.compile(
    r"\*\*==> picture \[(\d+) x (\d+)\] intentionally omitted <==\*\*",
    re.IGNORECASE,
)


def _convert_html_tables_to_markdown(text: str) -> str:
    """
    Reemplaza bloques <table>...</table> por su equivalente Markdown.
    """

    # markdownify convierte todo el HTML, no solo tablas, pero es seguro
    # para fragmentos pequeños. Envolvemos en un div para procesar por bloques.
    def repl(match: re.Match) -> str:
        html = match.group(0)
        try:
            converted = md(html, strip=["a", "img"])
            return converted.strip()
        except Exception:
            return html

    return re.sub(
        r"<table\b[^>]*>.*?</table>", repl, text, flags=re.DOTALL | re.IGNORECASE
    )


def _extract_image_bboxes(page: fitz.Page) -> list[fitz.Rect]:
    """Devuelve los bounding boxes de las imágenes de una página."""
    bboxes: list[fitz.Rect] = []
    seen: set[tuple[float, float, float, float]] = set()

    for img in page.get_images(full=True):
        xref = img[0]
        try:
            for item in page.get_image_rects(xref):
                bbox = item if isinstance(item, fitz.Rect) else fitz.Rect(item)
                key = (bbox.x0, bbox.y0, bbox.x1, bbox.y1)
                if key not in seen:
                    seen.add(key)
                    bboxes.append(bbox)
        except Exception:
            continue

    return bboxes


def _render_region(
    page: fitz.Page,
    bbox: fitz.Rect,
    output_path: Path,
    dpi: int = 200,
) -> Path:
    """Renderiza una región de la página a una imagen PNG."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    matrix = fitz.Matrix(dpi / 72, dpi / 72)
    pixmap = page.get_pixmap(clip=bbox, matrix=matrix)
    pixmap.save(str(output_path))
    return output_path


class OllamaEnricher:
    """
    Enriquece Markdown de PyMuPDF4LLM usando GLM-OCR via Ollama.

    Por página:
      1. Renderiza la página completa.
      2. Pide a Ollama el Markdown completo.
      3. Convierte tablas HTML a Markdown.
      4. Extrae figuras con PyMuPDF, les pide leyenda a Ollama y las referencia.
    """

    def __init__(self, config: GlmOcrConfig):
        self.config = config
        self.client = OllamaGlmOcrClient(config)
        self._figure_counter = 0

    def _next_figure_name(self, prefix: str) -> str:
        self._figure_counter += 1
        return f"{prefix}_figure_{self._figure_counter:04d}.png"

    def enrich(
        self,
        pdf_path: str | Path,
        page_chunks: list[dict[str, Any]],
        images_dir: Path,
        output_dir: Path | None = None,
        filename_prefix: str = "doc",
    ) -> tuple[str, int, int]:
        """
        Enriquece los chunks de página con Ollama.

        Args:
            pdf_path: Ruta al PDF.
            page_chunks: Salida de PyMuPDF4LLM con page_chunks=True.
            images_dir: Directorio donde guardar las figuras.
            output_dir: Directorio donde se guardará el Markdown. Si se
                proporciona, las referencias a imágenes serán relativas a él.
            filename_prefix: Prefijo para nombres de archivo.

        Returns:
            (markdown_enriquecido, paginas_procesadas, figuras_procesadas)
        """
        pdf_path = Path(pdf_path)
        images_dir = ensure_dir(images_dir)
        doc = fitz.open(str(pdf_path))

        total_pages = len(page_chunks)
        processed_pages = 0
        processed_figures = 0
        enriched_parts: list[str] = []

        try:
            for chunk in page_chunks:
                page_number = chunk.get("metadata", {}).get("page_number", 1)

                if page_number < 1 or page_number > len(doc):
                    enriched_parts.append(chunk.get("text", ""))
                    continue

                page = doc.load_page(page_number - 1)
                logger.debug("Procesando página %d con GLM-OCR", page_number)

                page_text = self._ocr_page(page, page_number)
                page_text = _convert_html_tables_to_markdown(page_text)

                page_text, figure_count = self._enrich_figures(
                    page,
                    page_text,
                    images_dir,
                    filename_prefix,
                    output_dir=output_dir,
                )
                processed_figures += figure_count

                marker = f"<!-- PAGE: {page_number} / {total_pages} -->"
                if page_text.strip():
                    enriched_parts.append(f"{marker}\n\n{page_text.strip()}")
                else:
                    enriched_parts.append(marker)
                processed_pages += 1
        finally:
            doc.close()

        logger.info(
            "GLM-OCR completado: %d páginas, %d figuras",
            processed_pages,
            processed_figures,
        )
        return "\n\n".join(enriched_parts), processed_pages, processed_figures

    def _ocr_page(self, page: fitz.Page, page_number: int) -> str:
        """Envía la página completa a Ollama y devuelve el Markdown."""
        # Renderizar a una resolución razonable para OCR.
        matrix = fitz.Matrix(200 / 72, 200 / 72)
        pixmap = page.get_pixmap(matrix=matrix)

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp_path = Path(tmp.name)
        try:
            pixmap.save(str(tmp_path))
            prompt = (
                "Extrae todo el contenido de esta página de documento como Markdown. "
                "Incluye tablas (puedes usar HTML para tablas complejas si es necesario). "
                "Omite las imágenes; solo describe su lugar con un placeholder breve. "
                "No agregues comentarios ni explicaciones."
            )
            logger.debug("Enviando página %d a Ollama", page_number)
            response = self.client.generate(prompt, image_path=tmp_path)
            if not response.strip():
                raise OcrError(
                    f"GLM-OCR devolvió respuesta vacía para la página {page_number}"
                )
            return response
        except OcrError:
            raise
        except Exception as exc:
            raise OcrError(f"Error de GLM-OCR en página {page_number}: {exc}") from exc
        finally:
            tmp_path.unlink(missing_ok=True)

    def _enrich_figures(
        self,
        page: fitz.Page,
        page_text: str,
        images_dir: Path,
        filename_prefix: str,
        output_dir: Path | None = None,
    ) -> tuple[str, int]:
        """
        Extrae imágenes del PDF, les pide una leyenda a Ollama y reemplaza
        los placeholders de PyMuPDF4LLM por referencias Markdown.
        """
        image_bboxes = _extract_image_bboxes(page)
        if not image_bboxes:
            return page_text, 0

        placeholders = list(_PICTURE_PLACEHOLDER_RE.finditer(page_text))
        count = 0

        for match_index, match in enumerate(placeholders):
            if match_index >= len(image_bboxes):
                break

            try:
                bbox = image_bboxes[match_index]
                filename = self._next_figure_name(filename_prefix)
                image_path = images_dir / filename
                _render_region(page, bbox, image_path)

                caption = self.client.describe_figure(image_path)
                alt_text = caption.strip() or f"Figura {match_index + 1}"
                if output_dir is not None:
                    reference = (
                        f"![{alt_text}]({os.path.relpath(image_path, output_dir)})"
                    )
                else:
                    reference = f"![{alt_text}]({filename})"

                page_text = (
                    page_text[: match.start()] + reference + page_text[match.end() :]
                )
                count += 1
            except Exception:
                continue

        return page_text, count
