"""
pdfstruct/extractors/pymupdf4llm_extractor.py

Extractor principal para PDFs utilizando PyMuPDF4LLM.
Este extractor está diseñado para generar Markdown de alta calidad
orientado a RAG y LLMs, con mejor soporte para layouts complejos,
tablas y orden de lectura.
"""

from pathlib import Path


class PyMuPDF4LLMExtractor:
    """
    Extractor basado en PyMuPDF4LLM.

    Por ahora es una versión base. Posteriormente se integrará
    la lógica real de extracción usando la librería pymupdf4llm.
    """

    def __init__(self):
        # TODO: Importar pymupdf4llm cuando se instale la dependencia
        pass

    def extract(self, pdf_path: str | Path) -> str:
        """
        Extrae el contenido de un PDF y lo devuelve en formato Markdown.

        Args:
            pdf_path: Ruta al archivo PDF.

        Returns:
            Contenido extraído en formato Markdown.
        """
        pdf_path = Path(pdf_path)

        if not pdf_path.exists():
            raise FileNotFoundError(f"No se encontró el archivo PDF: {pdf_path}")

        import pymupdf4llm
        return pymupdf4llm.to_markdown(str(pdf_path))

    def extract_pages(self, pdf_path: str | Path) -> list[str]:
        """
        Extrae el contenido de un PDF página por página.

        Args:
            pdf_path: Ruta al archivo PDF.

        Returns:
            Lista con el Markdown de cada página, en orden.
        """
        pdf_path = Path(pdf_path)

        if not pdf_path.exists():
            raise FileNotFoundError(f"No se encontró el archivo PDF: {pdf_path}")

        import pymupdf4llm
        chunks = pymupdf4llm.to_markdown(str(pdf_path), page_chunks=True)

        if isinstance(chunks, list):
            return [chunk.get("text", "") if isinstance(chunk, dict) else str(chunk) for chunk in chunks]

        # Fallback: si no devuelve chunks, devolvemos el texto completo como una sola página.
        return [pymupdf4llm.to_markdown(str(pdf_path))]
