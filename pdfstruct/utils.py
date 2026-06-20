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