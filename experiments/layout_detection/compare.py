"""
experiments/layout_detection/compare.py

Compara resultados de YOLOv8-doclaynet, LayoutLMv3-large y LayoutLMv3-base.
"""

from __future__ import annotations

import json
from pathlib import Path

RESULTS = {
    "YOLOv8-doclaynet": Path("experiments/layout_detection/yolo/results.json"),
    "LayoutLMv3-large": Path("experiments/layout_detection/layoutlmv3_large/results.json"),
    "LayoutLMv3-base": Path("experiments/layout_detection/layoutlmv3_base/results.json"),
}


def load_results(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {int(item["page"]): item for item in data}


def main() -> None:
    loaded = {name: load_results(path) for name, path in RESULTS.items()}
    pages = sorted(next(iter(loaded.values())).keys())

    lines = [
        "# Comparación de detectores de layout - doc_03\n",
        "Páginas seleccionadas: 10 páginas complejas del documento `doc_03_link.1_01_9789275129708_eng.pdf`.\n",
        "Cada detector se evalúa en número de detecciones objetivo (`Table` / `Picture`)\n",
        "y tiempo de inferencia por página.\n",
        "\n",
        "| Página | YOLOv8-detections | YOLOv8-time (s) | LMv3-large-detections | LMv3-large-time (s) | LMv3-base-detections | LMv3-base-time (s) |",
        "|--------|-------------------|-----------------|-----------------------|---------------------|----------------------|---------------------|",
    ]

    totals = {name: {"detections": 0, "time": 0.0} for name in RESULTS}

    for page in pages:
        row = [str(page)]
        for name, data in loaded.items():
            item = data[page]
            detections = len(item["target_detections"])
            elapsed = item["elapsed_seconds"]
            totals[name]["detections"] += detections
            totals[name]["time"] += elapsed
            row.append(str(detections))
            row.append(f"{elapsed:.3f}")
        lines.append("| " + " | ".join(row) + " |")

    lines.append(
        "| **Total** | "
        + " | ".join(
            f"**{totals[name]['detections']}** | **{totals[name]['time']:.3f}**"
            for name in RESULTS
        )
        + " |"
    )

    lines.extend(
        [
            "\n## Notas",
            "- **YOLOv8-doclaynet**: detector de objetos visual puro. Devuelve bounding boxes limpios.",
            "- **LayoutLMv3-large/base**: clasificador de tokens OCR. Requiere post-proceso para agrupar tokens en regiones.",
            "- Los tiempos incluyen solo forward/inferencia, no carga de modelo ni pre/post-procesamiento de imagen.",
            "\n## Archivos generados",
            "- `experiments/layout_detection/yolo/results.json`",
            "- `experiments/layout_detection/layoutlmv3_large/results.json`",
            "- `experiments/layout_detection/layoutlmv3_base/results.json`",
            "- Visualizaciones con sufijo `_vis.png` en cada carpeta.",
        ]
    )

    output_path = Path("experiments/layout_detection/comparison.md")
    output_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Comparison saved to {output_path}")


if __name__ == "__main__":
    main()
