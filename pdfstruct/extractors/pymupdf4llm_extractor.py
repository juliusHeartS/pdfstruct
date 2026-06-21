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

    def _extract_page_chunks(self, pdf_path: str | Path) -> list[dict]:
        """
        Extrae el PDF con page_chunks=True y devuelve los chunks crudos.

        Args:
            pdf_path: Ruta al archivo PDF.

        Returns:
            Lista de diccionarios con 'text' y 'metadata' por página.
        """
        pdf_path = Path(pdf_path)

        if not pdf_path.exists():
            raise FileNotFoundError(f"No se encontró el archivo PDF: {pdf_path}")

        import pymupdf4llm

        chunks = pymupdf4llm.to_markdown(str(pdf_path), page_chunks=True)

        if isinstance(chunks, list):
            return [
                chunk
                if isinstance(chunk, dict)
                else {"text": str(chunk), "metadata": {}}
                for chunk in chunks
            ]

        # Fallback: si no devuelve chunks, devolvemos el texto completo como una sola página.
        return [
            {"text": pymupdf4llm.to_markdown(str(pdf_path)), "metadata": {"page": 1}}
        ]

    def extract_pages(self, pdf_path: str | Path) -> list[str]:
        """
        Extrae el contenido de un PDF página por página.

        Args:
            pdf_path: Ruta al archivo PDF.

        Returns:
            Lista con el Markdown de cada página, en orden.
        """
        chunks = self._extract_page_chunks(pdf_path)
        return [chunk.get("text", "") for chunk in chunks]
