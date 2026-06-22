"""Prueba rápida de extracción de tablas con PyMuPDF en regiones detectadas por YOLO."""

from pathlib import Path

import fitz
from PIL import Image
from huggingface_hub import hf_hub_download
from ultralytics import YOLO

PDF_PATH = Path("resultados4/pdfs/doc_03_link.1_01_9789275129708_eng.pdf")
DPI = 200
PAGES = [5, 8, 12, 33, 34, 45, 74, 80]
TARGET_LABELS = {"Table"}


def main() -> None:
    model_path = hf_hub_download(
        repo_id="DILHTWD/documentlayoutsegmentation_YOLOv8_ondoclaynet",
        filename="yolov8x-doclaynet-epoch64-imgsz640-initiallr1e-4-finallr1e-5.pt",
    )
    model = YOLO(model_path)
    doc = fitz.open(str(PDF_PATH))

    for page_num in PAGES:
        page = doc.load_page(page_num - 1)
        matrix = fitz.Matrix(DPI / 72, DPI / 72)
        pixmap = page.get_pixmap(matrix=matrix)
        image = Image.frombytes("RGB", [pixmap.width, pixmap.height], pixmap.samples)

        results = model(image, imgsz=640, conf=0.25, iou=0.7, verbose=False)
        for result in results:
            names = result.names
            for box, conf, cls_id in zip(
                result.boxes.xyxy.cpu().numpy(),
                result.boxes.conf.cpu().numpy(),
                result.boxes.cls.cpu().numpy().astype(int),
            ):
                label = names[int(cls_id)]
                if label not in TARGET_LABELS:
                    continue
                scale = 72 / DPI
                rect = fitz.Rect(
                    box[0] * scale, box[1] * scale, box[2] * scale, box[3] * scale
                )
                tabs = page.find_tables(clip=rect)
                print(f"\nPage {page_num} Table conf={conf:.2f} rect={rect}")
                print(f"  find_tables found: {len(tabs.tables)}")
                if tabs.tables:
                    tab = tabs[0]
                    data = tab.extract()
                    print(f"  rows={len(data)} cols={len(data[0]) if data else 0}")
                    for i, row in enumerate(data[:8]):
                        print(f"    {i}: {row}")
                    if len(data) > 8:
                        print(f"    ... ({len(data) - 8} more rows)")

    doc.close()


if __name__ == "__main__":
    main()
