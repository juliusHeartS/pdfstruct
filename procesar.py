#!/usr/bin/env python3
"""
procesar.py

Script de prueba para procesar documentos con pdfstruct.
Genera un Markdown y extrae imágenes en una carpeta de resultados clara.

Uso:
    python procesar.py ruta/al/documento.pdf
    python procesar.py ruta/al/documento.pdf --output-dir mis_resultados
"""

import argparse
import sys
from pathlib import Path

from pdfstruct import PdfStruct


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Procesa un documento con pdfstruct y guarda los resultados."
    )
    parser.add_argument(
        "document", type=Path, help="Ruta al documento (PDF, DOCX, etc.)"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("resultados"),
        help="Directorio base donde guardar los resultados (default: resultados)",
    )
    parser.add_argument(
        "--images-dir",
        type=Path,
        default=None,
        help="Directorio para imágenes (default: <output-dir>/<nombre>/images)",
    )
    args = parser.parse_args()

    document_path = args.document.resolve()
    if not document_path.exists():
        print(f"Error: no se encontró el documento: {document_path}", file=sys.stderr)
        return 1

    # Carpeta de salida clara
    results_dir = args.output_dir.resolve() / document_path.stem
    results_dir.mkdir(parents=True, exist_ok=True)

    images_dir = args.images_dir
    if images_dir is None:
        images_dir = results_dir / "images"

    markdown_path = results_dir / f"{document_path.stem}.md"

    print(f"Procesando: {document_path}")
    struct = PdfStruct(images_output_dir=str(images_dir))
    result = struct.extract(document_path)

    markdown_path.write_text(result.markdown, encoding="utf-8")

    print(f"\nMarkdown guardado en: {markdown_path}")
    print(f"Total de páginas: {result.metadata.get('total_pages', 'N/A')}")
    print(f"Imágenes extraídas: {result.metadata.get('images_found', 0)}")
    if result.images_dir:
        print(f"Imágenes guardadas en: {result.images_dir}")
    print("\nResumen de metadata:")
    for key, value in result.metadata.items():
        print(f"  {key}: {value}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
