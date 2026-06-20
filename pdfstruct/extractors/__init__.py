"""
pdfstruct.extractors

Módulo que contiene los diferentes extractores disponibles.
"""

from .markitdown_extractor import MarkItDownExtractor
from .pymupdf4llm_extractor import PyMuPDF4LLMExtractor

__all__ = [
    "MarkItDownExtractor",
    "PyMuPDF4LLMExtractor",
]
