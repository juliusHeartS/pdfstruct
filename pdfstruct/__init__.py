"""
pdfstruct

Extractor de documentos a Markdown de alta calidad.
Soporta cualquier formato compatible con MarkItDown.
En PDFs puede activar lógica avanzada (imágenes con PyMuPDF, páginas, etc.).
"""

from .core import ExtractionResult, PdfStruct, ProgressCallback

__version__ = "0.3.0"
__all__ = ["PdfStruct", "ExtractionResult", "ProgressCallback"]
