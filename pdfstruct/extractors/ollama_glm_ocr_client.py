"""
pdfstruct/extractors/ollama_glm_ocr_client.py

Cliente ligero para GLM-OCR via Ollama usando requests.
Solo requiere que Ollama esté corriendo localmente con el modelo
"glm-ocr" disponible.
"""

from __future__ import annotations

import base64
import logging
import requests
from pathlib import Path

from ..config import GlmOcrConfig
from ..exceptions import OcrError

logger = logging.getLogger(__name__)


class OllamaGlmOcrClient:
    """
    Cliente directo al endpoint /api/generate de Ollama.

    No depende del SDK glmocr; solo usa ``requests`` para enviar imágenes
    y recibir texto Markdown o descripciones.
    """

    def __init__(self, config: GlmOcrConfig | None = None):
        self.config = config or GlmOcrConfig()

    def _encode_image(self, image_path: str | Path) -> str:
        """Codifica una imagen en base64 para el payload de Ollama."""
        image_path = Path(image_path)
        return base64.b64encode(image_path.read_bytes()).decode("utf-8")

    def generate(
        self,
        prompt: str,
        image_path: str | Path | None = None,
        options: dict | None = None,
    ) -> str:
        """
        Envía un prompt opcionalmente acompañado de una imagen a Ollama.

        Args:
            prompt: Instrucción para el modelo.
            image_path: Ruta a una imagen (PNG/JPG). Si es None, se envía
                solo texto.
            options: Opciones adicionales para Ollama (ej. {"num_predict": 4096}).

        Returns:
            Texto generado por el modelo.
        """
        payload: dict = {
            "model": self.config.model,
            "prompt": prompt,
            "stream": False,
        }

        if options:
            payload["options"] = options

        if image_path is not None:
            payload["images"] = [self._encode_image(image_path)]

        logger.debug(
            "POST %s con modelo %s", self.config.generate_url, self.config.model
        )
        try:
            response = requests.post(
                self.config.generate_url,
                json=payload,
                timeout=self.config.timeout,
            )
            response.raise_for_status()
        except requests.RequestException as exc:
            raise OcrError(
                f"No se pudo conectar con Ollama en {self.config.generate_url}: {exc}"
            ) from exc

        data = response.json()
        return data.get("response", "").strip()

    def extract_table(self, image_path: str | Path) -> str:
        """
        Pide a Ollama que extraiga una tabla Markdown desde una imagen.
        """
        return self.generate(self.config.table_prompt, image_path=image_path)

    def describe_figure(self, image_path: str | Path) -> str:
        """
        Pide a Ollama que genere una leyenda para una figura.
        """
        return self.generate(self.config.figure_prompt, image_path=image_path)

    def is_available(self) -> bool:
        """
        Verifica rápidamente si Ollama responde en la URL configurada.
        """
        url = self.config.url.rstrip("/") + "/api/tags"
        try:
            response = requests.get(url, timeout=5)
            available = response.status_code == 200
            logger.debug("Ollama disponible en %s: %s", url, available)
            return available
        except Exception as exc:
            logger.debug("Ollama no disponible en %s: %s", url, exc)
            return False
