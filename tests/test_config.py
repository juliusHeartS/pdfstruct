"""
tests/test_config.py

Tests para la configuración de GLM-OCR via Ollama.
"""

import os
from pathlib import Path

import pytest

from pdfstruct.config import Config, GlmOcrConfig


_LEGACY_KEYS = [
    "GLM_OCR_ENABLED",
    "GLM_OCR_URL",
    "GLM_OCR_MODEL",
    "GLM_OCR_TIMEOUT",
    "GLM_OCR_IMAGES_DIR",
]

_PDFSTRUCT_KEYS = [
    "PDFSTRUCT_IMAGES_OUTPUT_DIR",
    "PDFSTRUCT_GLM_OCR_ENABLED",
    "PDFSTRUCT_GLM_OCR_URL",
    "PDFSTRUCT_GLM_OCR_MODEL",
    "PDFSTRUCT_GLM_OCR_TIMEOUT",
    "PDFSTRUCT_GLM_OCR_IMAGES_DIR",
]


@pytest.fixture
def clean_env():
    """Limpia las variables de entorno de pdfstruct antes y después del test."""
    keys = _LEGACY_KEYS + _PDFSTRUCT_KEYS
    original = {k: os.environ.get(k) for k in keys}
    for k in keys:
        os.environ.pop(k, None)
    yield
    for k in keys:
        os.environ.pop(k, None)
        if original[k] is not None:
            os.environ[k] = original[k]


def test_default_config_is_disabled(clean_env):
    cfg = GlmOcrConfig.from_settings()
    assert cfg.enabled is False
    assert cfg.url == "http://localhost:11434"
    assert cfg.model == "glm-ocr:latest"
    assert cfg.generate_url == "http://localhost:11434/api/generate"


def test_config_from_arguments(clean_env):
    cfg = GlmOcrConfig.from_settings(
        enabled=True,
        url="http://ollama.local:11434",
        model="glm-ocr:q8_0",
        timeout=120,
    )
    assert cfg.enabled is True
    assert cfg.url == "http://ollama.local:11434"
    assert cfg.model == "glm-ocr:q8_0"
    assert cfg.timeout == 120


def test_config_from_env(clean_env):
    os.environ["GLM_OCR_ENABLED"] = "true"
    os.environ["GLM_OCR_URL"] = "http://env:11434"
    os.environ["GLM_OCR_MODEL"] = "custom-model"

    cfg = GlmOcrConfig.from_settings()
    assert cfg.enabled is True
    assert cfg.url == "http://env:11434"
    assert cfg.model == "custom-model"


def test_config_from_pdfstruct_env(clean_env):
    os.environ["PDFSTRUCT_GLM_OCR_ENABLED"] = "true"
    os.environ["PDFSTRUCT_GLM_OCR_URL"] = "http://pdfstruct-env:11434"

    cfg = GlmOcrConfig.from_settings()
    assert cfg.enabled is True
    assert cfg.url == "http://pdfstruct-env:11434"


def test_pdfstruct_env_overrides_legacy_env(clean_env):
    os.environ["GLM_OCR_ENABLED"] = "false"
    os.environ["PDFSTRUCT_GLM_OCR_ENABLED"] = "true"

    cfg = GlmOcrConfig.from_settings()
    assert cfg.enabled is True


def test_generate_url_trailing_slash(clean_env):
    cfg = GlmOcrConfig(url="http://localhost:11434/")
    assert cfg.generate_url == "http://localhost:11434/api/generate"


def test_config_from_yaml(tmp_path: Path, clean_env):
    yaml_path = tmp_path / "pdfstruct.yaml"
    yaml_path.write_text(
        "images_output_dir: yaml_images\n"
        "glm_ocr:\n"
        "  enabled: true\n"
        "  url: http://yaml:11434\n"
        "  model: yaml-model\n"
        "  timeout: 300\n",
        encoding="utf-8",
    )

    config = Config.from_yaml(yaml_path)
    assert config.images_output_dir == Path("yaml_images")
    assert config.glm_ocr.enabled is True
    assert config.glm_ocr.url == "http://yaml:11434"
    assert config.glm_ocr.model == "yaml-model"
    assert config.glm_ocr.timeout == 300


def test_config_args_override_yaml(tmp_path: Path, clean_env):
    yaml_path = tmp_path / "pdfstruct.yaml"
    yaml_path.write_text(
        "glm_ocr:\n  enabled: true\n  url: http://yaml:11434\n",
        encoding="utf-8",
    )

    data = Config.from_yaml(yaml_path)
    cfg = GlmOcrConfig.from_settings(
        enabled=False,
        url="http://args:11434",
        yaml_data={"glm_ocr": data.glm_ocr.__dict__},
    )
    assert cfg.enabled is False
    assert cfg.url == "http://args:11434"


def test_config_env_overrides_yaml(tmp_path: Path, clean_env):
    yaml_path = tmp_path / "pdfstruct.yaml"
    yaml_path.write_text(
        "glm_ocr:\n  enabled: false\n  url: http://yaml:11434\n",
        encoding="utf-8",
    )
    os.environ["PDFSTRUCT_GLM_OCR_ENABLED"] = "true"

    data = Config.from_yaml(yaml_path)
    cfg = GlmOcrConfig.from_settings(yaml_data={"glm_ocr": data.glm_ocr.__dict__})
    assert cfg.enabled is True
    assert cfg.url == "http://yaml:11434"


def test_config_missing_yaml_returns_defaults(tmp_path: Path, clean_env):
    config = Config.from_yaml(tmp_path / "no_existe.yaml")
    assert config.images_output_dir == Path("pdf_images")
    assert config.glm_ocr.enabled is False
