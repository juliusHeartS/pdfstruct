"""
experiments/layout_detection/test_layoutlmv3.py

Prueba LayoutLMv3 (base o large) fine-tuned en DocLayNet en las 10 páginas
seleccionadas de doc_03.

Uso:
    python test_layoutlmv3.py yonashailug/layoutlmv3-large-doclaynet layoutlmv3_large
    python test_layoutlmv3.py Kwan0/layoutlmv3-base-finetune-DocLayNet-100k layoutlmv3_base
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import torch
from PIL import Image
from transformers import AutoModelForTokenClassification, AutoProcessor

PAGES_DIR = Path("experiments/layout_detection/pages")
OUTPUT_ROOT = Path("experiments/layout_detection")
SELECTED_PAGES = [30, 34, 35, 36, 41, 43, 44, 50, 54, 56]
TARGET_LABELS = {"Table", "Picture"}


def _iou(box_a: list[int], box_b: list[int]) -> float:
    x_left = max(box_a[0], box_b[0])
    y_top = max(box_a[1], box_b[1])
    x_right = min(box_a[2], box_b[2])
    y_bottom = min(box_a[3], box_b[3])

    if x_right < x_left or y_bottom < y_top:
        return 0.0

    intersection = (x_right - x_left) * (y_bottom - y_top)
    area_a = (box_a[2] - box_a[0]) * (box_a[3] - box_a[1])
    area_b = (box_b[2] - box_b[0]) * (box_b[3] - box_b[1])
    return intersection / (area_a + area_b - intersection)


def _proximity(box_a: list[int], box_b: list[int]) -> bool:
    """True si dos cajas están muy cercanas o se solapan."""
    # Expandir ligeramente para capturar cajas adyacentes.
    margin = 25
    a = [box_a[0] - margin, box_a[1] - margin, box_a[2] + margin, box_a[3] + margin]
    x_left = max(a[0], box_b[0])
    y_top = max(a[1], box_b[1])
    x_right = min(a[2], box_b[2])
    y_bottom = min(a[3], box_b[3])
    return x_right >= x_left and y_bottom >= y_top


def _merge_boxes_by_label(regions: list[dict]) -> list[dict]:
    """Agrupa cajas del mismo label que se solapan o están muy cercanas."""
    merged: list[dict] = []
    iou_threshold = 0.01

    for r in sorted(regions, key=lambda x: (x["label"], x["box"][1], x["box"][0])):
        merged_into_existing = False
        for m in merged:
            if m["label"] != r["label"]:
                continue
            if _iou(m["box"], r["box"]) > iou_threshold or _proximity(m["box"], r["box"]):
                b = m["box"]
                r_box = r["box"]
                b[0] = min(b[0], r_box[0])
                b[1] = min(b[1], r_box[1])
                b[2] = max(b[2], r_box[2])
                b[3] = max(b[3], r_box[3])
                m["confidence"] = max(m["confidence"], r["confidence"])
                merged_into_existing = True
                break

        if not merged_into_existing:
            merged.append(
                {
                    "label": r["label"],
                    "confidence": r["confidence"],
                    "box": r["box"][:],
                }
            )

    # Filtrar regiones muy pequeñas (probablemente tokens sueltos mal clasificados).
    filtered = []
    for m in merged:
        width = m["box"][2] - m["box"][0]
        height = m["box"][3] - m["box"][1]
        if width > 80 and height > 40:
            filtered.append(m)

    return filtered


def load_model(model_id: str):
    processor = AutoProcessor.from_pretrained(model_id, apply_ocr=True)
    model = AutoModelForTokenClassification.from_pretrained(model_id)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model.to(device)
    model.eval()
    return processor, model, device


def detect_page(processor, model, device, image_path: Path) -> dict:
    image = Image.open(image_path).convert("RGB")
    img_w, img_h = image.size

    encoding = processor(image, return_tensors="pt", truncation=True)
    encoding = {
        k: v.to(device) for k, v in encoding.items() if isinstance(v, torch.Tensor)
    }

    start = time.time()
    with torch.no_grad():
        outputs = model(**encoding)
    elapsed = time.time() - start

    logits = outputs.logits.squeeze(0).cpu()
    probs = logits.softmax(-1).max(-1).values
    preds = logits.argmax(-1)

    bboxes = encoding["bbox"].squeeze(0).cpu()
    attention = encoding["attention_mask"].squeeze(0).cpu()
    id2label = model.config.id2label

    regions = []
    for i, mask in enumerate(attention):
        if mask == 0:
            continue

        x0, y0, x1, y1 = bboxes[i].tolist()
        if [x0, y0, x1, y1] == [0, 0, 0, 0]:
            continue

        label = id2label[int(preds[i])]
        confidence = float(probs[i])
        if label not in TARGET_LABELS or confidence < 0.5:
            continue

        regions.append(
            {
                "label": label,
                "confidence": confidence,
                "box": [
                    int(x0 * img_w / 1000),
                    int(y0 * img_h / 1000),
                    int(x1 * img_w / 1000),
                    int(y1 * img_h / 1000),
                ],
            }
        )

    # Merge token-level boxes into coherent regions.
    merged = _merge_boxes_by_label(regions)

    return {
        "page": int(image_path.stem.split("_")[-1]),
        "image": str(image_path.name),
        "elapsed_seconds": round(elapsed, 3),
        "target_detections": merged,
    }


def save_visualization(image_path: Path, detections: list[dict], output_path: Path) -> None:
    from PIL import ImageDraw

    image = Image.open(image_path).convert("RGB")
    draw = ImageDraw.Draw(image)
    for det in detections:
        x1, y1, x2, y2 = det["box"]
        draw.rectangle([x1, y1, x2, y2], outline="blue", width=3)
        draw.text((x1, y1 - 10), f"{det['label']} {det['confidence']:.2f}", fill="blue")
    image.save(output_path)


def main() -> None:
    if len(sys.argv) != 3:
        print("Usage: python test_layoutlmv3.py <model_id> <output_subdir>")
        sys.exit(1)

    model_id = sys.argv[1]
    output_subdir = sys.argv[2]
    output_dir = OUTPUT_ROOT / output_subdir
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Loading {model_id}...")
    processor, model, device = load_model(model_id)
    print(f"Model loaded on {device}")

    all_results = []
    for page_num in SELECTED_PAGES:
        image_path = PAGES_DIR / f"doc_03_page_{page_num:03d}.png"
        result = detect_page(processor, model, device, image_path)
        all_results.append(result)

        vis_path = output_dir / f"doc_03_page_{page_num:03d}_vis.png"
        save_visualization(image_path, result["target_detections"], vis_path)
        print(
            f"Page {page_num}: {len(result['target_detections'])} target detections "
            f"in {result['elapsed_seconds']}s"
        )

    summary_path = output_dir / "results.json"
    summary_path.write_text(json.dumps(all_results, indent=2), encoding="utf-8")
    print(f"\nResults saved to {summary_path}")


if __name__ == "__main__":
    main()
