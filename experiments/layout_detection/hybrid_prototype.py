"""
experiments/layout_detection/hybrid_prototype.py

Prototipo de modo híbrido para pdfstruct:
1. Renderiza cada página a imagen.
2. Detecta tablas/figuras con YOLOv8-doclaynet.
3. Extrae bloques de texto con PyMuPDF con coordenadas.
4. Para tablas: intenta PyMuPDF find_tables; si no basta, usa GLM-OCR con
   información previa de PyMuPDF y división horizontal inteligente.
5. Para figuras: envía el recorte a GLM-OCR.
6. Combina bloques de texto + detecciones ordenados verticalmente.
7. Si GLM-OCR falla, usa el texto base correspondiente.

Uso:
    python hybrid_prototype.py
"""

from __future__ import annotations

import difflib
import json
import re
import tempfile
import time
from pathlib import Path

import fitz
from PIL import Image
from huggingface_hub import hf_hub_download
from markdownify import markdownify as md
from ultralytics import YOLO

from pdfstruct.config import GlmOcrConfig
from pdfstruct.extractors.ollama_glm_ocr_client import OllamaGlmOcrClient

PDF_PATH = Path("resultados4/pdfs/doc_03_link.1_01_9789275129708_eng.pdf")
OUTPUT_DIR = Path("experiments/layout_detection/hybrid_output")
PAGES_TO_PROCESS = [5, 8, 12, 31, 33, 34, 41, 45, 74, 80]
DPI = 200
TARGET_LABELS = {"Table", "Picture"}

# Umbrales para decidir estrategia de tabla
TABLE_SPLIT_HEIGHT_RATIO = 0.75  # si la tabla supera este % de la página, dividir
DENSE_SPLIT_MIN_LINES = 50       # o si tiene muchas líneas de texto en poca altura
MAX_CHUNK_HEIGHT_RATIO = 0.45    # cada chunk no supera este % de la página
HEADER_RATIO = 0.12              # fracción superior de la tabla considerada encabezado
OVERLAP_RATIO = 0.08             # solapamiento entre chunks


def load_yolo_model() -> YOLO:
    model_path = hf_hub_download(
        repo_id="DILHTWD/documentlayoutsegmentation_YOLOv8_ondoclaynet",
        filename="yolov8x-doclaynet-epoch64-imgsz640-initiallr1e-4-finallr1e-5.pt",
    )
    return YOLO(model_path)


def load_ollama_client() -> OllamaGlmOcrClient:
    return OllamaGlmOcrClient(GlmOcrConfig(enabled=True))


def render_page(doc: fitz.Document, page_num: int, dpi: int = DPI) -> Image.Image:
    page = doc.load_page(page_num - 1)
    matrix = fitz.Matrix(dpi / 72, dpi / 72)
    pixmap = page.get_pixmap(matrix=matrix)
    return Image.frombytes("RGB", [pixmap.width, pixmap.height], pixmap.samples)


def detect_elements(model: YOLO, image: Image.Image) -> list[dict]:
    results = model(image, imgsz=640, conf=0.25, iou=0.7, verbose=False)
    detections = []
    for result in results:
        class_names = result.names
        boxes = result.boxes.xyxy.cpu().numpy()
        confs = result.boxes.conf.cpu().numpy()
        cls_ids = result.boxes.cls.cpu().numpy().astype(int)

        for box, conf, cls_id in zip(boxes, confs, cls_ids):
            label = class_names[int(cls_id)]
            if label not in TARGET_LABELS:
                continue
            detections.append(
                {
                    "label": label,
                    "confidence": float(conf),
                    "bbox": [float(c) for c in box],
                }
            )

    detections.sort(key=lambda d: (d["bbox"][1] + d["bbox"][3]) / 2)
    return detections


def image_bbox_to_pdf_rect(bbox: list[float], dpi: int = DPI) -> fitz.Rect:
    scale = 72 / dpi
    return fitz.Rect(bbox[0] * scale, bbox[1] * scale, bbox[2] * scale, bbox[3] * scale)


def deduplicate_sentences(text: str) -> str:
    """Elimina oraciones repetidas que GLM-OCR suele generar."""
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    seen = set()
    unique = []
    for sentence in sentences:
        normalized = " ".join(sentence.lower().split())
        if normalized and normalized not in seen:
            seen.add(normalized)
            unique.append(sentence)
    return " ".join(unique)


def first_sentence(text: str) -> str:
    """Devuelve solo la primera oración."""
    match = re.match(r"[^.!?]*[.!?]", text.strip())
    return match.group(0).strip() if match else text.strip()


def deduplicate_paragraphs(text: str) -> str:
    """Elimina párrafos completos repetidos."""
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text.strip()) if p.strip()]
    seen = set()
    unique = []
    for paragraph in paragraphs:
        normalized = re.sub(r"\s+", " ", paragraph.lower())
        if normalized not in seen:
            seen.add(normalized)
            unique.append(paragraph)
    return "\n\n".join(unique)


def get_text_blocks(doc: fitz.Document, page_num: int) -> list[dict]:
    page = doc.load_page(page_num - 1)
    blocks = page.get_text("blocks")
    result = []
    for block in blocks:
        x0, y0, x1, y1, text, block_no, block_type = block
        text = text.strip()
        if not text:
            continue
        result.append(
            {
                "type": "text",
                "text": text,
                "rect": fitz.Rect(x0, y0, x1, y1),
                "y": (y0 + y1) / 2,
            }
        )
    return result


def filter_overlapping_text_blocks(
    text_blocks: list[dict], detections: list[dict]
) -> list[dict]:
    """Elimina bloques de texto que están dentro de detecciones de YOLO."""
    detection_rects = [image_bbox_to_pdf_rect(d["bbox"]) for d in detections]

    def inside_detection(rect: fitz.Rect, det_rect: fitz.Rect) -> bool:
        center = fitz.Point((rect.x0 + rect.x1) / 2, (rect.y0 + rect.y1) / 2)
        if det_rect.contains(center):
            return True
        inter = rect & det_rect
        if inter.is_empty:
            return False
        return inter.get_area() / rect.get_area() > 0.5

    return [
        block
        for block in text_blocks
        if not any(inside_detection(block["rect"], det_rect) for det_rect in detection_rects)
    ]


# ---------------------------------------------------------------------------
# Extracción de tablas
# ---------------------------------------------------------------------------


def extract_table_with_pymupdf(page: fitz.Page, pdf_rect: fitz.Rect) -> dict | None:
    """Intenta extraer la estructura de una tabla con PyMuPDF find_tables."""
    try:
        tabs = page.find_tables(clip=pdf_rect)
    except Exception:
        return None

    if not tabs.tables:
        return None

    tab = tabs[0]
    try:
        data = tab.extract()
    except Exception:
        return None

    if not data or len(data) < 2:
        return None

    col_counts = [len(row) for row in data]
    consistent = max(col_counts) == min(col_counts)
    empty_cells = sum(1 for row in data for cell in row if cell is None or str(cell).strip() == "")
    total_cells = sum(col_counts)
    empty_ratio = empty_cells / total_cells if total_cells else 1.0

    quality = "good" if (consistent and empty_ratio < 0.25) else "partial"

    return {
        "data": data,
        "rows": len(data),
        "cols": col_counts[0],
        "consistent": consistent,
        "empty_ratio": empty_ratio,
        "quality": quality,
        "header": getattr(tab, "header", False),
    }


def table_data_to_markdown(data: list[list[str | None]], header: bool = True) -> str:
    """Convierte una matriz de celdas a Markdown."""
    lines = []
    for i, row in enumerate(data):
        cells = [str(cell).replace("\n", " ") if cell is not None else "" for cell in row]
        lines.append("| " + " | ".join(cells) + " |")
        if i == 0 and header:
            lines.append("|" + "|".join(["---"] * len(row)) + "|")
    return "\n".join(lines)


def get_raw_text_in_region(page: fitz.Page, pdf_rect: fitz.Rect) -> str:
    """Extrae texto plano de una región como contexto previo."""
    return page.get_text("text", clip=pdf_rect).strip()


def count_text_blocks_in_region(page: fitz.Page, pdf_rect: fitz.Rect) -> int:
    """Cuenta bloques de texto dentro de una región para estimar filas."""
    blocks = page.get_text("blocks", clip=pdf_rect)
    return sum(1 for b in blocks if str(b[4]).strip())


def split_table_image(
    image: Image.Image,
    bbox: list[float],
    max_chunk_height_ratio: float = MAX_CHUNK_HEIGHT_RATIO,
    header_ratio: float = HEADER_RATIO,
    overlap_ratio: float = OVERLAP_RATIO,
) -> list[Image.Image]:
    """Divide una imagen de tabla en franjas horizontales, repitiendo el encabezado."""
    x1, y1, x2, y2 = [int(c) for c in bbox]
    table_width = x2 - x1
    table_height = y2 - y1
    max_chunk_height = int(image.height * max_chunk_height_ratio)

    header_height = max(int(table_height * header_ratio), 30)
    header_crop = image.crop((x1, y1, x2, y1 + header_height))

    data_top = y1 + header_height
    data_bottom = y2
    data_height = data_bottom - data_top

    max_data_height = max_chunk_height - header_height
    if data_height <= max_data_height or max_data_height <= 0:
        return [image.crop((x1, y1, x2, y2))]

    overlap = max(int(data_height * overlap_ratio), 20)
    chunks: list[Image.Image] = []
    current = data_top
    while current < data_bottom:
        bottom = min(current + max_data_height, data_bottom)
        data_crop = image.crop((x1, current, x2, bottom))
        combined = Image.new("RGB", (table_width, header_height + data_crop.height))
        combined.paste(header_crop, (0, 0))
        combined.paste(data_crop, (0, header_height))
        chunks.append(combined)
        current += max_data_height - overlap
        if bottom == data_bottom:
            break

    return chunks if chunks else [image.crop((x1, y1, x2, y2))]


def parse_markdown_table(text: str) -> list[list[str]]:
    """Parsea una tabla Markdown a lista de filas."""
    rows = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        if re.match(r"^\|[-:\|\s]+\|$", stripped):
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        rows.append(cells)
    return rows


def rows_are_similar(a: list[str], b: list[str]) -> bool:
    """Compara dos filas de tabla con tolerancia a pequeñas diferencias."""
    if len(a) != len(b):
        return False
    matches = 0
    total = 0
    for ca, cb in zip(a, b):
        if ca.strip() or cb.strip():
            total += 1
            sa, sb = ca.strip().lower(), cb.strip().lower()
            # Coincidencia exacta, una contiene a la otra, o ratio alto
            if sa == sb or sa in sb or sb in sa:
                matches += 1
            elif difflib.SequenceMatcher(None, sa, sb).ratio() >= 0.65:
                matches += 1
    if total == 0:
        return True
    return matches / total >= 0.65


def _row_key(row: list[str]) -> str:
    return " | ".join(c.strip().lower() for c in row)


def _find_overlap(merged_rows: list[list[str]], new_rows: list[list[str]]) -> int:
    """Encuentra el solapamiento entre el final de merged_rows y el inicio de new_rows."""
    max_overlap = min(len(merged_rows), len(new_rows))
    for k in range(max_overlap, 0, -1):
        if all(
            rows_are_similar(merged_rows[-k + i], new_rows[i]) for i in range(k)
        ):
            return k
    return 0


def _row_completeness(row: list[str]) -> int:
    return sum(len(c) for c in row)


def merge_table_chunks(chunks_text: list[str]) -> str:
    """Une tablas de chunks descartando filas duplicadas en solapamientos."""
    parsed_chunks = [parse_markdown_table(t) for t in chunks_text]
    parsed_chunks = [c for c in parsed_chunks if c]
    if not parsed_chunks:
        return "\n\n".join(chunks_text).strip()

    merged: list[list[str]] = []
    for idx, rows in enumerate(parsed_chunks):
        if not merged:
            merged.extend(rows)
            continue
        # Cada chunk incluye el encabezado; lo descartamos del segundo en adelante.
        data_rows = rows[1:] if idx > 0 else rows
        for row in data_rows:
            # Si la fila es similar a una existente, conserva la más completa.
            replaced = False
            for eidx, existing in enumerate(merged):
                if rows_are_similar(row, existing):
                    if _row_completeness(row) > _row_completeness(existing):
                        merged[eidx] = row
                    replaced = True
                    break
            if not replaced:
                merged.append(row)

    return table_data_to_markdown(merged, header=True)


def clean_table_response(response: str) -> str:
    """Limpia salida de GLM-OCR dejando solo la tabla."""
    # Quitar bloques de código markdown
    response = re.sub(r"^```(?:markdown)?\s*", "", response.strip())
    response = re.sub(r"\s*```$", "", response.strip())

    response = deduplicate_sentences(response)
    if response.startswith("<"):
        response = md(response, strip=["a", "img"]).strip()

    lines = response.splitlines()
    table_lines = []
    in_table = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("|") or stripped.startswith("|-"):
            in_table = True
            table_lines.append(line)
        elif in_table:
            break
    return "\n".join(table_lines).strip() if table_lines else response.strip()


def clean_figure_response(response: str) -> str:
    """Limpia salida de GLM-OCR dejando una descripción concisa y la primera tabla/lista."""
    response = re.sub(r"```(?:markdown)?", "", response)
    response = re.sub(r"[】\]\[\ufeff]+", "", response)
    response = deduplicate_sentences(response)
    response = deduplicate_paragraphs(response)

    # Extraer primera oración
    first = first_sentence(response)

    # Extraer primera tabla Markdown
    lines = response.splitlines()
    table_lines = []
    in_table = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("|") or stripped.startswith("|-"):
            in_table = True
            table_lines.append(line)
        elif in_table:
            break

    if table_lines:
        return f"{first}\n\n" + "\n".join(table_lines).strip()

    # Si no hay tabla, devolver primer párrafo no vacío
    for paragraph in response.split("\n\n"):
        if paragraph.strip():
            return paragraph.strip()
    return response.strip()


def _call_glm_ocr(
    client: OllamaGlmOcrClient,
    image: Image.Image,
    prompt: str,
    num_predict: int | None = 4096,
) -> str | None:
    """Envía una imagen a GLM-OCR y devuelve la respuesta limpia."""
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    try:
        image.save(tmp_path)
        options = {"num_predict": num_predict} if num_predict else None
        response = client.generate(prompt, image_path=tmp_path, options=options)
        return response.strip() if response else None
    except Exception as exc:
        print(f"    GLM-OCR error: {exc}")
        return None
    finally:
        tmp_path.unlink(missing_ok=True)


def enrich_table(
    client: OllamaGlmOcrClient,
    image: Image.Image,
    element: dict,
    page: fitz.Page,
) -> str | None:
    """Extrae una tabla usando PyMuPDF + GLM-OCR con contexto previo."""
    pdf_rect = image_bbox_to_pdf_rect(element["bbox"])
    raw_text = get_raw_text_in_region(page, pdf_rect)

    # 1. Intento rápido con PyMuPDF
    pymupdf_table = extract_table_with_pymupdf(page, pdf_rect)
    if pymupdf_table and pymupdf_table["quality"] == "good":
        print(f"    PyMuPDF extracted {pymupdf_table['rows']}x{pymupdf_table['cols']} table")
        return table_data_to_markdown(pymupdf_table["data"], header=pymupdf_table["header"])

    # 2. Información previa para GLM-OCR (concisa)
    prior_parts = []
    if pymupdf_table:
        prior_parts.append(
            f"Estructura aproximada detectada: {pymupdf_table['rows']} filas, "
            f"{pymupdf_table['cols']} columnas."
        )
    else:
        approx_rows = max(2, count_text_blocks_in_region(page, pdf_rect))
        prior_parts.append(f"Filas aproximadas a extraer: {approx_rows}.")

    prior_info = " ".join(prior_parts)

    # 3. Decidir si dividir
    x1, y1, x2, y2 = element["bbox"]
    table_height = y2 - y1
    page_height = image.height
    table_ratio = table_height / page_height

    # Tabla densa: muchas líneas de texto en poca altura
    raw_lines = [ln for ln in raw_text.splitlines() if ln.strip()]
    is_dense = len(raw_lines) > DENSE_SPLIT_MIN_LINES and table_ratio < TABLE_SPLIT_HEIGHT_RATIO

    needs_split = table_ratio > TABLE_SPLIT_HEIGHT_RATIO or is_dense

    base_prompt = (
        "Extrae el contenido exacto de esta tabla. "
        "Si es compleja (celdas combinadas), usa HTML; si es simple, usa Markdown. "
        "Extrae TODAS las filas visibles, no omitas ninguna. "
        "Devuelve SOLO la tabla, sin texto explicativo, sin leyendas y sin repetir. "
        f"{prior_info}"
    )

    if not needs_split:
        crop = image.crop((int(x1), int(y1), int(x2), int(y2)))
        prompt = base_prompt
        response = _call_glm_ocr(client, crop, prompt)
        if response:
            return clean_table_response(response)
        return None

    # 4. Dividir en chunks horizontales
    reason = "densa" if is_dense else "alta"
    print(f"    Table is {reason} ({table_ratio:.1%} of page, {len(raw_lines)} text lines); splitting into chunks")
    chunks = split_table_image(image, element["bbox"])
    chunk_results = []
    for i, chunk in enumerate(chunks):
        prompt = (
            base_prompt
            + f" Esta imagen es el fragmento {i + 1} de {len(chunks)}. "
            "Las primeras filas son el encabezado; inclúyelo."
        )
        response = _call_glm_ocr(client, chunk, prompt)
        if response:
            chunk_results.append(clean_table_response(response))

    if not chunk_results:
        return None

    if len(chunk_results) == 1:
        return chunk_results[0]

    return merge_table_chunks(chunk_results)


def enrich_picture(
    client: OllamaGlmOcrClient,
    image: Image.Image,
    element: dict,
) -> str | None:
    """Extrae una descripción de figura con GLM-OCR."""
    x1, y1, x2, y2 = [int(c) for c in element["bbox"]]
    crop = image.crop((x1, y1, x2, y2))

    prompt = (
        "You are analyzing a statistical chart from a technical document. "
        "Return ONLY two things:\n"
        "1) One sentence identifying the chart type and the main finding.\n"
        "2) A Markdown table with the visible numerical data. Use columns that make sense for the chart (e.g., Country, Value).\n\n"
        "Do not include explanations, summaries, or repeated sections. "
        "Do not hallucinate values not visible in the image."
    )
    response = _call_glm_ocr(client, crop, prompt, num_predict=2048)
    if not response:
        return None

    return clean_figure_response(response)


def enrich_element(
    client: OllamaGlmOcrClient,
    image: Image.Image,
    element: dict,
    page: fitz.Page,
) -> str | None:
    if element["label"] == "Table":
        return enrich_table(client, image, element, page)
    return enrich_picture(client, image, element)


# ---------------------------------------------------------------------------
# Ensamblaje final de la página
# ---------------------------------------------------------------------------


def build_page_markdown(
    text_blocks: list[dict],
    detections: list[dict],
    enriched: dict[tuple[int, str], str | None],
) -> str:
    """Combina bloques de texto y detecciones en orden vertical."""
    elements: list[dict] = []

    for block in text_blocks:
        elements.append({"type": "text", "y": block["y"], "content": block["text"]})

    for idx, det in enumerate(detections):
        det_rect = image_bbox_to_pdf_rect(det["bbox"])
        y = (det_rect.y0 + det_rect.y1) / 2
        content = enriched.get((idx, det["label"]))
        if content is None:
            content = f"[_{det['label']} no pudo ser enriquecido; ver imagen original_)]"
        elements.append({"type": det["label"], "y": y, "content": content})

    elements.sort(key=lambda e: e["y"])

    parts = []
    for elem in elements:
        content = elem["content"].strip()
        if not content:
            continue
        if elem["type"] == "Picture":
            parts.append(f"\n\n**[Figura]** {content}\n\n")
        elif elem["type"] == "Table":
            parts.append(f"\n\n{content}\n\n")
        else:
            parts.append(f"\n\n{content}\n\n")

    return "".join(parts).strip()


def process_page(
    doc: fitz.Document,
    page_num: int,
    yolo_model: YOLO,
    ollama_client: OllamaGlmOcrClient,
) -> dict:
    print(f"\nProcessing page {page_num}...")

    image = render_page(doc, page_num)
    detections = detect_elements(yolo_model, image)
    print(f"  YOLO detections: {len(detections)}")

    text_blocks = get_text_blocks(doc, page_num)
    print(f"  Text blocks before filtering: {len(text_blocks)}")
    text_blocks = filter_overlapping_text_blocks(text_blocks, detections)
    print(f"  Text blocks after filtering: {len(text_blocks)}")

    page = doc.load_page(page_num - 1)
    enriched: dict[tuple[int, str], str | None] = {}
    for idx, element in enumerate(detections):
        print(
            f"  - {element['label']} conf={element['confidence']:.2f} "
            f"bbox={element['bbox']}"
        )
        result = enrich_element(ollama_client, image, element, page)
        enriched[(idx, element["label"])] = result
        if result:
            print(f"    Result: {result[:120].replace(chr(10), ' ')}...")
        else:
            print("    Enrichment failed, will keep base text")

    final_text = build_page_markdown(text_blocks, detections, enriched)

    return {
        "page": page_num,
        "text_blocks": len(text_blocks),
        "detections": detections,
        "enriched": {f"{k[0]}_{k[1]}": v for k, v in enriched.items()},
        "final_text": final_text,
    }


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("Loading YOLO model...")
    yolo_model = load_yolo_model()

    print("Loading Ollama client...")
    ollama_client = load_ollama_client()
    if not ollama_client.is_available():
        print("ERROR: Ollama not available")
        return

    doc = fitz.open(str(PDF_PATH))
    all_pages = []

    start = time.time()
    for page_num in PAGES_TO_PROCESS:
        page_result = process_page(doc, page_num, yolo_model, ollama_client)
        all_pages.append(page_result)

        output_path = OUTPUT_DIR / f"page_{page_num:03d}.md"
        output_path.write_text(page_result["final_text"], encoding="utf-8")
        print(f"  Saved: {output_path}")

    elapsed = time.time() - start
    doc.close()

    summary = {
        "pages_processed": PAGES_TO_PROCESS,
        "total_time_seconds": round(elapsed, 2),
        "pages": all_pages,
    }
    summary_path = OUTPUT_DIR / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"\nTotal time: {elapsed:.1f}s")
    print(f"Summary saved: {summary_path}")


if __name__ == "__main__":
    main()
