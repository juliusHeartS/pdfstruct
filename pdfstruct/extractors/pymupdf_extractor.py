"""
pdfstruct/extractors/pymupdf_extractor.py

Extractor especializado para PDFs usando PyMuPDF (fitz).
Este módulo se usará más adelante para:
- Extracción precisa de imágenes
- Detección de páginas
- Posible cruce de información con MarkItDown
"""

from pathlib import Path
import fitz  # PyMuPDF


class PyMuPDFExtractor:
    """
    Extractor basado en PyMuPDF para PDFs.
    Por ahora ofrece utilidades básicas. Más adelante se expandirá
    para extracción de imágenes y soporte de marcadores de página.
    """

    def __init__(self):
        pass

    def get_page_count(self, pdf_path: str | Path) -> int:
        """Devuelve el número total de páginas del PDF."""
        pdf_path = Path(pdf_path)
        doc = fitz.open(str(pdf_path))
        page_count = len(doc)
        doc.close()
        return page_count

    def extract_images_info(self, pdf_path: str | Path) -> list[dict]:
        """
        Extrae información básica de las imágenes embebidas en el PDF.
        Retorna lista de diccionarios con page e index.
        """
        pdf_path = Path(pdf_path)
        doc = fitz.open(str(pdf_path))
        images_info = []

        for page_num, page in enumerate(doc):
            image_list = page.get_images(full=True)
            for img_index, img in enumerate(image_list):
                images_info.append(
                    {
                        "page": page_num + 1,
                        "index": img_index + 1,
                        "xref": img[0],
                    }
                )

        doc.close()
        return images_info
