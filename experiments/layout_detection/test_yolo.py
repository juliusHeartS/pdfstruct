"""
experiments/layout_detection/test_yolo.py

Prueba YOLOv8-doclaynet en las 10 páginas seleccionadas de doc_03.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from PIL import Image
from huggingface_hub import hf_hub_download
from ultralytics import YOLO

PAGES_DIR = Path("experiments/layout_detection/pages")
OUTPUT_DIR = Path("experiments/layout_detection/yolo")
SELECTED_PAGES = [30, 34, 35, 36, 41, 43, 44, 50, 54, 56]
TARGET_LABELS = {"Table", "Picture"}


def load_model() -> YOLO:
    model_path = hf_hub_download(
        repo_id="DILHTWD/documentlayoutsegmentation_YOLOv8_ondoclaynet",
        filename="yolov8x-doclaynet-epoch64-imgsz640-initiallr1e-4-finallr1e-5.pt",
    )
    return YOLO(model_path)


def detect_page(model: YOLO, image_path: Path) -> dict:
    image = Image.open(image_path).convert("RGB")
    start = time.time()
    results = model(image, imgsz=640, conf=0.25, iou=0.7, verbose=False)
    elapsed = time.time() - start

    detections = []
    for result in results:
        class_names = result.names
        boxes = result.boxes.xyxy.cpu().numpy()
        confs = result.boxes.conf.cpu().numpy()
        cls_ids = result.boxes.cls.cpu().numpy().astype(int)

        for box, conf, cls_id in zip(boxes, confs, cls_ids):
            label = class_names[int(cls_id)]
            detections.append(
                {
                    "label": label,
                    "confidence": float(conf),
                    "bbox": [float(c) for c in box],
                }
            )

    target_detections = [d for d in detections if d["label"] in TARGET_LABELS]

    return {
        "page": int(image_path.stem.split("_")[-1]),
        "image": str(image_path.name),
        "elapsed_seconds": round(elapsed, 3),
        "all_detections": detections,
        "target_detections": target_detections,
    }


def save_visualization(image_path: Path, detections: list[dict], output_path: Path) -> None:
    from PIL import ImageDraw

    image = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(image)
    for det in detections:
        x1, y1, x2, y2 = det["bbox"]
        draw.rectangle([x1, y1, x2, y2], outline="red", width=3)
        draw.text((x1, y1 - 10), f"{det['label']} {det['confidence']:.2f}", fill="red")
    image.save(output_path)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    model = load_model()

    all_results = []
    for page_num in SELECTED_PAGES:
        image_path = PAGES_DIR / f"doc_03_page_{page_num:03d}.png"
        result = detect_page(model, image_path)
        all_results.append(result)

        vis_path = OUTPUT_DIR / f"doc_03_page_{page_num:03d}_vis.png"
        save_visualization(image_path, result["target_detections"], vis_path)
        print(
            f"Page {page_num}: {len(result['target_detections'])} target detections "
            f"({len(result['all_detections'])} total) in {result['elapsed_seconds']}s"
        )

    summary_path = OUTPUT_DIR / "results.json"
    summary_path.write_text(json.dumps(all_results, indent=2), encoding="utf-8")
    print(f"\nResults saved to {summary_path}")


if __name__ == "__main__":
    main()
