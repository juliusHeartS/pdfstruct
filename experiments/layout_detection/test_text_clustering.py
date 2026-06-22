"""Prueba de reconstrucción de tabla por clustering de bloques de texto."""

from pathlib import Path

import fitz

PDF_PATH = Path("resultados4/pdfs/doc_03_link.1_01_9789275129708_eng.pdf")
DPI = 200

# Page 45 table bbox from YOLO (image coords)
BBOX = [174.36993408203125, 1600.79345703125, 1527.9866943359375, 1922.2081298828125]


def extract_rows(page: fitz.Page, rect: fitz.Rect, tolerance: float = 5.0) -> dict[int, list[tuple[float, str]]]:
    blocks = page.get_text("blocks", clip=rect)
    rows: dict[int, list[tuple[float, str]]] = {}
    for block in blocks:
        x0, y0, x1, y1, text, *_ = block
        if not str(text).strip():
            continue
        y = (y0 + y1) / 2
        key = None
        for k in rows:
            if abs(k - y) <= tolerance:
                key = k
                break
        if key is None:
            key = int(y)
        rows.setdefault(key, []).append((x0, text.strip()))
    return rows


def main() -> None:
    scale = 72 / DPI
    rect = fitz.Rect(BBOX[0] * scale, BBOX[1] * scale, BBOX[2] * scale, BBOX[3] * scale)

    doc = fitz.open(str(PDF_PATH))
    page = doc.load_page(45 - 1)

    print("=== Detected bbox ===")
    rows = extract_rows(page, rect)
    for y in sorted(rows):
        cells = sorted(rows[y], key=lambda t: t[0])
        print(f"Row y={y}: {[c[1] for c in cells]}")

    # Check larger region below
    larger_rect = fitz.Rect(rect.x0, rect.y0, rect.x1, rect.y1 + 100)
    print("\n=== Larger bbox (+100 pts) ===")
    rows2 = extract_rows(page, larger_rect)
    for y in sorted(rows2):
        cells = sorted(rows2[y], key=lambda t: t[0])
        print(f"Row y={y}: {[c[1] for c in cells]}")

    # Check next page for page 12 table continuation
    print("\n=== Page 13 (page 12 continued) ===")
    page13 = doc.load_page(13 - 1)
    rows3 = extract_rows(page13, fitz.Rect(0, 0, page13.rect.width, page13.rect.height))
    for y in sorted(rows3):
        cells = sorted(rows3[y], key=lambda t: t[0])
        print(f"Row y={y}: {[c[1] for c in cells]}")

    doc.close()


if __name__ == "__main__":
    main()
