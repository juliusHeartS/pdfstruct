# pdfstruct

**Extractor de documentos a Markdown de alta calidad**, especialmente diseñado para PDFs complejos y documentos institucionales.

El objetivo de `pdfstruct` es generar Markdown limpio, bien estructurado y rico en contexto, listo para ser utilizado en sistemas RAG, bases de datos vectoriales o pipelines de procesamiento de documentos.

## Características principales

- **Extracción de PDFs** utilizando **PyMuPDF4LLM** como motor principal (mejor soporte para layouts de dos columnas, tablas y orden de lectura).
- Soporte para **otros formatos** (DOCX, XLSX, PPTX, etc.) mediante MarkItDown.
- **Validación cruzada ligera** entre extractores para detectar posibles omisiones o problemas de extracción.
- Clasificación básica de imágenes (decorativas vs. imágenes con datos).
- Inserción de marcadores de página (`<!-- PAGE: X -->`).
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

# Inicializar
struct = PdfStruct(images_output_dir="imagenes_extraidas")

# Extraer un PDF
result = struct.extract("informe_anual.pdf")

print(result.markdown)           # Markdown generado
print(result.metadata)           # Metadata (extractor usado, warnings, etc.)

# Guardar directamente en archivo
output_path = struct.extract_to_file("informe_anual.pdf", output_path="salida.md")
```

### Como herramienta de línea de comandos

```bash
# Extracción básica
pdfstruct extract documento.pdf

# Especificar archivo de salida y carpeta de imágenes
pdfstruct extract documento.pdf -o salida.md --images-dir imagenes_pdf
```

## Arquitectura

```
PdfStruct
├── PDFProcessor (para PDFs)
│   ├── PyMuPDF4LLMExtractor (principal)
│   ├── MarkItDownExtractor (fallback)
│   ├── CrossValidator (validación cruzada)
│   └── ImageClassifier + PageMarkers (enriquecimiento)
│
└── DocumentProcessor (para DOCX, XLSX, PPTX, etc.)
    └── MarkItDownExtractor
```

## Estado actual del proyecto

El proyecto se encuentra en fase de desarrollo activo. Actualmente cuenta con:

- Extracción funcional de PDFs usando PyMuPDF4LLM.
- Soporte para documentos que no son PDF.
- Validación cruzada básica (reporta warnings).
- Clasificación simple de imágenes.
- CLI operativa.

**Próximos pasos planeados:**
- Mejorar la detección y clasificación de imágenes con datos.
- Fortalecer el `CrossValidator` con más reglas de validación.
- Mejorar el manejo de tablas complejas.
- Agregar soporte para descripciones de imágenes (OCR selectivo).

## Cuándo usar pdfstruct

- Cuando necesitas extraer PDFs con layouts complejos (dos columnas, tablas, gráficos).
- Cuando quieres un Markdown más limpio y estructurado que el que entrega MarkItDown por defecto en PDFs.
- Cuando estás construyendo un pipeline RAG y necesitas buena calidad de extracción + trazabilidad (páginas, imágenes).

## Licencia

MIT
