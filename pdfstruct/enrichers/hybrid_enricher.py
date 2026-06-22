"""
pdfstruct/enrichers/hybrid_enricher.py

Enriquecimiento híbrido de PDFs:
- YOLOv8-doclaynet detecta tablas y figuras.
- PyMuPDF extrae bloques de texto y estructura de tablas.
- GLM-OCR via Ollama refina tablas complejas y describe figuras.
- Se reconstruye cada página ordenando texto + detecciones verticalmente.
"""

from __future__ import annotations

import difflib
import logging
import re
import tempfile
from pathlib import Path
from typing import Any, Callable

import fitz
from PIL import Image
from markdownify import markdownify as md

from ..config import GlmOcrConfig, HybridConfig
from ..extractors.layout_detector import LayoutDetector
from ..extractors.ollama_glm_ocr_client import OllamaGlmOcrClient
from ..utils import ensure_dir

logger = logging.getLogger(__name__)

ProgressCallback = Callable[[str, int, int], None]


class HybridEnricher:
    """
    Enriquece PDFs usando detección de layout + GLM-OCR selectivo.
    """

    def __init__(
        self,
        glm_ocr_config: GlmOcrConfig,
        hybrid_config: HybridConfig | None = None,
    ):
        self.glm_ocr_config = glm_ocr_config
        self.hybrid_config = hybrid_config or HybridConfig()
        self.client = OllamaGlmOcrClient(glm_ocr_config)
        self.layout_detector: LayoutDetector | None = None

    def _get_layout_detector(self) -> LayoutDetector:
        if self.layout_detector is None:
            self.layout_detector = LayoutDetector(
                model_path=self.hybrid_config.yolo_model_path,
                target_labels=self.hybrid_config.target_labels,
                conf=self.hybrid_config.conf_threshold,
                iou=self.hybrid_config.iou_threshold,
            )
        return self.layout_detector

    def enrich(
        self,
        pdf_path: str | Path,
        page_chunks: list[dict[str, Any]],
        images_dir: Path,
        output_dir: Path | None = None,
        filename_prefix: str = "doc",
        progress_callback: ProgressCallback | None = None,
    ) -> tuple[str, int, int]:
        """
        Enriquece los chunks de página con el pipeline híbrido.

        Returns:
            (markdown_enriquecido, paginas_procesadas, elementos_enriquecidos)
        """
        pdf_path = Path(pdf_path)
        images_dir = ensure_dir(images_dir)
        doc = fitz.open(str(pdf_path))

        total_pages = len(page_chunks)
        processed_pages = 0
        enriched_elements = 0
        enriched_parts: list[str] = []

        try:
            for chunk in page_chunks:
                page_number = chunk.get("metadata", {}).get("page_number", 1)
                if page_number < 1 or page_number > len(doc):
                    enriched_parts.append(chunk.get("text", ""))
                    continue

                page = doc.load_page(page_number - 1)
                logger.debug("Procesando página %d con pipeline híbrido", page_number)

                page_text, element_count = self._process_page(
                    page,
                    page_number,
                    images_dir,
                    filename_prefix,
                    output_dir=output_dir,
                )
                enriched_elements += element_count

                marker = f"<!-- PAGE: {page_number} / {total_pages} -->"
                if page_text.strip():
                    enriched_parts.append(f"{marker}\n\n{page_text.strip()}")
                else:
                    enriched_parts.append(marker)

                processed_pages += 1
                if progress_callback is not None:
                    progress_callback("hybrid_page", processed_pages, total_pages)
        finally:
            doc.close()

        return "\n\n".join(enriched_parts), processed_pages, enriched_elements

    def _process_page(
        self,
        page: fitz.Page,
        page_number: int,
        images_dir: Path,
        filename_prefix: str,
        output_dir: Path | None = None,
    ) -> tuple[str, int]:
        """Procesa una sola página: detecta layout, enriquece, ensambla."""
        config = self.hybrid_config

        # Renderizar página completa para YOLO.
        matrix = fitz.Matrix(config.dpi / 72, config.dpi / 72)
        pixmap = page.get_pixmap(matrix=matrix)
        image = Image.frombytes("RGB", [pixmap.width, pixmap.height], pixmap.samples)

        detections = self._get_layout_detector().detect(image)
        text_blocks = self._get_text_blocks(page)
        text_blocks = self._filter_overlapping_text_blocks(text_blocks, detections)

        enriched: dict[tuple[int, str], str | None] = {}
        element_count = 0
        for idx, element in enumerate(detections):
            try:
                if element["label"] == "Table":
                    result = self._enrich_table(image, element, page)
                else:
                    result = self._enrich_picture(image, element)
                enriched[(idx, element["label"])] = result
                if result:
                    element_count += 1
            except Exception as exc:
                logger.warning(
                    "Error enriqueciendo %s en página %d: %s",
                    element["label"],
                    page_number,
                    exc,
                )
                enriched[(idx, element["label"])] = None

        return (
            self._build_page_markdown(text_blocks, detections, enriched),
            element_count,
        )

    # ------------------------------------------------------------------
    # Helpers de coordenadas y texto
    # ------------------------------------------------------------------

    def _image_bbox_to_pdf_rect(self, bbox: list[float]) -> fitz.Rect:
        scale = 72 / self.hybrid_config.dpi
        return fitz.Rect(
            bbox[0] * scale,
            bbox[1] * scale,
            bbox[2] * scale,
            bbox[3] * scale,
        )

    def _get_text_blocks(self, page: fitz.Page) -> list[dict]:
        blocks = page.get_text("blocks")
        result = []
        for block in blocks:
            x0, y0, x1, y1, text, *_ = block
            text = str(text).strip()
            if not text:
                continue
            result.append(
                {
                    "text": text,
                    "rect": fitz.Rect(x0, y0, x1, y1),
                    "y": (y0 + y1) / 2,
                }
            )
        return result

    def _filter_overlapping_text_blocks(
        self,
        text_blocks: list[dict],
        detections: list[dict],
    ) -> list[dict]:
        detection_rects = [
            self._image_bbox_to_pdf_rect(d["bbox"]) for d in detections
        ]

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
            if not any(
                inside_detection(block["rect"], det_rect)
                for det_rect in detection_rects
            )
        ]

    def _build_page_markdown(
        self,
        text_blocks: list[dict],
        detections: list[dict],
        enriched: dict[tuple[int, str], str | None],
    ) -> str:
        elements: list[dict] = []

        for block in text_blocks:
            elements.append({"type": "text", "y": block["y"], "content": block["text"]})

        for idx, det in enumerate(detections):
            det_rect = self._image_bbox_to_pdf_rect(det["bbox"])
            y = (det_rect.y0 + det_rect.y1) / 2
            content = enriched.get((idx, det["label"]))
            if content is None:
                content = (
                    f"[_{det['label']} no pudo ser enriquecido; "
                    f"ver imagen original_]"
                )
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

    # ------------------------------------------------------------------
    # Tablas
    # ------------------------------------------------------------------

    def _extract_table_with_pymupdf(
        self,
        page: fitz.Page,
        pdf_rect: fitz.Rect,
    ) -> dict | None:
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
        empty_cells = sum(
            1 for row in data for cell in row if cell is None or str(cell).strip() == ""
        )
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

    def _table_data_to_markdown(
        self,
        data: list[list[str | None]],
        header: bool = True,
    ) -> str:
        lines = []
        for i, row in enumerate(data):
            cells = [
                str(cell).replace("\n", " ") if cell is not None else ""
                for cell in row
            ]
            lines.append("| " + " | ".join(cells) + " |")
            if i == 0 and header:
                lines.append("|" + "|".join(["---"] * len(row)) + "|")
        return "\n".join(lines)

    def _enrich_table(
        self,
        image: Image.Image,
        element: dict,
        page: fitz.Page,
    ) -> str | None:
        pdf_rect = self._image_bbox_to_pdf_rect(element["bbox"])
        raw_text = page.get_text("text", clip=pdf_rect).strip()

        # 1. Intento rápido con PyMuPDF.
        pymupdf_table = self._extract_table_with_pymupdf(page, pdf_rect)
        if pymupdf_table and pymupdf_table["quality"] == "good":
            return self._table_data_to_markdown(
                pymupdf_table["data"], header=pymupdf_table["header"]
            )

        # 2. Información previa para GLM-OCR.
        prior_parts = []
        if pymupdf_table:
            prior_parts.append(
                f"Estructura aproximada: {pymupdf_table['rows']} filas, "
                f"{pymupdf_table['cols']} columnas."
            )
        else:
            blocks = page.get_text("blocks", clip=pdf_rect)
            approx_rows = max(2, sum(1 for b in blocks if str(b[4]).strip()))
            prior_parts.append(f"Filas aproximadas: {approx_rows}.")
        prior_info = " ".join(prior_parts)

        # 3. Decidir si dividir.
        x1, y1, x2, y2 = element["bbox"]
        table_height = y2 - y1
        page_height = image.height
        table_ratio = table_height / page_height
        raw_lines = [ln for ln in raw_text.splitlines() if ln.strip()]
        cfg = self.hybrid_config

        is_dense = (
            len(raw_lines) > cfg.dense_split_min_lines
            and table_ratio < cfg.table_split_height_ratio
        )
        needs_split = table_ratio > cfg.table_split_height_ratio or is_dense

        base_prompt = (
            "Extrae el contenido exacto de esta tabla. "
            "Si es compleja (celdas combinadas), usa HTML; si es simple, Markdown. "
            "Extrae TODAS las filas visibles, no omitas ninguna. "
            "Devuelve SOLO la tabla, sin texto explicativo, sin leyendas y sin repetir. "
            f"{prior_info}"
        )

        if not needs_split:
            crop = image.crop((int(x1), int(y1), int(x2), int(y2)))
            response = self._call_ocr(crop, base_prompt)
            return self._clean_table_response(response) if response else None

        logger.debug("Tabla grande/densa; se divide en chunks")
        chunks = self._split_table_image(image, element["bbox"])
        chunk_results = []
        for i, chunk in enumerate(chunks):
            prompt = (
                base_prompt
                + f" Fragmento {i + 1} de {len(chunks)}. "
                "Las primeras filas son el encabezado; inclúyelo."
            )
            response = self._call_ocr(chunk, prompt)
            if response:
                chunk_results.append(self._clean_table_response(response))

        if not chunk_results:
            return None
        if len(chunk_results) == 1:
            return chunk_results[0]
        return self._merge_table_chunks(chunk_results)

    def _split_table_image(
        self,
        image: Image.Image,
        bbox: list[float],
    ) -> list[Image.Image]:
        cfg = self.hybrid_config
        x1, y1, x2, y2 = [int(c) for c in bbox]
        table_width = x2 - x1
        table_height = y2 - y1
        max_chunk_height = int(image.height * cfg.max_chunk_height_ratio)

        header_height = max(int(table_height * cfg.header_ratio), 30)
        header_crop = image.crop((x1, y1, x2, y1 + header_height))

        data_top = y1 + header_height
        data_bottom = y2
        data_height = data_bottom - data_top
        max_data_height = max_chunk_height - header_height

        if data_height <= max_data_height or max_data_height <= 0:
            return [image.crop((x1, y1, x2, y2))]

        overlap = max(int(data_height * cfg.overlap_ratio), 20)
        chunks: list[Image.Image] = []
        current = data_top
        while current < data_bottom:
            bottom = min(current + max_data_height, data_bottom)
            data_crop = image.crop((x1, current, x2, bottom))
            combined = Image.new(
                "RGB", (table_width, header_height + data_crop.height)
            )
            combined.paste(header_crop, (0, 0))
            combined.paste(data_crop, (0, header_height))
            chunks.append(combined)
            current += max_data_height - overlap
            if bottom == data_bottom:
                break

        return chunks if chunks else [image.crop((x1, y1, x2, y2))]

    # ------------------------------------------------------------------
    # Figuras
    # ------------------------------------------------------------------

    def _enrich_picture(self, image: Image.Image, element: dict) -> str | None:
        x1, y1, x2, y2 = [int(c) for c in element["bbox"]]
        crop = image.crop((x1, y1, x2, y2))

        prompt = (
            "This is a statistical chart or figure from a technical document. "
            "Identify the chart type and extract the main message plus visible "
            "numerical data in a coherent way. Return a short paragraph and a "
            "Markdown table or list with key data points. Do not hallucinate. "
            "Do not repeat."
        )
        response = self._call_ocr(crop, prompt, num_predict=2048)
        if not response:
            return None
        return self._clean_figure_response(response)

    # ------------------------------------------------------------------
    # GLM-OCR y post-proceso
    # ------------------------------------------------------------------

    def _call_ocr(
        self,
        image: Image.Image,
        prompt: str,
        num_predict: int | None = None,
    ) -> str | None:
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp_path = Path(tmp.name)
        try:
            image.save(tmp_path)
            options = {"num_predict": num_predict} if num_predict else None
            return self.client.generate(prompt, image_path=tmp_path, options=options)
        except Exception as exc:
            logger.warning("GLM-OCR error: %s", exc)
            return None
        finally:
            tmp_path.unlink(missing_ok=True)

    def _deduplicate_sentences(self, text: str) -> str:
        sentences = re.split(r"(?<=[.!?])\s+", text.strip())
        seen = set()
        unique = []
        for sentence in sentences:
            normalized = " ".join(sentence.lower().split())
            if normalized and normalized not in seen:
                seen.add(normalized)
                unique.append(sentence)
        return " ".join(unique)

    def _deduplicate_paragraphs(self, text: str) -> str:
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text.strip()) if p.strip()]
        seen = set()
        unique = []
        for paragraph in paragraphs:
            normalized = re.sub(r"\s+", " ", paragraph.lower())
            if normalized not in seen:
                seen.add(normalized)
                unique.append(paragraph)
        return "\n\n".join(unique)

    def _first_sentence(self, text: str) -> str:
        match = re.match(r"[^.!?]*[.!?]", text.strip())
        return match.group(0).strip() if match else text.strip()

    def _clean_table_response(self, response: str) -> str:
        response = re.sub(r"^```(?:markdown)?\s*", "", response.strip())
        response = re.sub(r"\s*```$", "", response.strip())
        response = self._deduplicate_sentences(response)
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

    def _clean_figure_response(self, response: str) -> str:
        response = re.sub(r"```(?:markdown)?", "", response)
        response = re.sub(r"[】\]\[\ufeff]+", "", response)
        response = self._deduplicate_sentences(response)
        response = self._deduplicate_paragraphs(response)

        first = self._first_sentence(response)

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

        for paragraph in response.split("\n\n"):
            if paragraph.strip():
                return paragraph.strip()
        return response.strip()

    # ------------------------------------------------------------------
    # Merge de tablas divididas
    # ------------------------------------------------------------------

    def _parse_markdown_table(self, text: str) -> list[list[str]]:
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

    def _rows_are_similar(self, a: list[str], b: list[str]) -> bool:
        if len(a) != len(b):
            return False
        matches = 0
        total = 0
        for ca, cb in zip(a, b):
            if ca.strip() or cb.strip():
                total += 1
                sa, sb = ca.strip().lower(), cb.strip().lower()
                if sa == sb or sa in sb or sb in sa:
                    matches += 1
                elif difflib.SequenceMatcher(None, sa, sb).ratio() >= 0.65:
                    matches += 1
        if total == 0:
            return True
        return matches / total >= 0.65

    def _row_completeness(self, row: list[str]) -> int:
        return sum(len(c) for c in row)

    def _merge_table_chunks(self, chunks_text: list[str]) -> str:
        parsed_chunks = [self._parse_markdown_table(t) for t in chunks_text]
        parsed_chunks = [c for c in parsed_chunks if c]
        if not parsed_chunks:
            return "\n\n".join(chunks_text).strip()

        merged: list[list[str]] = []
        for idx, rows in enumerate(parsed_chunks):
            if not merged:
                merged.extend(rows)
                continue
            data_rows = rows[1:] if idx > 0 else rows
            for row in data_rows:
                replaced = False
                for eidx, existing in enumerate(merged):
                    if self._rows_are_similar(row, existing):
                        if self._row_completeness(row) > self._row_completeness(existing):
                            merged[eidx] = row
                        replaced = True
                        break
                if not replaced:
                    merged.append(row)

        return self._table_data_to_markdown(merged, header=True)
