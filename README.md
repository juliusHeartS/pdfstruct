# pdfstruct

**Extractor de documentos a Markdown de alta calidad**, especialmente diseñado para PDFs complejos y documentos institucionales.

El objetivo de `pdfstruct` es generar Markdown limpio, bien estructurado y rico en contexto, listo para ser utilizado en sistemas RAG, bases de datos vectoriales o pipelines de procesamiento de documentos.

## Características principales

- **Extracción de PDFs** utilizando **PyMuPDF4LLM** como motor principal (mejor soporte para layouts de dos columnas, tablas y orden de lectura).
- **Modos `soft` y `hard`**:
  - `soft` (default): extracción rápida sin OCR enrichment.
  - `hard`: extracción con GLM-OCR via Ollama para mayor precisión en tablas y figuras.
- **Configuración visible** mediante `pdfstruct.yaml` y variables de entorno `PDFSTRUCT_*`.
- Soporte para **otros formatos** (DOCX, XLSX, PPTX, etc.) mediante MarkItDown.
- **Validación cruzada ligera** entre extractores para detectar posibles omisiones o problemas de extracción (se omite cuando GLM-OCR está activo para evitar OCR doble).
- Inserción de marcadores de página (`<!-- PAGE: X / TOTAL -->`).
- Referencias relativas de imágenes cuando se especifica `output_path`.
- Retroalimentación de progreso opcional para operaciones largas.
- Arquitectura modular y extensible.
- Interfaz de línea de comandos (CLI) funcional.

## Instalación

```bash
cd pdfstruct
pip install -e .
```

> **Nota:** Se recomienda tener instalada la librería `pymupdf4llm` para obtener el mejor rendimiento en PDFs.

## Uso

### Como biblioteca de Python

```python
from pdfstruct import PdfStruct
from pdfstruct.config import GlmOcrConfig

# Extracción básica con PyMuPDF4LLM
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

### Configuración persistente (`pdfstruct.yaml`)

Crea un archivo `pdfstruct.yaml` en el directorio de trabajo:

```yaml
images_output_dir: pdf_images

glm_ocr:
  enabled: false
  url: http://localhost:11434
  model: glm-ocr:latest
  timeout: 600
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

# Modo hard con barra de progreso
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
│   ├── OllamaEnricher (GLM-OCR opcional, OCR de página completa)
│   ├── MarkItDownExtractor (fallback)
│   ├── CrossValidator (validación cruzada)
│   └── TablePostProcessor + utilidades (limpieza y reparación)
│
└── DocumentProcessor (para DOCX, XLSX, PPTX, etc.)
    └── MarkItDownExtractor
```

## Estado actual del proyecto

El proyecto se encuentra en fase de preparación para publicación (v0.3.0). Actualmente cuenta con:

- Extracción funcional de PDFs usando PyMuPDF4LLM.
- Integración opcional con GLM-OCR via Ollama para OCR de página completa.
- Soporte para documentos que no son PDF.
- Validación cruzada básica (reporta warnings).
- CLI operativa.
- Configuración persistente mediante `pdfstruct.yaml`.
- Tests de integración con 10 PDFs reales.
- Logging estructurado y excepciones específicas.

**Próximos pasos planeados:**
- Fortalecer el `CrossValidator` con más reglas de validación.
- Mejorar el manejo de figuras vectoriales.
- Publicar en PyPI.

## Cuándo usar pdfstruct

- Cuando necesitas extraer PDFs con layouts complejos (dos columnas, tablas, gráficos).
- Cuando quieres un Markdown más limpio y estructurado que el que entrega MarkItDown por defecto en PDFs.
- Cuando estás construyendo un pipeline RAG y necesitas buena calidad de extracción + trazabilidad (páginas, imágenes).

## Licencia

MIT
