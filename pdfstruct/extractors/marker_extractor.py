"""
pdfstruct/extractors/marker_extractor.py

Extractor opcional para PDFs utilizando Marker (marker-pdf).
Marker usa modelos de layout OCR/ML (Surya) y suele producir tablas
multilínea mucho más limpias que extractores basados únicamente en PDF.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List


class MarkerExtractor:
    """
    Extractor basado en Marker (marker-pdf).

    Requiere el paquete opcional ``marker-pdf`` y sus dependencias
    (torch, transformers, surya-ocr, etc.). En la primera ejecución
    descarga modelos desde Hugging Face.
    """

    _PAGE_SPAN_RE = re.compile(
        r'<span\s+id="page-(?P<page>\d+)-(?P<idx>\d+)"[^>]*></span>',
        re.IGNORECASE,
    )

    def __init__(self):
        self._converter = None

    def _get_converter(self):
        """Inicializa el convertidor de Marker de forma lazy."""
        if self._converter is None:
            from marker.converters.pdf import PdfConverter
            from marker.models import create_model_dict

            self._converter = PdfConverter(artifact_dict=create_model_dict())
        return self._converter

    def extract(self, pdf_path: str | Path) -> str:
        """
        Extrae el contenido de un PDF y lo devuelve en formato Markdown.

        Args:
            pdf_path: Ruta al archivo PDF.

        Returns:
            Contenido extraído en formato Markdown con marcadores de página.
        """
        pdf_path = Path(pdf_path)

        if not pdf_path.exists():
            raise FileNotFoundError(f"No se encontró el archivo PDF: {pdf_path}")

        from marker.output import text_from_rendered

        converter = self._get_converter()
        rendered = converter(str(pdf_path))
        text, _, _ = text_from_rendered(rendered)

        return self._replace_page_spans(text)

    def extract_pages(self, pdf_path: str | Path) -> List[str]:
        """
        Extrae el contenido de un PDF página por página.

        Marker no devuelve chunks de página directamente, pero inserta
        anclas HTML ``<span id="page-N-0">`` que utilizamos como
        referencias aproximadas de página.

        Args:
            pdf_path: Ruta al archivo PDF.

        Returns:
            Lista con el Markdown de cada página, en orden.
        """
        pdf_path = Path(pdf_path)

        if not pdf_path.exists():
            raise FileNotFoundError(f"No se encontró el archivo PDF: {pdf_path}")

        from marker.output import text_from_rendered

        converter = self._get_converter()
        rendered = converter(str(pdf_path))
        text, _, _ = text_from_rendered(rendered)

        return self._split_by_page_spans(text)

    @classmethod
    def _replace_page_spans(cls, text: str) -> str:
        """Reemplaza las anclas de página de Marker por marcadores HTML."""
        pages = [int(m.group("page")) for m in cls._PAGE_SPAN_RE.finditer(text)]
        total_pages = max(pages) if pages else 1

        def repl(match):
            page_num = int(match.group("page"))
            return f"<!-- PAGE: {page_num} / {total_pages} -->"

        return cls._PAGE_SPAN_RE.sub(repl, text)

    @classmethod
    def _split_by_page_spans(cls, text: str) -> List[str]:
        """
        Divide el markdown de Marker usando las anclas de página.

        Las anclas tienen la forma ``<span id="page-N-0"></span>``.
        El contenido anterior a la primera ancla se asigna a la página 1.
        El número de página puede no ser contiguo si Marker omite páginas vacías.
        """
        if not cls._PAGE_SPAN_RE.search(text):
            # Si no hay anclas, devolvemos el texto completo como una sola página.
            return [text]

        pages: dict[int, str] = {}
        last_pos = 0
        current_page: int | None = None

        for match in cls._PAGE_SPAN_RE.finditer(text):
            page_num = int(match.group("page"))

            chunk = text[last_pos:match.start()].strip()
            if chunk:
                # El contenido previo pertenece a la página actual (o a la 1 si aún no hay).
                target_page = current_page if current_page is not None else 1
                pages[target_page] = chunk

            current_page = page_num
            last_pos = match.end()

        # Agregar el contenido después de la última ancla
        if current_page is not None:
            chunk = text[last_pos:].strip()
            if chunk:
                pages[current_page] = chunk

        if not pages:
            return [text]

        # Rellenar páginas vacías para mantener el orden y el conteo total
        max_page = max(pages.keys())
        return [pages.get(i, "") for i in range(1, max_page + 1)]
