"""
pdfstruct/enrichers/image_handler.py

Módulo para manejar la extracción y referencia de imágenes en PDFs.
"""

from pathlib import Path
import hashlib
import fitz  # PyMuPDF


def _image_hash(image_bytes: bytes) -> str:
    """Devuelve un hash corto para detectar imágenes duplicadas."""
    return hashlib.sha256(image_bytes).hexdigest()[:16]


def extract_and_save_images(
    pdf_path: str | Path,
    output_dir: Path,
    min_bytes: int = 2048,
    doc: fitz.Document | None = None,
) -> list[dict]:
    """
    Extrae todas las imágenes de un PDF y las guarda en output_dir.

    Args:
        pdf_path: Ruta al PDF (usada para naming si doc no está abierto).
        output_dir: Directorio de salida.
        min_bytes: Tamaño mínimo en bytes para guardar una imagen.
                   Por defecto 2048 para evitar iconos en producción.
        doc: Documento PyMuPDF ya abierto. Si se proporciona, no se cierra.

    Returns:
        Lista de información de cada imagen guardada.
    """
    pdf_path = Path(pdf_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    opened_here = False
    if doc is None:
        doc = fitz.open(str(pdf_path))
        opened_here = True

    images_info: list[dict] = []
    seen_hashes: set[str] = set()

    try:
        for page_num, page in enumerate(doc):
            image_list = page.get_images(full=True)

            for img_index, img in enumerate(image_list):
                xref = img[0]

                try:
                    base_image = doc.extract_image(xref)
                except Exception:
                    continue

                image_bytes = base_image["image"]
                image_ext = base_image["ext"]

                if len(image_bytes) < min_bytes:
                    continue

                img_hash = _image_hash(image_bytes)
                if img_hash in seen_hashes:
                    continue
                seen_hashes.add(img_hash)

                filename = (
                    f"page_{page_num + 1:03d}_img_{img_index + 1:02d}.{image_ext}"
                )
                image_path = output_dir / filename

                with open(image_path, "wb") as f:
                    f.write(image_bytes)

                images_info.append(
                    {
                        "page": page_num + 1,
                        "index": img_index + 1,
                        "path": image_path,
                        "filename": filename,
                        "hash": img_hash,
                        "bytes": len(image_bytes),
                    }
                )
    finally:
        if opened_here:
            doc.close()

    return images_info


def create_image_references(
    images_info: list[dict],
    images_dir: Path,
    relative_to: Path | None = None,
) -> str:
    """
    Crea una sección de referencias de imágenes para agregar al Markdown.
    """
    if not images_info:
        return ""

    if relative_to is None:
        relative_to = images_dir.parent

    sorted_images = sorted(images_info, key=lambda x: (x["page"], x["index"]))

    section = "\n\n---\n\n## Imágenes extraídas\n\n"

    for img in sorted_images:
        rel_path = Path(img["path"]).relative_to(relative_to)
        section += f"![{img['filename']}]({rel_path})\n"
        section += f"*Página {img['page']} - Imagen {img['index']}*\n\n"

    return section


def images_for_page(images_info: list[dict], page: int) -> list[dict]:
    """Devuelve las imágenes asociadas a una página específica."""
    return [img for img in images_info if img["page"] == page]
