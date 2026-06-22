"""
pdfstruct/extractors/layout_detector.py

Detector de layout basado en YOLOv8-doclaynet.

Uso opcional: solo se carga cuando se activa el modo híbrido. Requiere
instalar las dependencias ``[hybrid]`` de pdfstruct.
"""

from __future__ import annotations

import logging
from typing import Any, TYPE_CHECKING

from ..exceptions import ConfigurationError

if TYPE_CHECKING:
    from PIL import Image

logger = logging.getLogger(__name__)

DEFAULT_TARGET_LABELS = {"Table", "Picture"}
DEFAULT_MODEL_REPO = "DILHTWD/documentlayoutsegmentation_YOLOv8_ondoclaynet"
DEFAULT_MODEL_FILENAME = "yolov8x-doclaynet-epoch64-imgsz640-initiallr1e-4-finallr1e-5.pt"


class LayoutDetector:
    """
    Envoltorio alrededor de YOLOv8-doclaynet para detectar tablas y figuras.

    El modelo se descarga lazy desde Hugging Face la primera vez que se usa.
    """

    def __init__(
        self,
        model_path: str | None = None,
        target_labels: set[str] | None = None,
        conf: float = 0.25,
        iou: float = 0.7,
    ):
        self.model_path = model_path
        self.target_labels = target_labels or DEFAULT_TARGET_LABELS
        self.conf = conf
        self.iou = iou
        self._model: Any | None = None

    @property
    def model(self) -> Any:
        """Carga el modelo YOLO bajo demanda."""
        if self._model is None:
            self._model = self._load_model()
        return self._model

    def _load_model(self) -> Any:
        try:
            from huggingface_hub import hf_hub_download
            from ultralytics import YOLO
        except ImportError as exc:
            raise ConfigurationError(
                "El modo híbrido requiere dependencias extras. "
                "Instálalas con: pip install pdfstruct[hybrid]"
            ) from exc

        path = self.model_path
        if path is None:
            logger.info("Descargando modelo doclaynet desde Hugging Face...")
            path = hf_hub_download(
                repo_id=DEFAULT_MODEL_REPO,
                filename=DEFAULT_MODEL_FILENAME,
            )
        return YOLO(path)

    def detect(
        self,
        image: Image.Image,
        target_labels: set[str] | None = None,
    ) -> list[dict]:
        """
        Detecta elementos de layout en una imagen.

        Args:
            image: Imagen PIL RGB.
            target_labels: Conjunto de etiquetas a conservar. Por defecto
                ``{"Table", "Picture"}``.

        Returns:
            Lista de detecciones ordenadas verticalmente. Cada detección es un
            dict con ``label``, ``confidence`` y ``bbox`` (coordenadas de
            imagen ``[x1, y1, x2, y2]``).
        """
        labels = target_labels or self.target_labels
        results = self.model(
            image,
            imgsz=640,
            conf=self.conf,
            iou=self.iou,
            verbose=False,
        )

        detections: list[dict] = []
        for result in results:
            class_names = result.names
            boxes = result.boxes.xyxy.cpu().numpy()
            confs = result.boxes.conf.cpu().numpy()
            cls_ids = result.boxes.cls.cpu().numpy().astype(int)

            for box, conf, cls_id in zip(boxes, confs, cls_ids):
                label = class_names[int(cls_id)]
                if label not in labels:
                    continue
                detections.append(
                    {
                        "label": label,
                        "confidence": float(conf),
                        "bbox": [float(c) for c in box],
                    }
                )

        # Ordenar por centro vertical para facilitar ensamblaje posterior.
        detections.sort(key=lambda d: (d["bbox"][1] + d["bbox"][3]) / 2)
        return detections
