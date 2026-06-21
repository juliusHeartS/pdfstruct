# Changelog

Todos los cambios notables de este proyecto se documentarán en este archivo.

El formato está basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.0.0/).

## [0.3.0] - 2026-06-21

### Added
- Integración con GLM-OCR via Ollama usando llamadas HTTP directas a `/api/generate`.
- Extracción de página completa con GLM-OCR para preservar el layout y tablas complejas.
- Conversión automática de tablas HTML devueltas por GLM-OCR a Markdown con `markdownify`.
- Detección y descripción de figuras usando GLM-OCR.
- Configuración persistente y visible mediante `pdfstruct.yaml`.
- Soporte para variables de entorno con prefijo `PDFSTRUCT_*` (compatibilidad legacy `GLM_OCR_*`).
- Excepciones específicas: `PdfStructError`, `ConfigurationError`, `ExtractionError`, `FileError`, `OcrError`.
- Logging estructurado bajo el namespace `pdfstruct`.
- Parámetro `output_path` en `PdfStruct.extract()` para generar referencias relativas de imágenes.
- Parámetro `max_pages` para limitar el procesamiento a un prefijo del documento.
- Tests de integración con 10 PDFs reales del corpus `paho_pdfs`.
- CLI con opciones `--glm-ocr-enabled`, `--glm-ocr-url`, `--glm-ocr-model`, `--glm-ocr-timeout`.

### Changed
- Reemplazo completo de Marker por PyMuPDF4LLM + GLM-OCR/Ollama.
- La validación cruzada con MarkItDown se desactiva automáticamente cuando GLM-OCR está habilitado.
- `PdfStruct.__init__` ahora carga `pdfstruct.yaml` por defecto y permite sobrescribir con argumentos explícitos.

### Removed
- Dependencia opcional y soporte de Marker.
- Fallback silencioso a extracción base cuando GLM-OCR falla; ahora se lanza `ConfigurationError` si Ollama no está disponible.

## [0.2.0] - 2026-06-XX

### Added
- Extracción base de PDFs con PyMuPDF4LLM.
- Soporte de extracción para otros formatos con MarkItDown.
- Validación cruzada entre extractores.
- Post-procesamiento conservador de tablas.

### Removed
- (Placeholder para versiones anteriores)
