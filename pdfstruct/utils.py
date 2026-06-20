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
    name = re.sub(r'[<>:"/\\|?*]', '_', name)
    # Quita espacios al inicio y final
    name = name.strip()
    # Reemplaza múltiples espacios o guiones bajos seguidos
    name = re.sub(r'[\s_]+', '_', name)
    return name


def is_pdf_file(file_path: str | Path) -> bool:
    """
    Verifica si un archivo es PDF por su extensión.
    """
    return Path(file_path).suffix.lower() == ".pdf"


def get_safe_output_path(
    input_path: str | Path,
    suffix: str = ".structured.md",
    output_dir: str | Path | None = None
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

    # 3. Compactar <br> sueltos en saltos de línea limpios.
    text = _BR_RUIDO_RE.sub("\n", text)

    # 4. Normalizar líneas vacías múltiples.
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()