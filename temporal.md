### Estructura Actualizada de `pdfstruct` (Recomendada)

Después de analizar tu requerimiento y el diagnóstico que hiciste, aquí te presento la **estructura actualizada** que propongo. El objetivo es evolucionar lo que ya tenemos sin tirar todo, pero corrigiendo los dos problemas principales:

- Falta de **validación cruzada** real.
- Mejor manejo de **imágenes** (decorativas vs con datos).
- Aprovechar **PyMuPDF4LLM** como extractor principal para PDFs, manteniendo a MarkItDown.

---

### 1. Estructura General Recomendada

### 2. Responsabilidades de cada componente (Actualizado)

| Componente                    | Responsabilidad Principal                                                                 | Cambios respecto a la versión anterior |
|------------------------------|-------------------------------------------------------------------------------------------|----------------------------------------|
| **PdfStruct**                | Punto de entrada. Decide si usar `PDFProcessor` o `DocumentProcessor`                     | Agrega parámetro `images_output_dir` y lógica de decisión |
| **PDFProcessor**             | Orquestador para PDFs. Coordina extracción + validación cruzada + enriquecimiento         | **Cambia significativamente**. Ya no es solo secuencial |
| **DocumentProcessor**        | Maneja documentos que no son PDF (DOCX, XLSX, PPTX, etc.)                                 | Se mantiene similar |
| **MarkItDownExtractor**      | Extrae usando MarkItDown                                                                  | Se mantiene, pero se usa menos en PDFs |
| **PyMuPDF4LLMExtractor**     | Nuevo extractor principal para PDFs usando PyMuPDF4LLM                                    | **Nuevo** |
| **CrossValidator**           | Realiza la validación cruzada entre extractores (páginas, orden, tablas, imágenes)        | **Nuevo y crítico** |
| **ImageClassifier**          | Clasifica imágenes (decorativa vs con datos)                                              | **Nuevo** |
| **PageMarkers**              | Agrega marcadores de página `<!-- PAGE: X -->`                                            | Se mantiene y se integra mejor |

---

### 3. Flujo Propuesto para PDFs (el cambio más importante)

El flujo actual es lineal. El nuevo flujo propuesto es:

```
PDF → 
   ├─ PyMuPDF4LLMExtractor → Markdown + imágenes + metadata de layout
   ├─ MarkItDownExtractor    → Markdown alternativo (para comparación)
   └─ CrossValidator         → Compara ambos resultados
          │
          ├─ Corrige orden de lectura (columnas)
          ├─ Detecta y corrige tablas
          ├─ Clasifica imágenes (decorativas vs con datos)
          ├─ Agrega marcadores de página
          └─ Enriquece el Markdown final
```

**PDFProcessor** se convierte en el **orquestador** que:
1. Ejecuta ambos extractores.
2. Llama al `CrossValidator`.
3. Decide qué información usar del extractor A vs B.
4. Aplica enriquecedores (marcadores de página + clasificación de imágenes).


Flujo Recomendado dentro de PDFProcessor
textPDF de entrada
      │
      ▼
PyMuPDF4LLMExtractor → Markdown + imágenes + metadata
      │
      ▼
(Opcional) MarkItDownExtractor → Markdown alternativo (solo si se activa fallback o comparación)
      │
      ▼
CrossValidator → Compara ambos resultados y genera warnings
      │
      ▼
ImageClassifier → Clasifica imágenes extraídas
      │
      ▼
PageMarkers → Agrega marcadores de página
      │
      ▼
Markdown final enriquecido + metadata + warnings

Resumen de Cambios Principales

Nota: hay un import circular potencial entre core.py y pdf.py:
- core.py importa PDFProcessor desde .pdf
- pdf.py importa ExtractionResult desde .core
En la versión anterior lo resolví importando PDFProcessor de forma lazy. El nuevo código que me diste no hace eso, así que probablemente falle al ejecutar. Pero como me pediste crear el archivo exactamente con ese código, lo dejé tal cual. Lo podemos corregir después si es necesario.

