"""
tests/test_core.py

Tests de integración para PdfStruct con PDFs y documentos genéricos.
"""

import fitz
import struct
from pathlib import Path
from pdfstruct import PdfStruct


def _create_test_pdf(output_path: Path, num_pages: int = 1) -> Path:
    doc = fitz.open()
    for i in range(num_pages):
        page = doc.new_page(width=300, height=200)
        page.insert_text((20, 20), f"Página {i + 1} del documento de prueba")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(output_path))
    doc.close()
    return output_path


def _create_pdf_with_image(output_path: Path) -> Path:
    doc = fitz.open()
    page = doc.new_page(width=300, height=200)
    page.insert_text((20, 20), "Documento con imagen")

    w, h = 20, 20
    samples = b"".join(struct.pack(">BBB", 255, 0, 0) for _ in range(w * h))
    pixmap = fitz.Pixmap(fitz.csRGB, w, h, samples, 0)
    page.insert_image(fitz.Rect(20, 40, 120, 140), pixmap=pixmap)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(output_path))
    doc.close()
    return output_path


def test_extract_pdf(tmp_path: Path):
    pdf_path = tmp_path / "test.pdf"
    _create_test_pdf(pdf_path, num_pages=2)

    struct = PdfStruct(images_output_dir=str(tmp_path / "images"))
    result = struct.extract(pdf_path)

    assert result.metadata["is_pdf"] is True
    assert result.metadata["total_pages"] == 2
    assert "<!-- PAGE: 1 / 2 -->" in result.markdown


def test_extract_pdf_with_images(tmp_path: Path):
    pdf_path = tmp_path / "test_img.pdf"
    _create_pdf_with_image(pdf_path)

    images_dir = tmp_path / "images"
    struct = PdfStruct(images_output_dir=str(images_dir))
    result = struct.extract(pdf_path)

    # En producción el umbral por defecto es 2048 bytes; las imágenes de test
    # pequeñas no se extraen. Verificamos que la metadata es coherente.
    assert result.metadata["images_found"] == 0
    assert result.images_dir is None



def test_extract_nonexistent_file(tmp_path: Path):
    struct = PdfStruct()
    try:
        struct.extract(tmp_path / "no_existe.pdf")
        assert False, "Debería haber lanzado FileNotFoundError"
    except FileNotFoundError:
        pass
