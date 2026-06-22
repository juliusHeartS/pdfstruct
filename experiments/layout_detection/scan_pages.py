"""Escanea un PDF y reporta páginas con detecciones de layout."""

from pathlib import Path

import fitz
from PIL import Image
from huggingface_hub import hf_hub_download
from ultralytics import YOLO

PDF_PATH = Path("resultados4/pdfs/doc_03_link.1_01_9789275129708_eng.pdf")
DPI = 200
TARGET_LABELS = {"Table", "Picture"}


def main() -> None:
    model_path = hf_hub_download(
        repo_id="DILHTWD/documentlayoutsegmentation_YOLOv8_ondoclaynet",
        filename="yolov8x-doclaynet-epoch64-imgsz640-initiallr1e-4-finallr1e-5.pt",
    )
    model = YOLO(model_path)
    doc = fitz.open(str(PDF_PATH))

    pages_with_detections = []
    for page_num in range(1, len(doc) + 1):
        page = doc.load_page(page_num - 1)
        matrix = fitz.Matrix(DPI / 72, DPI / 72)
        pixmap = page.get_pixmap(matrix=matrix)
        image = Image.frombytes("RGB", [pixmap.width, pixmap.height], pixmap.samples)

        results = model(image, imgsz=640, conf=0.25, iou=0.7, verbose=False)
        detections = []
        for result in results:
            names = result.names
            for box, conf, cls_id in zip(
                result.boxes.xyxy.cpu().numpy(),
                result.boxes.conf.cpu().numpy(),
                result.boxes.cls.cpu().numpy().astype(int),
            ):
                label = names[int(cls_id)]
                if label in TARGET_LABELS:
                    detections.append((label, float(conf)))

        if detections:
            pages_with_detections.append((page_num, detections))
            print(f"Page {page_num}: {detections}")

    doc.close()
    print(f"\nTotal pages with detections: {len(pages_with_detections)}")


if __name__ == "__main__":
    main()
