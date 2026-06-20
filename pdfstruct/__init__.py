"""
pdfstruct

Extractor de documentos a Markdown de alta calidad.
Soporta cualquier formato compatible con MarkItDown.
En PDFs puede activar lógica avanzada (imágenes con PyMuPDF, páginas, etc.).
"""

from .core import PdfStruct

__version__ = "0.1.0"
__all__ = ["PdfStruct"]