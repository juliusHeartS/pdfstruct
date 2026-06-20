"""
pdfstruct/enrichers/page_markers.py

Módulo para agregar marcadores de página al Markdown.
"""

from pathlib import Path
import fitz


def _count_pdf_pages(total_pages_source: int | Path) -> int:
    """
    Resuelve la cantidad de páginas desde un entero o una ruta PDF.
    """
    if isinstance(total_pages_source, int):
        return total_pages_source
    pdf_path = Path(total_pages_source)
    if not pdf_path.exists():
        return 0
    with fitz.open(str(pdf_path)) as doc:
        return len(doc)


def add_page_markers(markdown: str, total_pages_source: int | Path = 0) -> str:
    """
    Agrega un marcador de página al inicio del Markdown.

    Args:
        markdown: Contenido Markdown original.
        total_pages_source: Número total de páginas del documento o ruta al PDF.

    Returns:
        Markdown con el marcador de página agregado.
    """
    total_pages = _count_pdf_pages(total_pages_source)

    if total_pages > 0:
        header = f"<!-- PAGE: 1 / {total_pages} -->\n\n"
    else:
        header = "<!-- PAGE: 1 -->\n\n"

    return header + markdown


def get_page_marker(page_number: int, total_pages: int = 0) -> str:
    """
    Genera un marcador de página individual.
    """
    if total_pages > 0:
        return f"<!-- PAGE: {page_number} / {total_pages} -->"
    return f"<!-- PAGE: {page_number} -->"
