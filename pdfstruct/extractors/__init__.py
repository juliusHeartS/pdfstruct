"""
pdfstruct.extractors

Módulo que contiene los diferentes extractores disponibles.
"""

from .markitdown_extractor import MarkItDownExtractor
from .pymupdf4llm_extractor import PyMuPDF4LLMExtractor
from .ollama_glm_ocr_client import OllamaGlmOcrClient

__all__ = [
    "MarkItDownExtractor",
    "PyMuPDF4LLMExtractor",
    "OllamaGlmOcrClient",
]
