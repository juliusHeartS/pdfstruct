"""
pdfstruct/enrichers/image_classifier.py

Módulo para clasificar imágenes entre decorativas y con datos.
Versión inicial basada en reglas simples (tamaño, posición y contenido).
"""

from pathlib import Path
from typing import Dict, Any


def classify_image(
    image_path: str | Path,
    page_number: int = 0,
    image_index: int = 0,
    image_size: int = 0,
    image_width: int = 0,
    image_height: int = 0
) -> Dict[str, Any]:
    """
    Clasifica una imagen como 'decorative' o 'data_rich'.

    Criterios iniciales (pueden mejorarse después):
    - Imágenes pequeñas o en encabezado/pie suelen ser decorativas.
    - Imágenes grandes o con mucho contenido visual suelen tener datos.

    Returns:
        Diccionario con la clasificación y razones.
    """
    image_path = Path(image_path)
    classification = "unknown"
    reasons = []

    # Regla simple por tamaño
    if image_size > 0 and image_size < 15000:  # menos de ~15KB
        classification = "decorative"
        reasons.append("Tamaño pequeño")

    # Regla por dimensiones (imágenes muy anchas o altas suelen ser decorativas)
    if image_width > 0 and image_height > 0:
        if image_width > 1200 or image_height > 800:
            if classification != "decorative":
                classification = "data_rich"
                reasons.append("Tamaño grande (posible gráfico o tabla)")

    # Regla por posición aproximada (encabezado o pie de página)
    if page_number == 1 and image_index <= 2:
        if classification != "data_rich":
            classification = "decorative"
            reasons.append("Posible logo o encabezado")

    if not reasons:
        reasons.append("Clasificación por defecto")

    if classification == "unknown":
        classification = "data_rich"  # Por defecto asumimos que puede tener valor

    return {
        "classification": classification,
        "reasons": reasons,
        "filename": image_path.name,
        "page": page_number,
    }
