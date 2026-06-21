"""
experiments/layout_detection/render_pages.py

Renderiza las 10 páginas seleccionadas de doc_03 a imágenes PNG.
"""

from pathlib import Path

import fitz

PDF_PATH = Path("resultados4/pdfs/doc_03_link.1_01_9789275129708_eng.pdf")
OUTPUT_DIR = Path("experiments/layout_detection/pages")
SELECTED_PAGES = [30, 34, 35, 36, 41, 43, 44, 50, 54, 56]
DPI = 200


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    doc = fitz.open(str(PDF_PATH))

    for page_num in SELECTED_PAGES:
        page = doc.load_page(page_num - 1)  # 0-indexed
        matrix = fitz.Matrix(DPI / 72, DPI / 72)
        pixmap = page.get_pixmap(matrix=matrix)
        output_path = OUTPUT_DIR / f"doc_03_page_{page_num:03d}.png"
        pixmap.save(str(output_path))
        print(f"Rendered page {page_num} -> {output_path}")

    doc.close()
    print(f"\nAll {len(SELECTED_PAGES)} pages rendered to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
