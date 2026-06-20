"""
pdfstruct/extractors/markitdown_extractor.py

Extractor basado en MarkItDown.
Se utiliza principalmente para documentos que no son PDF
y como extractor de fallback.
"""

from pathlib import Path
from markitdown import MarkItDown


class MarkItDownExtractor:
    """
    Wrapper alrededor de MarkItDown para extracción de documentos.
    """

    def __init__(self):
        self.md = MarkItDown()

    def extract(self, document_path: str | Path) -> str:
        """
        Extrae el contenido de un documento y lo devuelve como Markdown.

        Args:
            document_path: Ruta al documento.

        Returns:
            Contenido en formato Markdown.
        """
        document_path = Path(document_path)

        if not document_path.exists():
            raise FileNotFoundError(f"No se encontró el documento: {document_path}")

        result = self.md.convert(str(document_path))
        return result.text_content
