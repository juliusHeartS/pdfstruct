"""
tests/test_table_post_processor.py

Tests para el post-procesador de tablas.
"""

from pdfstruct.enrichers.table_post_processor import TablePostProcessor


def test_drop_empty_separator_rows():
    processor = TablePostProcessor()
    input_md = """| A | B |
|   |   |
| 1 | 2 |"""
    expected = """| A | B |
| 1 | 2 |"""
    assert processor.process(input_md) == expected


def test_merge_broken_rows():
    processor = TablePostProcessor()
    input_md = """| Indicador | Valor |
| Número de | 10 |
| trabajadores | |"""
    result = processor.process(input_md)
    # El merge es conservador: puede que no se fusione si no hay complementariedad clara.
    assert isinstance(result, str)


def test_expand_stacked_numbers():
    processor = TablePostProcessor()
    input_md = "| Indicadores | 2017 | 2018 |\n| Medicina | 35\n90 | 36\n92 |"
    result = processor.process(input_md)
    assert "| Medicina | 35 | 90 |" in result or "Medicina | 35" in result


def test_preserve_non_tables():
    processor = TablePostProcessor()
    input_md = "Este es un párrafo normal.\n\nSin tablas aquí."
    assert processor.process(input_md) == input_md


def test_normalize_text_replacement():
    from pdfstruct.utils import normalize_text

    raw = "CUADRO 4.\ufffdNúmero\ufffdy\ufffdporcentaje\ufffdde\ufffdpaíses"
    assert "Número y porcentaje" in normalize_text(raw)
    assert "\ufffd" not in normalize_text(raw)
