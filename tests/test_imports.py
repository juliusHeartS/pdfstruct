"""
tests/test_imports.py

Verifica que todos los módulos se importan correctamente y
que las clases principales existen.
"""


def test_import_core():
    from pdfstruct.core import PdfStruct, ExtractionResult
    assert PdfStruct is not None
    assert ExtractionResult is not None


def test_import_pdf_processor():
    from pdfstruct.pdf import PDFProcessor
    assert PDFProcessor is not None


def test_import_document_processor():
    from pdfstruct.document import DocumentProcessor
    assert DocumentProcessor is not None


def test_import_extractors():
    from pdfstruct.extractors.markitdown_extractor import MarkItDownExtractor
    from pdfstruct.extractors.pymupdf_extractor import PyMuPDFExtractor
    assert MarkItDownExtractor is not None
    assert PyMuPDFExtractor is not None


def test_import_enrichers():
    from pdfstruct.enrichers.page_markers import add_page_markers
    from pdfstruct.enrichers.image_handler import (
        extract_and_save_images,
        create_image_references,
        images_for_page,
    )
    assert add_page_markers is not None
    assert extract_and_save_images is not None
    assert create_image_references is not None
    assert images_for_page is not None


def test_import_cli():
    from pdfstruct.cli import app
    assert app is not None
