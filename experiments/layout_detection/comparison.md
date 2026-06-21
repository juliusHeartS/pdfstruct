# Comparación de detectores de layout - doc_03

Páginas seleccionadas: 10 páginas complejas del documento `doc_03_link.1_01_9789275129708_eng.pdf`.

Cada detector se evalúa en número de detecciones objetivo (`Table` / `Picture`)

y tiempo de inferencia por página.



| Página | YOLOv8-detections | YOLOv8-time (s) | LMv3-large-detections | LMv3-large-time (s) | LMv3-base-detections | LMv3-base-time (s) |
|--------|-------------------|-----------------|-----------------------|---------------------|----------------------|---------------------|
| 30 | 1 | 0.350 | 7 | 0.577 | 8 | 0.213 |
| 34 | 1 | 0.226 | 12 | 0.508 | 12 | 0.178 |
| 35 | 1 | 0.226 | 13 | 0.618 | 13 | 0.224 |
| 36 | 1 | 0.225 | 4 | 0.619 | 4 | 0.229 |
| 41 | 2 | 0.241 | 0 | 0.615 | 10 | 0.225 |
| 43 | 2 | 0.238 | 1 | 0.550 | 10 | 0.210 |
| 44 | 2 | 0.240 | 3 | 0.582 | 12 | 0.215 |
| 50 | 1 | 0.239 | 2 | 0.321 | 4 | 0.116 |
| 54 | 2 | 0.238 | 1 | 0.386 | 1 | 0.137 |
| 56 | 2 | 0.240 | 5 | 0.452 | 5 | 0.166 |
| **Total** | **15** | **2.463** | **48** | **5.228** | **79** | **1.913** |

## Observaciones cualitativas

### YOLOv8-doclaynet
- **Mejor opción para pdfstruct**.
- Bounding boxes limpios y bien definidos.
- Detecta correctamente tablas completas (ej. página 34) y figuras/gráficos (ej. página 41).
- Sin dependencia de OCR/Tesseract.
- Tiempo de inferencia muy rápido (~0.2–0.4s por página en CPU).
- Modelo de 137 MB (YOLOv8x).

### LayoutLMv3-large
- Clasifica tokens OCR a nivel de palabra.
- Requiere post-proceso complejo para agrupar tokens en regiones coherentes.
- En la práctica, genera muchas cajas pequeñas dispersas en lugar de una región por tabla/figura.
- Tiempo más lento (~0.5–0.6s por página).
- Modelo pesado (~1.4 GB).

### LayoutLMv3-base
- Similar a large pero más rápido (~0.1–0.2s por página).
- Sigue sufriendo del mismo problema de post-proceso.
- Modelo de ~500 MB.

## Conclusión

Para el modo híbrido de pdfstruct, **YOLOv8-doclaynet es la opción recomendada** porque:

1. Devuelve bounding boxes listos para recortar y enviar a GLM-OCR.
2. Es rápido y liviano comparado con LayoutLMv3.
3. No requiere Tesseract ni OCR previo.
4. Detecta tanto tablas (`Table`) como figuras/gráficos (`Picture`).
5. Los resultados visuales son claros y útiles.

## Siguiente paso recomendado

Implementar un prototipo de enriquecimiento híbrido:

1. Extraer Markdown base con PyMuPDF4LLM.
2. Detectar `Table` y `Picture` con YOLOv8-doclaynet.
3. Recortar esas regiones.
4. Enviar los recortes a GLM-OCR con prompts específicos.
5. Insertar los resultados en el Markdown base.

## Archivos generados
- `experiments/layout_detection/yolo/results.json`
- `experiments/layout_detection/layoutlmv3_large/results.json`
- `experiments/layout_detection/layoutlmv3_base/results.json`
- Visualizaciones con sufijo `_vis.png` en cada carpeta.