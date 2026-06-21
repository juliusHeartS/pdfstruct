"""
pdfstruct/exceptions.py

Excepciones específicas del proyecto pdfstruct.
"""


class PdfStructError(Exception):
    """Excepción base para todos los errores de pdfstruct."""


class ConfigurationError(PdfStructError):
    """Error en la configuración de pdfstruct."""


class ExtractionError(PdfStructError):
    """Error durante la extracción de un documento."""


class FileError(ExtractionError):
    """Error relacionado con archivos de entrada/salida."""


class OcrError(ExtractionError):
    """Error durante el procesamiento OCR (GLM-OCR / Ollama)."""
