"""
pdfstruct/utils.py

Funciones de utilidad generales para el proyecto.
"""

from pathlib import Path
import re


def ensure_dir(path: str | Path) -> Path:
    """
    Asegura que un directorio exista. Si no existe, lo crea.
    Retorna el Path del directorio.
    """
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def sanitize_filename(name: str) -> str:
    """
    Limpia un nombre de archivo para que sea seguro en la mayoría de sistemas.
    """
    # Reemplaza caracteres problemáticos
    name = re.sub(r'[<>:"/\\|?*]', "_", name)
    # Quita espacios al inicio y final
    name = name.strip()
    # Reemplaza múltiples espacios o guiones bajos seguidos
    name = re.sub(r"[\s_]+", "_", name)
    return name


def is_pdf_file(file_path: str | Path) -> bool:
    """
    Verifica si un archivo es PDF por su extensión.
    """
    return Path(file_path).suffix.lower() == ".pdf"


def get_safe_output_path(
    input_path: str | Path,
    suffix: str = ".structured.md",
    output_dir: str | Path | None = None,
) -> Path:
    """
    Genera una ruta de salida segura para el archivo Markdown.
    """
    input_path = Path(input_path)

    if output_dir:
        output_dir = ensure_dir(output_dir)
        base_name = sanitize_filename(input_path.stem)
        return output_dir / f"{base_name}{suffix}"
    else:
        return input_path.with_suffix(suffix)


# ---------------------------------------------------------------------------
# Limpieza de artefactos de OCR / PyMuPDF4LLM
# ---------------------------------------------------------------------------

# Bloques de texto de imagen generados por OCR ruidoso.
_PICTURE_BLOCK_RE = re.compile(
    r"----- Start of picture text -----.*?----- End of picture text -----",
    re.DOTALL | re.IGNORECASE,
)

# Marcadores de imagen omitida intencionalmente.
_OMITTED_PICTURE_RE = re.compile(
    r"\*\*==> picture \[\d+ x \d+\] intentionally omitted <==\*\*",
    re.IGNORECASE,
)

# Artefactos de modelos OCR multimodales cuando no leen una región.
_OCR_MISSING_TEXT_RE = re.compile(
    r"-Text content is missing\. No legible\. Please provide the text content from the image\.?",
    re.IGNORECASE,
)

# Saltos forzados de PyMuPDF4LLM que dejan basura.
_BR_RUIDO_RE = re.compile(r"<br>\s*")


def clean_ocr_garbage(markdown: str) -> str:
    """
    Limpia artefactos comunes generados por PyMuPDF4LLM + OCR:

    - Bloques ``----- Start of picture text ----- ... ----- End of picture text -----``.
    - Marcadores ``==> picture [W x H] intentionally omitted <==``.
    - Ruido residual de saltos de línea ``<br>`` sueltos.

    Args:
        markdown: Markdown crudo devuelto por el extractor.

    Returns:
        Markdown limpio.
    """
    # 1. Quitar bloques de texto de imagen (incluyendo líneas con <br> internas).
    text = _PICTURE_BLOCK_RE.sub("", markdown)

    # 2. Quitar marcadores de imagen omitida.
    text = _OMITTED_PICTURE_RE.sub("", text)

    # 3. Quitar artefactos de OCR multimodal.
    text = _OCR_MISSING_TEXT_RE.sub("", text)

    # 4. Conservar <br> dentro de celdas de tabla Markdown, pero compactar
    #    <br> sueltos que no están dentro de una fila de tabla.
    lines = text.splitlines()
    preserved: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("|"):
            preserved.append(line)
        else:
            preserved.append(_BR_RUIDO_RE.sub("\n", line))
    text = "\n".join(preserved)

    # 4. Normalizar líneas vacías múltiples.
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


# ---------------------------------------------------------------------------
# Normalización de texto: reemplazos de carácter y espacios
# ---------------------------------------------------------------------------

# Caracteres de control C0 excepto tab, newline y carriage return.
_CONTROL_CHARS = set(chr(o) for o in range(0x20) if o not in (9, 10, 13))
# Espacios y separadores invisibles de Unicode que suelen confundir a los extractores.
_WEIRD_SPACES = {
    "\u00a0",
    "\u2000",
    "\u2001",
    "\u2002",
    "\u2003",
    "\u2004",
    "\u2005",
    "\u2006",
    "\u2007",
    "\u2008",
    "\u2009",
    "\u200a",
    "\u200b",
    "\u200c",
    "\u200d",
    "\u200e",
    "\u200f",
    "\u2028",
    "\u2029",
    "\u202f",
    "\u205f",
    "\u2060",
    "\ufeff",
}
_REPLACEMENT_CHAR = "\ufffd"


def normalize_text(text: str) -> str:
    """
    Normaliza texto extraído de PDFs:

    - Reemplaza caracteres de control por espacios.
    - Reemplaza espacios "raros" de Unicode por espacio normal.
    - Reemplaza ``\ufffd`` (carácter de reemplazo) por espacio.
    - Compacta espacios múltiples.
    - Normaliza espacios alrededor de puntuación simple (``,``, ``.``, ``;``, ``:``, ``?``, ``!``).

    Args:
        text: Texto a normalizar.

    Returns:
        Texto normalizado.
    """
    chars = []
    for c in text:
        if c in _CONTROL_CHARS or c in _WEIRD_SPACES or c == _REPLACEMENT_CHAR:
            chars.append(" ")
        else:
            chars.append(c)
    result = "".join(chars)

    # Compactar espacios múltiples.
    result = re.sub(r" +", " ", result)
    # Normalizar espacio antes de signos de puntuación occidentales.
    result = re.sub(r"\s+([.,;:?!)])", r"\1", result)
    # Normalizar espacio después de signo de apertura.
    result = re.sub(r"([(])\s+", r"\1", result)
    # Compactar líneas vacías múltiples.
    result = re.sub(r"\n{3,}", "\n\n", result)

    return result.strip()
