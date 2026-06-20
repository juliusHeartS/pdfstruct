"""
pdfstruct/enrichers/page_markers.py

Módulo para agregar marcadores de página al Markdown.
Usamos el formato <!-- PAGE: X --> porque es limpio,
no afecta el renderizado y es fácil de parsear después.
"""

from pathlib import Path
import fitz  # PyMuPDF
import re


def _get_page_texts(doc: fitz.Document) -> list[str]:
    """Extrae el texto de cada página del PDF ya abierto."""
    return [(page.get_text("text") or "") for page in doc]


def _normalize(text: str) -> str:
    """Normaliza texto para comparación robusta."""
    return " ".join(text.split()).lower()


def _find_page_for_block(block: str, page_texts: list[str], last_page: int) -> int:
    """
    Heurística para determinar la página más probable de un bloque Markdown.
    Busca coincidencias de texto en las páginas a partir de last_page.
    """
    if not block.strip():
        return last_page

    norm_block = _normalize(block)
    if not norm_block:
        return last_page

    sample = norm_block[:150]
    best_page = last_page
    best_score = -1.0

    for page_idx in range(last_page, len(page_texts)):
        norm_page = _normalize(page_texts[page_idx])
        if not norm_page:
            continue

        if sample in norm_page:
            return page_idx + 1

        block_words = set(norm_block.split())
        page_words = set(norm_page.split())
        if not block_words:
            continue
        score = len(block_words & page_words) / len(block_words)
        if score > best_score:
            best_score = score
            best_page = page_idx + 1

    if best_score < 0.1:
        return last_page

    return best_page


def add_page_markers(markdown: str, doc: fitz.Document | str | Path) -> str:
    """
    Inserta marcadores de página (<!-- PAGE: X -->) en el Markdown.

    Args:
        markdown: Markdown generado por el extractor.
        doc: Documento PyMuPDF ya abierto, o ruta a un PDF.

    Returns:
        Markdown enriquecido con marcadores de página.
    """
    pdf_path: Path | None = None
    opened_here = False

    if isinstance(doc, (str, Path)):
        pdf_path = Path(doc)
        if not pdf_path.exists():
            raise FileNotFoundError(f"No se encontró el PDF: {pdf_path}")
        doc = fitz.open(str(pdf_path))
        opened_here = True

    try:
        page_texts = _get_page_texts(doc)
    except Exception:
        if opened_here:
            doc.close()
        return markdown

    if not page_texts:
        if opened_here:
            doc.close()
        return markdown

    blocks = markdown.split("\n\n")
    result_blocks: list[str] = []
    current_page = 1

    for block in blocks:
        if not block.strip():
            result_blocks.append(block)
            continue

        detected_page = _find_page_for_block(block, page_texts, current_page - 1)

        if detected_page > current_page:
            result_blocks.append(f"<!-- PAGE: {detected_page} -->")
            current_page = detected_page

        result_blocks.append(block)

    if result_blocks and not result_blocks[0].strip().startswith("<!-- PAGE:"):
        result_blocks.insert(0, "<!-- PAGE: 1 -->")

    if opened_here:
        doc.close()

    # Limpia marcadores duplicados consecutivos
    cleaned: list[str] = []
    last_marker: str | None = None
    marker_re = re.compile(r"^<!-- PAGE:\s*\d+\s*-->$")
    for blk in result_blocks:
        if marker_re.match(blk.strip()):
            if blk.strip() != last_marker:
                cleaned.append(blk)
                last_marker = blk.strip()
        else:
            cleaned.append(blk)
            last_marker = None

    return "\n\n".join(cleaned)
