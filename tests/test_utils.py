"""
tests/test_utils.py

Tests para funciones de utilidad.
"""

from pdfstruct.utils import clean_ocr_garbage


def test_clean_ocr_garbage_removes_ocr_missing_text_artifact():
    text = (
        "Valid paragraph.\n\n"
        "-Text content is missing. No legible. Please provide the text content from the image.\n\n"
        "Another valid paragraph."
    )
    result = clean_ocr_garbage(text)
    assert "-Text content is missing" not in result
    assert "Valid paragraph" in result
    assert "Another valid paragraph" in result


def test_clean_ocr_garbage_removes_picture_blocks():
    text = (
        "Some text\n\n"
        "----- Start of picture text -----\n"
        "garbage line\n"
        "----- End of picture text -----\n\n"
        "More text"
    )
    result = clean_ocr_garbage(text)
    assert "----- Start of picture text -----" not in result
    assert "garbage line" not in result
    assert "More text" in result
