"""
pdfstruct.enrichers

Módulos para enriquecer y mejorar el Markdown después de la extracción.
"""

from .page_markers import add_page_markers
from .image_classifier import classify_image
from .cross_validator import CrossValidator

__all__ = [
    "add_page_markers",
    "classify_image",
    "CrossValidator",
]
