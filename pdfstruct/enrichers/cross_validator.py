"""
pdfstruct/enrichers/cross_validator.py

Módulo para realizar validación cruzada entre diferentes extractores.
Por ahora implementa una versión ligera que reporta problemas
en lugar de modificar automáticamente el Markdown.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any


@dataclass
class ValidationResult:
    """Resultado de la validación cruzada."""

    warnings: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class CrossValidator:
    """
    Validador cruzado entre extractores.

    Actualmente realiza validaciones básicas y genera warnings.
    No modifica el Markdown de forma automática.
    """

    def __init__(self):
        pass

    def validate(
        self,
        primary_markdown: str,
        secondary_markdown: str = "",
        primary_metadata: dict = None,
        secondary_metadata: dict = None,
    ) -> ValidationResult:
        """
        Compara los resultados de dos extractores y genera warnings.

        Args:
            primary_markdown: Markdown del extractor principal (PyMuPDF4LLM).
            secondary_markdown: Markdown del extractor secundario (MarkItDown).
            primary_metadata: Metadata del extractor principal.
            secondary_metadata: Metadata del extractor secundario.

        Returns:
            ValidationResult con warnings y metadata adicional.
        """
        warnings = []
        metadata = {}

        # Validación básica: comparar longitud de texto
        if secondary_markdown:
            primary_len = len(primary_markdown)
            secondary_len = len(secondary_markdown)

            if secondary_len > primary_len * 1.3:
                warnings.append(
                    "MarkItDown extrajo significativamente más texto que PyMuPDF4LLM. "
                    "Posible omisión de contenido."
                )

            metadata["primary_text_length"] = primary_len
            metadata["secondary_text_length"] = secondary_len

        # TODO: Agregar más validaciones en el futuro:
        # - Detección de mezcla de columnas
        # - Imágenes no referenciadas
        # - Cobertura de páginas

        if warnings:
            metadata["has_warnings"] = True
        else:
            metadata["has_warnings"] = False

        return ValidationResult(warnings=warnings, metadata=metadata)
