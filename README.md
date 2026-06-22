# pdfstruct

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Extractor de documentos a Markdown de alta calidad**, diseñado para PDFs complejos y documentos institucionales.

El objetivo de `pdfstruct` es generar Markdown limpio, bien estructurado y rico en contexto, listo para ser utilizado en sistemas RAG, bases de datos vectoriales o pipelines de procesamiento de documentos.

## Características principales

- **Extracción de PDFs** utilizando **PyMuPDF4LLM** como motor principal (mejor soporte para layouts de dos columnas, tablas y orden de lectura).
- **Tres modos de extracción**:
  - `soft` (default): extracción rápida sin OCR enrichment.
  - `hard`: extracción con GLM-OCR via Ollama para máxima precisión en tablas y figuras.
  - `hybrid`: detección de layout con YOLOv8-doclaynet + PyMuPDF + GLM-OCR selectivo por regiones.
- **Configuración visible** mediante `pdfstruct.yaml` y variables de entorno `PDFSTRUCT_*`.
- Soporte para **otros formatos** (DOCX, XLSX, PPTX, etc.) mediante MarkItDown.
- **Validación cruzada ligera** entre extractores para detectar posibles omisiones o problemas de extracción (se omite cuando GLM-OCR está activo para evitar OCR doble).
- Inserción de marcadores de página (`<!-- PAGE: X / TOTAL -->`).
- Referencias relativas de imágenes cuando se especifica `output_path`.
- Retroalimentación de progreso opcional para operaciones largas.
- Arquitectura modular y extensible.
- Interfaz de línea de comandos (CLI) funcional.

## Requisitos

- Python 3.10 o superior.
- Para modos `hard` e `hybrid`: [Ollama](https://ollama.com) instalado y corriendo con el modelo `glm-ocr:latest` disponible.
- Para modo `hybrid`: dependencias adicionales de `ultralytics` y `huggingface_hub`.

## Instalación

Instalación base (modos `soft` y `hard`):

```bash
git clone https://github.com/juliusHeartS/pdfstruct.git
cd pdfstruct
git checkout experiments/hybrid-layout-detection
pip install -e .
```

Instalación completa con modo `hybrid`:

```bash
pip install -e ".[hybrid]"
```

Instalación para desarrollo:

```bash
pip install -e ".[dev]"
```

> **Nota:** Se recomienda tener instalada la librería `pymupdf4llm` para obtener el mejor rendimiento en PDFs. Se instala automáticamente como dependencia principal.

## Uso

### Como biblioteca de Python

```python
from pdfstruct import PdfStruct

# Extracción básica con PyMuPDF4LLM (modo soft)
struct = PdfStruct(images_output_dir="imagenes_extraidas")
result = struct.extract("informe_anual.pdf")

print(result.markdown)           # Markdown generado
print(result.metadata)           # Metadata (extractor usado, warnings, etc.)

# Guardar directamente en archivo
output_path = struct.extract_to_file("informe_anual.pdf", output_path="salida.md")

# Procesar solo las primeras 5 páginas de un documento grande
result = struct.extract("libro_grueso.pdf", max_pages=5)
```

### Modo `hard` (GLM-OCR via Ollama)

```python
from pdfstruct import PdfStruct

# Mayor precisión, requiere Ollama
struct = PdfStruct(mode="hard", images_output_dir="imagenes_extraidas")
result = struct.extract("informe_anual.pdf", output_path="salida.md")

# Con callback de progreso
def on_progress(stage, current, total):
    print(f"{stage}: {current}/{total}")

result = struct.extract(
    "informe_anual.pdf",
    output_path="salida.md",
    progress_callback=on_progress,
)
```

### Modo `hybrid` (YOLOv8-doclaynet + GLM-OCR selectivo)

```python
from pdfstruct import PdfStruct

# Requiere Ollama y pip install "pdfstruct[hybrid]"
struct = PdfStruct(mode="hybrid", images_output_dir="imagenes_extraidas")
result = struct.extract("informe_anual.pdf", output_path="salida.md")
```

### Configuración persistente (`pdfstruct.yaml`)

Crea un archivo `pdfstruct.yaml` en el directorio de trabajo:

```yaml
images_output_dir: pdf_images

glm_ocr:
  enabled: false
  url: http://localhost:11434
  model: glm-ocr:latest
  timeout: 600

hybrid:
  dpi: 200
  conf_threshold: 0.25
  target_labels:
    - Table
    - Picture
```

`PdfStruct` lo cargará automáticamente y podrás sobrescribir valores
pasando argumentos o variables de entorno.

### Como herramienta de línea de comandos

```bash
# Extracción básica (modo soft, default)
pdfstruct documento.pdf

# Especificar archivo de salida y carpeta de imágenes
pdfstruct documento.pdf -o salida.md --images-dir imagenes_pdf

# Modo hard con GLM-OCR (requiere Ollama)
pdfstruct documento.pdf -o salida.md --images-dir imagenes_pdf --mode hard

# Modo híbrido (requiere Ollama y extras de hybrid)
pdfstruct documento.pdf -o salida.md --images-dir imagenes_pdf --mode hybrid

# Modo hard o híbrido con barra de progreso
pdfstruct documento.pdf -o salida.md --mode hard --progress

# Usar otro modelo de Ollama
pdfstruct documento.pdf --mode hard --glm-ocr-model glm-ocr:q8_0
```

## Configuración de GLM-OCR

Para usar GLM-OCR se requiere tener [Ollama](https://ollama.com) instalado y el modelo descargado:

```bash
# Instalar Ollama (macOS/Linux/Windows): https://ollama.com/download

# Descargar GLM-OCR
ollama pull glm-ocr:latest

# Asegurarse de que el servidor está corriendo
ollama serve
```

Variables de entorno reconocidas (prefijo recomendado `PDFSTRUCT_*`):

- `PDFSTRUCT_GLM_OCR_ENABLED=true` — activa GLM-OCR.
- `PDFSTRUCT_GLM_OCR_URL` — URL del servidor Ollama (default: `http://localhost:11434`).
- `PDFSTRUCT_GLM_OCR_MODEL` — modelo a usar (default: `glm-ocr:latest`).
- `PDFSTRUCT_GLM_OCR_TIMEOUT` — timeout en segundos (default: `600`).
- `PDFSTRUCT_IMAGES_OUTPUT_DIR` — directorio base para imágenes (default: `pdf_images`).

También se aceptan los nombres legacy `GLM_OCR_*`, pero `PDFSTRUCT_*` tiene prioridad.

## Arquitectura

```
PdfStruct
├── Config (carga de `pdfstruct.yaml`, env vars y defaults)
├── PDFProcessor (para PDFs)
│   ├── PyMuPDF4LLMExtractor (principal)
│   ├── OllamaEnricher (GLM-OCR página completa, modo hard)
│   ├── HybridEnricher (YOLO + GLM-OCR selectivo, modo hybrid)
│   ├── MarkItDownExtractor (fallback y otros formatos)
│   ├── CrossValidator (validación cruzada)
│   └── TablePostProcessor + utilidades (limpieza y reparación)
│
└── DocumentProcessor (para DOCX, XLSX, PPTX, etc.)
    └── MarkItDownExtractor
```

## Estado actual del proyecto

El proyecto se encuentra en fase activa de desarrollo (v0.3.0) en la rama `experiments/hybrid-layout-detection`. Actualmente cuenta con:

- Extracción funcional de PDFs usando PyMuPDF4LLM.
- Integración opcional con GLM-OCR via Ollama para OCR de página completa (modo `hard`).
- Pipeline híbrido con YOLOv8-doclaynet y GLM-OCR selectivo (modo `hybrid`).
- Soporte para documentos que no son PDF.
- Validación cruzada básica (reporta warnings).
- CLI operativa con soporte para los tres modos y barra de progreso.
- Configuración persistente mediante `pdfstruct.yaml`.
- Tests de integración con 10 PDFs reales del corpus PAHO.
- Logging estructurado y excepciones específicas.
- Documentación técnica en `DescripcionTecnicaPdfstruct.md`.

**Próximos pasos planeados:**
- Fortalecer el `CrossValidator` con más reglas de validación.
- Mejorar el manejo de figuras vectoriales y organigramas.
- Optimizar el modo `hybrid` para GPU.
- Publicar la primera versión estable en PyPI.

## Cuándo usar pdfstruct

- Cuando necesitas extraer PDFs con layouts complejos (dos columnas, tablas, gráficos).
- Cuando quieres un Markdown más limpio y estructurado que el que entrega MarkItDown por defecto en PDFs.
- Cuando estás construyendo un pipeline RAG y necesitas buena calidad de extracción + trazabilidad (páginas, imágenes).
- Cuando prefieres ejecutar modelos de visión localmente con Ollama en lugar de depender de APIs en la nube.

## Licencia

MIT

## Documentación adicional

Para una descripción técnica completa de la historia, motivación, arquitectura, elección de tecnologías, limitaciones e instrucciones de uso en RAG, consulta el documento [`DescripcionTecnicaPdfstruct.md`](DescripcionTecnicaPdfstruct.md).
