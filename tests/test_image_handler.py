"""
tests/test_image_handler.py

Tests básicos para image_handler con PDFs generados dinámicamente.
"""

import fitz
from pathlib import Path
from pdfstruct.enrichers.image_handler import (
    extract_and_save_images,
    create_image_references,
)


def _create_test_pdf(output_path: Path) -> Path:
    """Crea un PDF de prueba con una página de texto y una imagen embebida."""
    doc = fitz.open()
    page = doc.new_page(width=300, height=200)

    # Texto de prueba
    page.insert_text((20, 20), "Hola PDF de prueba")

    # Imagen embebida simple (rectángulo rojo 20x20) para superar el filtro de 100 bytes
    import struct

    width, height = 20, 20
    samples = b"".join(struct.pack(">BBB", 255, 0, 0) for _ in range(width * height))
    pixmap = fitz.Pixmap(fitz.csRGB, width, height, samples, 0)
    page.insert_image(fitz.Rect(20, 40, 120, 140), pixmap=pixmap)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(output_path))
    doc.close()
    return output_path


def test_extract_images(tmp_path: Path):
    pdf_path = tmp_path / "test.pdf"
    _create_test_pdf(pdf_path)

    output_dir = tmp_path / "images"
    images_info = extract_and_save_images(pdf_path, output_dir, min_bytes=100)

    assert len(images_info) >= 1
    for img in images_info:
        assert img["path"].exists()
        assert "page" in img
        assert "hash" in img


def test_create_image_references(tmp_path: Path):
    pdf_path = tmp_path / "test.pdf"
    _create_test_pdf(pdf_path)

    output_dir = tmp_path / "images"
    images_info = extract_and_save_images(pdf_path, output_dir, min_bytes=100)
    section = create_image_references(images_info, output_dir)

    assert "## Imágenes extraídas" in section
    assert "Página 1" in section
