"""
pdfstruct/config.py

Configuración centralizada para pdfstruct, especialmente para la
integración opcional con GLM-OCR via Ollama.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


_DEFAULT_IMAGES_DIR = Path("pdf_images")


def _parse_bool(value: Any) -> bool:
    """Convierte un valor a bool de forma tolerante."""
    if isinstance(value, bool):
        return value
    return str(value).lower() in ("1", "true", "yes", "on")


@dataclass
class GlmOcrConfig:
    """
    Configuración para GLM-OCR via Ollama.

    Por defecto está deshabilitado. Cuando se habilita, pdfstruct usa
    Ollama para enriquecer tablas y figuras detectadas por PyMuPDF.

    Attributes:
        enabled: Activa el enriquecimiento con GLM-OCR/Ollama.
        url: Endpoint de Ollama (ej. http://localhost:11434).
        model: Nombre del modelo (ej. glm-ocr:latest).
        timeout: Timeout de la petición en segundos.
        images_dir: Directorio base donde guardar las figuras extraídas.
        table_prompt: Prompt para extraer tablas.
        figure_prompt: Prompt para describir figuras.
    """

    enabled: bool = False
    url: str = "http://localhost:11434"
    model: str = "glm-ocr:latest"
    timeout: int = 600
    images_dir: Path = Path("pdf_images")
    table_prompt: str = (
        "Extrae esta tabla como una tabla Markdown bien formada. "
        "Devuelve solo la tabla Markdown, sin explicaciones. "
        "Asegúrate de que todas las filas y columnas estén completas."
    )
    figure_prompt: str = (
        "Describe esta imagen de un documento de forma concisa. "
        "Devuelve solo una leyenda o descripción breve en una sola línea."
    )

    @property
    def generate_url(self) -> str:
        """URL completa del endpoint /api/generate de Ollama."""
        base = self.url.rstrip("/")
        return f"{base}/api/generate"

    @classmethod
    def from_settings(
        cls,
        enabled: bool | None = None,
        url: str | None = None,
        model: str | None = None,
        timeout: int | None = None,
        images_dir: str | Path | None = None,
        table_prompt: str | None = None,
        figure_prompt: str | None = None,
        yaml_data: dict[str, Any] | None = None,
    ) -> "GlmOcrConfig":
        """
        Combina argumentos, variables de entorno, archivo YAML y valores por
        defecto (de mayor a menor prioridad).

        Variables de entorno:
            PDFSTRUCT_GLM_OCR_ENABLED: "1"/"true"/"yes" para activar.
            PDFSTRUCT_GLM_OCR_URL
            PDFSTRUCT_GLM_OCR_MODEL
            PDFSTRUCT_GLM_OCR_TIMEOUT
            PDFSTRUCT_GLM_OCR_IMAGES_DIR

        También se aceptan las variables legacy GLM_OCR_*.
        """
        yaml_data = yaml_data or {}

        settings: dict[str, Any] = {
            "enabled": cls.enabled,
            "url": cls.url,
            "model": cls.model,
            "timeout": cls.timeout,
            "images_dir": cls.images_dir,
            "table_prompt": cls.table_prompt,
            "figure_prompt": cls.figure_prompt,
        }

        # Aplicar YAML (sección glm_ocr).
        if "glm_ocr" in yaml_data:
            settings.update(yaml_data["glm_ocr"])

        # Aplicar variables de entorno (prefijo PDFSTRUCT_ o legacy GLM_OCR_).
        env_enabled = os.getenv("PDFSTRUCT_GLM_OCR_ENABLED") or os.getenv(
            "GLM_OCR_ENABLED"
        )
        if env_enabled is not None:
            settings["enabled"] = _parse_bool(env_enabled)

        env_url = os.getenv("PDFSTRUCT_GLM_OCR_URL") or os.getenv("GLM_OCR_URL")
        if env_url is not None:
            settings["url"] = env_url

        env_model = os.getenv("PDFSTRUCT_GLM_OCR_MODEL") or os.getenv("GLM_OCR_MODEL")
        if env_model is not None:
            settings["model"] = env_model

        env_timeout = os.getenv("PDFSTRUCT_GLM_OCR_TIMEOUT") or os.getenv(
            "GLM_OCR_TIMEOUT"
        )
        if env_timeout is not None:
            settings["timeout"] = int(env_timeout)

        env_images_dir = os.getenv("PDFSTRUCT_GLM_OCR_IMAGES_DIR") or os.getenv(
            "GLM_OCR_IMAGES_DIR"
        )
        if env_images_dir is not None:
            settings["images_dir"] = Path(env_images_dir)

        # Aplicar argumentos explícitos (mayor prioridad).
        if enabled is not None:
            settings["enabled"] = enabled
        if url is not None:
            settings["url"] = url
        if model is not None:
            settings["model"] = model
        if timeout is not None:
            settings["timeout"] = timeout
        if images_dir is not None:
            settings["images_dir"] = Path(images_dir)
        if table_prompt is not None:
            settings["table_prompt"] = table_prompt
        if figure_prompt is not None:
            settings["figure_prompt"] = figure_prompt

        return cls(**settings)


@dataclass
class Config:
    """
    Configuración global de pdfstruct.

    Attributes:
        images_output_dir: Directorio base para guardar imágenes extraídas.
        glm_ocr: Configuración de GLM-OCR via Ollama.
    """

    images_output_dir: Path = _DEFAULT_IMAGES_DIR
    glm_ocr: GlmOcrConfig = field(default_factory=GlmOcrConfig)

    @classmethod
    def from_yaml(cls, path: str | Path) -> "Config":
        """Carga configuración desde un archivo YAML."""
        path = Path(path)
        if not path.exists():
            return cls()

        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}

        glm_ocr = GlmOcrConfig.from_settings(yaml_data=data)

        images_output_dir = data.get("images_output_dir", _DEFAULT_IMAGES_DIR)
        env_images_dir = os.getenv("PDFSTRUCT_IMAGES_OUTPUT_DIR")
        if env_images_dir is not None:
            images_output_dir = env_images_dir

        return cls(
            images_output_dir=Path(images_output_dir),
            glm_ocr=glm_ocr,
        )

    @classmethod
    def load(cls, path: str | Path | None = None) -> "Config":
        """
        Carga configuración desde un archivo YAML.

        Si no se indica ruta, busca ``pdfstruct.yaml`` en el directorio de
        trabajo actual.
        """
        if path is None:
            path = Path.cwd() / "pdfstruct.yaml"
        return cls.from_yaml(path)
