"""
pdfstruct/enrichers/text_cleaner.py

Post-procesamiento de Markdown extraído de PDFs para mejorar su calidad
antes de usarlo en RAG.

Problemas típicos que resuelve:
- Líneas sueltas que deberían ser un solo párrafo.
- Líneas con solo números de página.
- Bloques de texto duplicados consecutivos.
- Saltos de línea innecesarios dentro de párrafos.
"""

from __future__ import annotations

import re
from typing import Callable


def _looks_like_header(line: str) -> bool:
    """Detecta si una línea es un encabezado Markdown."""
    stripped = line.strip()
    return bool(re.match(r"^#{1,6}\s+", stripped)) or stripped.endswith("---")


def _looks_like_list_item(line: str) -> bool:
    """Detecta si una línea es una viñeta o ítem numerado."""
    stripped = line.strip()
    return bool(re.match(r"^(\*\s+|\-\s+|\+\s+|\d+\.\s+|\d+\)\s+)", stripped))


def _looks_like_page_number(line: str) -> bool:
    """Detecta líneas con solo números de página o números romanos sueltos."""
    stripped = line.strip()
    if not stripped:
        return False
    # Solo dígitos, opcionalmente con "de N" o "página N"
    if re.match(r"^(página\s+)?\d+\s*(de\s+\d+)?$", stripped, re.IGNORECASE):
        return True
    # Números romanos comunes sueltos
    if re.match(r"^(ix|iv|v?i{0,3})$", stripped, re.IGNORECASE) and len(stripped) <= 4:
        return True
    return False


def _looks_like_table_row(line: str) -> bool:
    """Detecta si una línea parece parte de una tabla Markdown."""
    stripped = line.strip()
    return "|" in stripped or re.match(r"^\|.*\|$", stripped) is not None


def _is_short_line(line: str, threshold: int = 50) -> bool:
    """Determina si una línea es corta en comparación con un umbral."""
    return len(line.strip()) < threshold


def _line_ends_sentence(line: str) -> bool:
    """Detecta si una línea termina en punto, signo de exclamación o interrogación."""
    stripped = line.rstrip()
    return stripped.endswith((".", "!", "?", ":", ";", '"', "'"))


def _should_merge_with_next(current: str, next_line: str) -> bool:
    """
    Decide si la línea actual debe unirse con la siguiente.

    Reglas:
    - No unir si current es header, lista, tabla o marcador de página.
    - No unir si next_line es header, lista, tabla o marcador de página.
    - No unir si current termina en signo de puntuación fuerte.
    - No unir si next_line empieza con mayúscula y current no termina en coma.
    """
    if not current.strip() or not next_line.strip():
        return False

    for check in (_looks_like_header, _looks_like_list_item, _looks_like_table_row):
        if check(current) or check(next_line):
            return False

    if _line_ends_sentence(current) and not current.rstrip().endswith(","):
        # Termina en punto, exclamación, etc. — probablemente fin de oración
        # Pero si la siguiente línea no empieza con mayúscula, podría ser continuación
        if next_line.strip()[0].isupper():
            return False

    # Si la siguiente línea empieza con minúscula, casi seguro es continuación
    if next_line.strip()[0].islower():
        return True

    # Si current no termina en puntuación y next_line empieza con mayúscula,
    # puede ser un título compuesto; unimos con cautela si current es corto.
    if _is_short_line(current, 60) and not _line_ends_sentence(current):
        return True

    return False


def merge_short_lines(markdown: str) -> str:
    """
    Une líneas sueltas en párrafos coherentes.

    Preserva encabezados, listas, tablas y bloques de código.
    """
    lines = markdown.split("\n")
    result: list[str] = []
    current_paragraph: list[str] = []

    def flush():
        if current_paragraph:
            result.append(" ".join(current_paragraph))
            current_paragraph.clear()

    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            flush()
            result.append(line)
            i += 1
            continue

        if (
            _looks_like_header(stripped)
            or _looks_like_list_item(stripped)
            or _looks_like_table_row(stripped)
        ):
            flush()
            result.append(line)
            i += 1
            continue

        if _looks_like_page_number(stripped):
            # Descartamos líneas con solo números de página
            i += 1
            continue

        # Decidir si unimos con la siguiente línea
        if i + 1 < len(lines) and _should_merge_with_next(stripped, lines[i + 1]):
            current_paragraph.append(stripped)
        else:
            current_paragraph.append(stripped)
            flush()

        i += 1

    flush()
    return "\n".join(result)


def remove_duplicate_blocks(markdown: str) -> str:
    """
    Elimina bloques de texto idénticos consecutivos.
    Útil cuando la portada o encabezados se repiten.
    """
    blocks = markdown.split("\n\n")
    cleaned: list[str] = []
    last_block: str | None = None

    for block in blocks:
        normalized = " ".join(block.split())
        if normalized and normalized == last_block:
            continue
        cleaned.append(block)
        last_block = normalized

    return "\n\n".join(cleaned)


def clean_markdown(
    markdown: str,
    cleaners: list[Callable[[str], str]] | None = None,
) -> str:
    """
    Aplica un pipeline de limpieza al Markdown.

    Args:
        markdown: Markdown a limpiar.
        cleaners: Lista de funciones de limpieza. Por defecto aplica
                  merge_short_lines y remove_duplicate_blocks.

    Returns:
        Markdown limpio.
    """
    if cleaners is None:
        cleaners = [merge_short_lines, remove_duplicate_blocks]

    result = markdown
    for cleaner in cleaners:
        result = cleaner(result)
    return result
