# pdfstruct

Extractor de documentos a Markdown de alta calidad.

## Características actuales

- Soporta cualquier documento compatible con **MarkItDown** (PDF, DOCX, PPTX, XLSX, etc.).
- Para **PDFs** combina MarkItDown + PyMuPDF:
  - Markdown de buena calidad
  - Marcadores de página (`<!-- PAGE: X -->`)
  - Extracción y guardado de imágenes embebidas
  - Sección de referencias de imágenes al final del Markdown
- API simple y CLI funcional.

## Instalación

```bash
cd pdfstruct
pip install -e .
```

## Uso como biblioteca

```python
from pdfstruct import PdfStruct

struct = PdfStruct()

# Extraer cualquier documento
result = struct.extract("mi_documento.pdf")

print(result.markdown)           # Markdown generado
print(result.metadata)           # Metadata (páginas, imágenes, etc.)
```

## Uso como CLI

```bash
# Extracción básica
pdfstruct extract mi_documento.pdf -o salida.md

# Controlar directorio de imágenes
pdfstruct extract mi_documento.pdf --images-dir mis_imagenes
```

## Estructura del proyecto

```
pdfstruct/
├── pdfstruct/
│   ├── __init__.py
│   ├── core.py
│   ├── document.py              # Procesador genérico para documentos
│   ├── pdf.py                   # Procesador especializado para PDFs
│   ├── cli.py
│   ├── extractors/
│   │   ├── markitdown_extractor.py
│   │   └── pymupdf_extractor.py
│   └── enrichers/
│       ├── page_markers.py
│       └── image_handler.py
```

## Estado actual (junio 2026)

El extractor ya es funcional:
- Documentos generales → MarkItDown
- PDFs → MarkItDown + PyMuPDF (imágenes + páginas + referencias)

Próximos pasos planeados:
- Mejorar inserción de descripciones de imágenes (especialmente gráficos estadísticos)
- Mejor manejo de tablas complejas
- Soporte más avanzado de marcadores de página por sección

## Licencia

MIT