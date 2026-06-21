"""
tests/test_ollama_glm_ocr_client.py

Tests para el cliente directo de Ollama GLM-OCR.
"""

from pathlib import Path
from unittest.mock import Mock, patch


from pdfstruct.config import GlmOcrConfig
from pdfstruct.extractors.ollama_glm_ocr_client import OllamaGlmOcrClient


def test_extract_table_sends_image_and_prompt(tmp_path: Path):
    image_path = tmp_path / "table.png"
    image_path.write_bytes(b"fake-image")

    config = GlmOcrConfig(enabled=True)
    client = OllamaGlmOcrClient(config=config)

    mock_response = Mock()
    mock_response.json.return_value = {"response": "| A | B |\n|---|---|\n| 1 | 2 |"}
    mock_response.raise_for_status = Mock()

    with patch("requests.post", return_value=mock_response) as mock_post:
        result = client.extract_table(image_path)

    assert result == "| A | B |\n|---|---|\n| 1 | 2 |"
    mock_post.assert_called_once()
    call_args = mock_post.call_args
    assert call_args.kwargs["json"]["model"] == "glm-ocr:latest"
    assert call_args.kwargs["json"]["prompt"] == config.table_prompt
    # La imagen se envía codificada en base64.
    import base64

    decoded = base64.b64decode(call_args.kwargs["json"]["images"][0])
    assert decoded == b"fake-image"


def test_describe_figure_sends_image_and_prompt(tmp_path: Path):
    image_path = tmp_path / "figure.png"
    image_path.write_bytes(b"fake-image")

    config = GlmOcrConfig(enabled=True)
    client = OllamaGlmOcrClient(config=config)

    mock_response = Mock()
    mock_response.json.return_value = {"response": "Gráfico de ventas anuales"}
    mock_response.raise_for_status = Mock()

    with patch("requests.post", return_value=mock_response):
        result = client.describe_figure(image_path)

    assert result == "Gráfico de ventas anuales"


def test_is_available_true():
    config = GlmOcrConfig()
    client = OllamaGlmOcrClient(config=config)

    mock_response = Mock()
    mock_response.status_code = 200

    with patch("requests.get", return_value=mock_response):
        assert client.is_available() is True


def test_is_available_false():
    config = GlmOcrConfig()
    client = OllamaGlmOcrClient(config=config)

    with patch("requests.get", side_effect=Exception("connection refused")):
        assert client.is_available() is False
