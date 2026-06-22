# Descripción técnica de pdfstruct

## Resumen ejecutivo

`pdfstruct` es una librería de Python diseñada para convertir documentos, principalmente archivos PDF, en Markdown de alta calidad. Nace de la necesidad de transformar publicaciones institucionales complejas —tablas densas, figuras, esquemas organizacionales, layouts de dos columnas y contenido multilingüe— en texto estructurado que pueda alimentar sistemas de recuperación de información, bases de datos vectoriales, pipelines de RAG y flujos de análisis documental.

La librería ofrece tres modos de extracción. El modo `soft` usa PyMuPDF4LLM para obtener Markdown limpio y rápido. El modo `hard` enriquece cada página con GLM-OCR a través de Ollama, aprovechando la capacidad multimodal del modelo para interpretar tablas complejas y figuras. El modo `hybrid`, la línea de trabajo más reciente, combina detección de layout con YOLOv8-doclaynet, extracción estructural con PyMuPDF y refuerzo selectivo con GLM-OCR, atacando solo las regiones que realmente lo necesitan.

Este documento describe la historia del proyecto, la motivación detrás de cada decisión de arquitectura, las tecnologías elegidas, los resultados obtenidos y las limitaciones conocidas. También ofrece instrucciones de uso prácticas para quienes quieran incorporar `pdfstruct` en sus propios proyectos o pipelines de RAG, ya sea para indexación masiva, análisis documental o sistemas de preguntas y respuestas.

## 1. Historia y evolución del proyecto

### 1.1. Origen y primeras iteraciones

El proyecto comenzó como un extractor experimental orientado a PDFs del conjunto `paho_pdfs`, un corpus de publicaciones de la Organización Panamericana de la Salud. Estos documentos representan un desafío típico en el procesamiento de documentos institucionales: portadas formales, tablas de contenido, tablas estadísticas extensas, figuras con datos, anexos y referencias, todo en layouts de alta densidad informativa. La primera versión de `pdfstruct` apuntaba a ofrecer una envoltura simple sobre extractores existentes, con validación cruzada básica y post-procesamiento de tablas.

En la versión 0.2.0 la base estaba formada por PyMuPDF4LLM como extractor principal y MarkItDown como extractor secundario para otros formatos. La validación cruzada comparaba la longitud del texto extraído por ambos motores y emitía advertencias cuando las diferencias eran significativas, lo cual permitía detectar omisiones importantes en documentos de una sola página o en contenido con estructuras no textuales.

### 1.2. La transición lejos de Marker

Durante las primeras iteraciones se evaluó el uso de Marker, una herramienta especializada en la extracción de PDFs académicos y libros. Aunque Marker ofrece buenos resultados en documentos con fuentes tipográficas estándar y estructuras relativamente predecibles, presentó varios inconvenientes para el corpus objetivo. En primer lugar, Marker introduce una dependencia pesada y un proceso de instalación más complejo. En segundo lugar, su rendimiento en documentos institucionales con tablas complejas, esquemas y contenido mixto no fue consistentemente superior al de un enfoque más ligero basado en PyMuPDF. Finalmente, mantener Marker como dependencia opcional complicaba el empaquetado, las pruebas y la experiencia de instalación para los usuarios.

La decisión de eliminar Marker por completo liberó el proyecto de una dependencia opcional conflictiva y permitió enfocar los esfuerzos en un extractor principal sólido y en un enriquecedor visual basado en modelos locales. Este cambio se consolidó en la versión 0.3.0.

### 1.3. Llegada de GLM-OCR y Ollama

Con Marker fuera del diseño, el siguiente paso natural fue incorporar un componente de visión para mejorar la extracción de elementos no textuales. Se eligió GLM-OCR, un modelo multimodal capaz de interpretar imágenes de páginas y regiones, devolviendo su contenido como Markdown o HTML. La principal ventaja de GLM-OCR es que puede leer tablas y figuras directamente desde una imagen, sin depender de la calidad de la capa de texto incrustada en el PDF.

Para mantener la librería autosuficiente y evitar dependencias de servicios en la nube, se decidió ejecutar GLM-OCR a través de Ollama. Esto permite operar completamente localmente, preserva la privacidad de los documentos y evita costos por uso. La integración se implementó con llamadas HTTP directas al endpoint `/api/generate` de Ollama, en lugar de usar un SDK específico de GLM-OCR. Esta elección redujo dependencias, simplificó el mantenimiento y dio un control total sobre el payload, los prompts y las opciones de generación.

Inicialmente se experimentó con OCR por regiones: recortar cada tabla o figura detectada y enviarla al modelo. Sin embargo, GLM-OCR tendía a devolver HTML malformado o fragmentado cuando recibía recortes aislados. Después de varias pruebas, el enfoque que mejor funcionó fue enviar la página completa al modelo, dejando que GLM-OCR interpretara el contexto visual completo. Las tablas devueltas en HTML se convirtieron automáticamente a Markdown con `markdownify`, lo que mejoró sustancialmente la calidad de las tablas complejas en el modo `hard`.

### 1.4. Hacia el modo híbrido

Aunque el modo `hard` entrega buena calidad, su costo computacional es alto: procesar un documento de 84 páginas con GLM-OCR página completa puede tomar entre 20 y 50 minutos, dependiendo del hardware. Para muchos casos de uso esto es excesivo, especialmente cuando solo un pequeño porcentaje de las páginas contiene tablas o figuras que realmente requieren visión.

Esta observación llevó al desarrollo del modo `hybrid`. La idea es usar un detector de layout rápido para identificar tablas y figuras, mantener la extracción rápida de PyMuPDF para el texto corriente, y aplicar GLM-OCR solo sobre las regiones detectadas. El modo híbrido representa un compromiso entre calidad y velocidad, orientado a documentos donde el texto plano es mayoritario pero donde las tablas y figuras son críticas.

La primera versión del modo híbrido se prototipó en `experiments/layout_detection/hybrid_prototype.py` y se probó en 10 páginas representativas del documento más complejo del corpus. Después de ajustar la estrategia de división de tablas grandes, el post-procesamiento de repeticiones y la comparación entre resultados de PyMuPDF y GLM-OCR, se migró el código a módulos de producción bajo `pdfstruct/extractors/layout_detector.py` y `pdfstruct/enrichers/hybrid_enricher.py`.

El desarrollo del modo híbrido también respondió a una necesidad de control. En el modo `hard`, el modelo de visión decide qué extraer de cada página, lo cual es conveniente pero opaco. En el modo híbrido, el usuario puede inspeccionar las detecciones de layout, ajustar umbrales de confianza, modificar los prompts por tipo de elemento y decidir, mediante configuración, cuánto recursos invertir en cada página. Esta flexibilidad es valiosa para pipelines de producción donde la reproducibilidad y la auditoría importan tanto como la calidad.

## 2. Motivación y problemas que resuelve

### 2.1. PDFs como fuente de información estructurada

Los PDFs siguen siendo el formato dominante para informes, políticas, manuales y publicaciones oficiales. A diferencia de HTML o Markdown, el PDF está optimizado para la representación visual, no para la lectura estructurada por máquinas. Esto crea un problema central: un PDF puede verse perfectamente bien para un humano mientras que su contenido subyacente es una secuencia de bloques de texto, imágenes y trazos sin relación semántica explícita.

Cuando estos documentos se usan en pipelines de RAG o análisis automatizado, la calidad de la extracción determina directamente la calidad de la recuperación. Una tabla mal convertida en texto continuo, una figura ignorada o un índice desordenado pueden hacer que un sistema no encuentre información relevante o, peor aún, genere respuestas incorrectas. El problema se intensifica cuando los modelos de lenguaje intentan razonar sobre datos que fueron extraídos de forma desordenada: una fila de tabla partida en dos chunks puede producir inferencias estadísticas erróneas, y una figura reducida a un nombre de archivo sin descripción hace imposible responder preguntas sobre tendencias visuales.

### 2.2. Limitaciones de los extractores generales

Extractores generales como MarkItDown o las conversiones directas con PyMuPDF funcionan razonablemente bien en documentos simples. Sin embargo, enfrentan dificultades sistemáticas:

- **Tablas complejas**: cuando una tabla tiene celdas combinadas, colores de fondo, notas al pie o está dividida en varias páginas, la extracción como texto plano pierde la estructura.
- **Figuras y gráficos**: los gráficos de barras, líneas, pastel y los diagramas de flujo se extraen como imágenes sin descripción, perdiendo su contenido informativo.
- **Layouts de varias columnas**: el orden de lectura puede confundirse si el extractor recorre las columnas en el orden incorrecto.
- **Encabezados y pies de página repetidos**: sin un post-procesamiento cuidadoso, estos elementos se insertan en medio de párrafos.
- **Documentos escaneados o con tipografías especiales**: cuando la capa de texto es deficiente, los extractores basados en texto plano fallan.

`pdfstruct` no resuelve todos estos problemas de forma perfecta, pero proporciona una arquitectura modular que permite elegir la estrategia adecuada según el documento y los requisitos de calidad.

### 2.3. Necesidad de trazabilidad

Un aspecto frecuentemente ignorado en los extractores es la trazabilidad. `pdfstruct` inserta marcadores de página en el Markdown de salida y permite guardar las imágenes extraídas en una carpeta organizada. Esto es útil para sistemas RAG que necesitan citar la fuente de una respuesta o para auditorías humanas que requieren verificar el contenido original.

## 3. Arquitectura general

`pdfstruct` se organiza en capas que van desde la interfaz de usuario hasta los extractores especializados. El punto de entrada principal es la clase `PdfStruct` en `pdfstruct/core.py`, que decide si el archivo es un PDF u otro documento y delega el trabajo al procesador correspondiente.

### 3.1. `PdfStruct`: fachada principal

`PdfStruct` expone una API sencilla para extraer documentos. Al inicializarse, carga la configuración desde `pdfstruct.yaml`, variables de entorno y argumentos explícitos, resolviendo prioridades en ese orden. Soporta tres modos de operación para PDFs:

- `soft`: solo PyMuPDF4LLM, sin OCR.
- `hard`: PyMuPDF4LLM como base, pero reemplaza el contenido de cada página por el Markdown generado por GLM-OCR a partir de la página completa.
- `hybrid`: usa YOLOv8-doclaynet para detectar tablas y figuras, PyMuPDF para el texto corriente, y GLM-OCR para refinar regiones detectadas.

La fachada también permite limitar el procesamiento a un número máximo de páginas, guardar el resultado en un archivo de salida y recibir retroalimentación de progreso mediante un callback.

### 3.2. `PDFProcessor`: orquestador para PDFs

`PDFProcessor`, en `pdfstruct/pdf.py`, coordina la extracción base, la validación cruzada, el post-procesamiento de tablas y el enriquecimiento opcional con GLM-OCR. Sus componentes principales son:

- `PyMuPDF4LLMExtractor`: extrae Markdown por página usando `pymupdf4llm`, con buen soporte para layouts complejos.
- `MarkItDownExtractor`: extractor secundario usado principalmente para otros formatos o como referencia de validación cruzada.
- `CrossValidator`: compara longitudes de texto entre extractores para detectar posibles omisiones.
- `TablePostProcessor`: repara y limpia tablas Markdown.
- `OllamaEnricher`: aplica GLM-OCR página completa en modo `hard`.
- `HybridEnricher`: aplica detección de layout y enriquecimiento selectivo en modo `hybrid`.

### 3.3. `Config`: configuración centralizada

El sistema de configuración vive en `pdfstruct/config.py`. Define dos dataclasses principales: `GlmOcrConfig` y `HybridConfig`. La configuración se resuelve en cuatro niveles de prioridad, de menor a mayor:

1. Valores por defecto en el código.
2. Archivo `pdfstruct.yaml` en el directorio de trabajo.
3. Variables de entorno con prefijo `PDFSTRUCT_*` (compatibilidad legacy `GLM_OCR_*`).
4. Argumentos explícitos pasados a `PdfStruct` o al CLI.

La decisión de usar un archivo YAML visible, en lugar de esconder la configuración en variables de entorno exclusivamente, busca facilitar la experimentación y la documentación de parámetros para usuarios técnicos. Este enfoque también mejora la reproducibilidad: dos usuarios que compartan el mismo `pdfstruct.yaml` obtendrán resultados comparables sin depender de un estado oculto en sus shell. En entornos de desarrollo colaborativo, el archivo de configuración puede versionarse junto al proyecto, mientras que los secretos o rutas locales siguen pudiendo sobrescribirse mediante variables de entorno.

### 3.4. `OllamaGlmOcrClient`: cliente ligero de OCR

El cliente en `pdfstruct/extractors/ollama_glm_ocr_client.py` envía imágenes codificadas en base64 al endpoint `/api/generate` de Ollama. Soporta prompts personalizados para tablas y figuras, opciones adicionales como `num_predict`, y verificación de disponibilidad del servidor. Al no depender del SDK `glmocr`, el código es más transparente y fácil de adaptar a cambios en la API de Ollama.

### 3.5. `LayoutDetector` y `HybridEnricher`: pipeline híbrido

El detector de layout, en `pdfstruct/extractors/layout_detector.py`, carga un modelo YOLOv8 entrenado sobre DocLayNet. Si no se proporciona una ruta local, descarga automáticamente el modelo desde Hugging Face. El detector devuelve bounding boxes con etiquetas como `Table` y `Picture`, listas para recortar.

`HybridEnricher`, en `pdfstruct/enrichers/hybrid_enricher.py`, implementa la lógica de combinación:

1. Renderiza cada página a una imagen de alta resolución.
2. Detecta elementos de layout.
3. Extrae bloques de texto con PyMuPDF y filtra aquellos que caen dentro de detecciones, para evitar duplicación.
4. Para cada tabla detectada, intenta primero `find_tables` de PyMuPDF; si la calidad es insuficiente, recurre a GLM-OCR.
5. Si una tabla es muy alta o muy densa, la divide en franjas horizontales con encabezado repetido y luego fusiona los resultados eliminando filas duplicadas.
6. Para figuras, envía el recorte a GLM-OCR con un prompt estricto que pide el tipo de gráfico y los datos numéricos principales.
7. Reconstruye la página ordenando verticalmente los bloques de texto y las detecciones enriquecidas.

### 3.6. Excepciones y logging

La librería define excepciones propias en `pdfstruct/exceptions.py`: `PdfStructError`, `ConfigurationError`, `ExtractionError`, `FileError` y `OcrError`. Esto permite a los usuarios capturar errores específicos e integrar `pdfstruct` en flujos de control robustos. El logging utiliza el namespace `pdfstruct`, lo que facilita configurar niveles de detalle y destinos desde la aplicación que consume la librería.

La jerarquía de excepciones refleja las distintas capas del sistema. `FileError` cubre problemas de lectura y rutas inexistentes. `ConfigurationError` indica que la configuración activa no puede producir el modo solicitado, como cuando se pide modo `hard` sin Ollama disponible. `OcrError` agrupa fallos de comunicación con Ollama o respuestas inesperadas del modelo. `ExtractionError` cubre errores durante el procesamiento del documento. Finalmente, `PdfStructError` actúa como excepción base para toda la librería. Esta organización permite a quien integra `pdfstruct` decidir el nivel de granularidad con el que desea manejar fallos.

## 4. Elección de tecnologías

### 4.1. PyMuPDF4LLM como extractor base

PyMuPDF, a través del paquete `pymupdf4llm`, fue elegido como extractor base por varias razones:

- Es rápido y estable.
- Produce Markdown con marcadores de página y buen soporte para layouts de dos columnas.
- Permite extraer imágenes incrustadas y bloques de texto con coordenadas.
- Tiene funciones auxiliares como `find_tables` para recuperar la estructura tabular.
- Está ampliamente mantenido y documentado.

Para documentos bien formateados con capa de texto clara, PyMuPDF4LLM entrega resultados de alta calidad a bajo costo computacional. Esto lo hace ideal para el modo `soft` y como base del modo `hybrid`.

### 4.2. MarkItDown como extractor complementario

MarkItDown se usa principalmente para otros formatos de office y como referencia en la validación cruzada. No es el extractor principal para PDFs porque, en pruebas internas, PyMuPDF4LLM obtuvo mejores resultados en layouts densos. Sin embargo, mantenerlo en la arquitectura permite que `pdfstruct` siga siendo útil para DOCX, XLSX, PPTX y otros documentos sin necesidad de importar librerías adicionales por defecto.

### 4.3. GLM-OCR vía Ollama

GLM-OCR fue elegido como modelo de visión porque:

- Está disponible como modelo local a través de Ollama.
- Produce salida en Markdown o HTML.
- Entiende tablas y figuras sin necesidad de un pipeline de detección de layout previo.
- Permite personalizar prompts para tareas específicas.
- Funciona sin dependencia de servicios en la nube, lo que preserva la privacidad del documento y evita costos variables.

El costo principal es el tiempo de inferencia. En una MacBook Pro M2 Max con 64 GB de RAM, procesar una página con GLM-OCR toma típicamente entre 10 y 40 segundos, dependiendo de la complejidad. Esto hace que el modo `hard` sea adecuado para documentos cortos o páginas críticas, pero no para procesamiento masivo sin recursos de GPU.

Una decisión importante fue implementar la integración con llamadas HTTP directas a `/api/generate` en lugar de usar el SDK oficial de GLM-OCR. Esto redujo dependencias, hizo transparente el payload enviado al modelo y permitió ajustar opciones como `num_predict` para controlar la longitud máxima de la respuesta. En pipelines de producción, tener control directo sobre la comunicación con Ollama facilita el debugging y la adaptación a futuras versiones de la API.

### 4.4. YOLOv8-doclaynet frente a LayoutLMv3

Para el modo híbrido se evaluaron dos familias de detectores de layout: YOLOv8 entrenado en DocLayNet y LayoutLMv3 en sus variantes base y large.

Los experimentos en 10 páginas complejas del documento `doc_03` arrojaron los siguientes resultados cualitativos:

- **YOLOv8-doclaynet**: bounding boxes limpios y bien definidos, detección correcta de tablas completas y figuras, independencia de OCR previo, tiempos de inferencia de 0.2 a 0.4 segundos por página en CPU, modelo de 137 MB.
- **LayoutLMv3-large**: clasifica tokens a nivel de palabra, requiere post-proceso complejo para agrupar regiones, genera muchas cajas pequeñas dispersas, tiempos de 0.5 a 0.6 segundos por página, modelo de aproximadamente 1.4 GB.
- **LayoutLMv3-base**: similar a large pero más rápido, aunque sigue sufriendo el mismo problema de agrupación.

Por estas razones se eligió YOLOv8-doclaynet. Su salida está lista para recortar y enviar a GLM-OCR, y su peso razonable permite distribuirlo como dependencia opcional sin gravar la instalación base.

### 4.5. Dependencias opcionales

Para no forzar a todos los usuarios a instalar modelos pesados, las dependencias de modo híbrido se declaran como extras en `pyproject.toml`:

```toml
[project.optional-dependencies]
hybrid = ["ultralytics", "huggingface_hub"]
dev = ["pytest", "pytest-cov", "ruff"]
```

De este modo, una instalación base (`pip install pdfstruct`) es liviana y rápida, mientras que los usuarios que necesiten modo híbrido pueden usar `pip install pdfstruct[hybrid]`.

## 5. Proceso de extracción en cada modo

### 5.1. Modo `soft`

1. Se verifica que el archivo exista y sea un PDF.
2. Se abre el documento con PyMuPDF.
3. Se extrae Markdown por páginas usando PyMuPDF4LLM.
4. Se ejecuta un post-procesamiento ligero de tablas.
5. Se insertan marcadores de página.
6. Se guardan las imágenes incrustadas en el directorio configurado.
7. Opcionalmente se ejecuta validación cruzada con MarkItDown.

Este modo es el más rápido y consume pocos recursos. Es la opción por defecto y funciona bien para PDFs bien formateados y para prototipos rápidos. Es también la base recomendada para pipelines de indexación masiva donde el objetivo es cubrir muchos documentos con una calidad razonable antes de aplicar extracciones más costosas de forma selectiva.

### 5.2. Modo `hard`

1. Se realiza la extracción base con PyMuPDF4LLM, principalmente para obtener la estructura de página y las imágenes incrustadas.
2. Se verifica que Ollama esté disponible; si no responde, se lanza `ConfigurationError`.
3. Para cada página, se renderiza la página completa como imagen.
4. Se envía la imagen a GLM-OCR con un prompt que pide extraer el contenido completo en Markdown.
5. Si GLM-OCR devuelve HTML, se convierte a Markdown con `markdownify`.
6. El resultado reemplaza al Markdown base de esa página.
7. Se emiten marcadores de página y se actualiza la metadata.

Aunque el modo `hard` es lento, fue el primero en producir tablas bien estructuradas en documentos como `doc_03`, donde las tablas estadísticas son fundamentales.

### 5.3. Modo `hybrid`

1. Se renderiza cada página a imagen a 200 DPI.
2. YOLOv8-doclaynet detecta tablas y figuras.
3. PyMuPDF extrae los bloques de texto y se eliminan aquellos que están contenidos en detecciones.
4. Para cada tabla:
   - Se intenta `find_tables` de PyMuPDF.
   - Si la tabla es completa y consistente, se usa directamente.
   - Si no, se recurre a GLM-OCR.
   - Tablas altas o densas se dividen horizontalmente, repitiendo el encabezado en cada chunk.
   - Se fusionan los chunks eliminando filas duplicadas y conservando la versión más completa de cada fila.
5. Para cada figura:
   - Se recorta la región detectada.
   - Se envía a GLM-OCR con un prompt que pide identificar el tipo de gráfico y extraer los datos numéricos principales.
   - Se limpia la respuesta para evitar repeticiones y artefactos.
6. Se ordenan verticalmente bloques de texto y detecciones enriquecidas.
7. Se genera el Markdown final por página.

El modo híbrido reduce drásticamente el número de llamadas a GLM-OCR respecto al modo `hard`, concentrándose solo en las regiones problemáticas. La clave del diseño es la división horizontal inteligente de tablas grandes. Cuando una tabla ocupa más del 75% de la altura de la página o contiene más de 50 líneas de texto en poca altura, el sistema la divide en franjas con encabezado repetido. Cada franja se envía por separado a GLM-OCR, y los resultados se fusionan comparando filas con `difflib.SequenceMatcher` y conservando la versión más completa cuando hay solapamientos. Esta estrategia evita que el modelo omita filas por alcanzar el límite de contexto y mejora la calidad en tablas estadísticas extensas.

## 6. Resultados y evaluación

### 6.1. Corpus de evaluación

La evaluación se realizó sobre 10 documentos del corpus `paho_pdfs`, con un total de aproximadamente 463 páginas. Los documentos incluyen publicaciones en inglés, español y portugués, con una variedad de layouts y densidades de tablas e imágenes.

Los resultados de la extracción base y del modo GLM-OCR página completa se guardaron en `resultados4/`. El resumen muestra tiempos de extracción base entre 2.6 y 20.7 segundos para todo el documento, mientras que el modo `hard` requiere entre 13.7 segundos para un documento de una página y 2824.66 segundos para un documento de 84 páginas.

### 6.2. Comparación cualitativa de modos

- El modo `soft` produce Markdown limpio y utilizable para la mayoría de los documentos. Funciona especialmente bien en texto corrido, índices y páginas con una o dos columnas. En el corpus de evaluación, procesar documentos enteros tomó entre 2.6 y 20.7 segundos.
- El modo `hard` mejora notablemente la calidad de tablas complejas y la interpretación de figuras. Es la opción recomendada cuando la fidelidad estructural es prioritaria y el tiempo no es crítico. En el corpus, el documento de 84 páginas requirió 2824.66 segundos, mientras que documentos de una sola página se resolvieron en menos de 21 segundos.
- El modo `hybrid` está diseñado para ofrecer la mayor parte de la calidad del modo `hard` a una fracción del tiempo, siempre que el detector de layout sea preciso. La diferencia absoluta depende de cuántas regiones detecte YOLOv8 en cada documento.

### 6.3. Lecciones aprendidas

- Enviar páginas completas a GLM-OCR produce mejores resultados que enviar recortes aislados, porque el modelo utiliza el contexto visual circundante.
- PyMuPDF `find_tables` es suficiente para tablas regulares; GLM-OCR debe reservarse para tablas irregulares o con celdas combinadas.
- La división de tablas grandes en franjas horizontales, con encabezado repetido, evita que GLM-OCR omita filas por límite de contexto.
- El post-procesamiento de repeticiones es esencial, ya que GLM-OCR tiende a repetir oraciones o filas al final de respuestas largas.
- Los modelos de visión aproximan valores numéricos; no deben usarse como fuente de verdad para datos exactos sin verificación humana.

## 7. Limitaciones conocidas

### 7.1. Dependencia de Ollama en modos avanzados

Los modos `hard` y `hybrid` requieren que Ollama esté instalado, ejecutándose y con el modelo `glm-ocr` disponible. Si Ollama no responde, `pdfstruct` lanza `ConfigurationError` en lugar de caer silenciosamente a extracción base. Este comportamiento es intencional: evita que el usuario crea que obtuvo extracción enriquecida cuando en realidad no se ejecutó el modelo.

### 7.2. Rendimiento del modo `hard`

El procesamiento de página completa con GLM-OCR es intrínsecamente lento. En hardware CPU, documentos de decenas de páginas pueden tomar media hora o más. Este modo no está pensado para procesamiento masivo en tiempo real, sino para documentos cortos o páginas seleccionadas.

### 7.3. Precisión numérica de modelos de visión

GLM-OCR aproxima valores numéricos a partir de imágenes. En tablas estadísticas, es posible que algunos números no coincidan exactamente con los del PDF. Por esta razón, `pdfstruct` no garantiza exactitud numérica absoluta y recomienda verificación humana para aplicaciones críticas.

### 7.4. Calidad del detector de layout

YOLOv8-doclaynet funciona bien en documentos institucionales, pero puede fallar en tablas con bordes invisibles, figuras poco contrastadas o elementos no estándar. En modo `hybrid`, una detección omitida implica que esa tabla o figura se extraerá solo como texto o imagen, sin enriquecimiento.

### 7.5. Idiomas y tipografías

Aunque el corpus de prueba incluye inglés, español y portugués, documentos con tipografías muy ornamentadas, scripts no latinos o caligrafía pueden presentar dificultades tanto en PyMuPDF como en GLM-OCR.

### 7.6. No es determinista

GLM-OCR puede producir resultados ligeramente diferentes entre ejecuciones para la misma imagen. Esto significa que pipelines que dependen de hashes exactos del Markdown pueden necesitar tolerancias.

## 8. Instrucciones de uso

### 8.1. Instalación

Para la funcionalidad base:

```bash
git clone <repositorio>
cd pdfstruct
pip install -e .
```

Para modo híbrido:

```bash
pip install -e ".[hybrid]"
```

Para desarrollo:

```bash
pip install -e ".[dev]"
```

### 8.2. Configuración persistente

Crea un archivo `pdfstruct.yaml` en el directorio de trabajo:

```yaml
images_output_dir: pdf_images

glm_ocr:
  enabled: false
  url: http://localhost:11434
  model: glm-ocr:latest
  timeout: 600
```

Para activar GLM-OCR globalmente, cambia `enabled` a `true` o usa la variable de entorno:

```bash
export PDFSTRUCT_GLM_OCR_ENABLED=true
```

### 8.3. Uso como librería

Extracción base:

```python
from pdfstruct import PdfStruct

struct = PdfStruct(images_output_dir="imagenes_extraidas")
result = struct.extract("informe.pdf")
print(result.markdown)
```

Modo `hard`:

```python
struct = PdfStruct(mode="hard")
result = struct.extract("informe.pdf", output_path="salida.md")
```

Modo `hybrid` con callback de progreso:

```python
def on_progress(stage, current, total):
    print(f"{stage}: {current}/{total}")

struct = PdfStruct(mode="hybrid")
result = struct.extract(
    "informe.pdf",
    output_path="salida.md",
    progress_callback=on_progress,
)
```

Procesar solo un prefijo de páginas:

```python
result = struct.extract("libro.pdf", max_pages=5)
```

### 8.4. Uso desde la línea de comandos

```bash
# Modo soft
pdfstruct documento.pdf

# Modo hard con salida e imágenes
pdfstruct documento.pdf -o salida.md --images-dir imagenes_pdf --mode hard

# Modo híbrido con progreso
pdfstruct documento.pdf -o salida.md --images-dir imagenes_pdf --mode hybrid --progress

# Usar otro modelo de Ollama
pdfstruct documento.pdf --mode hard --glm-ocr-model glm-ocr:q8_0
```

### 8.5. Preparación de Ollama

```bash
ollama pull glm-ocr:latest
ollama serve
```

Si Ollama no está corriendo, los modos `hard` y `hybrid` fallarán con `ConfigurationError`, sin fallback silencioso.

## 9. Uso en sistemas RAG

### 9.1. División en chunks

El Markdown de salida incluye marcadores `<!-- PAGE: X / TOTAL -->` que facilitan dividir el documento en chunks semánticos. Un pipeline típico puede:

1. Dividir por páginas o por secciones de encabezado.
2. Asociar cada chunk con su número de página y, opcionalmente, con las imágenes extraídas de esa página.
3. Incluir metadatos del documento y del extractor usado.

### 9.2. Manejo de tablas y figuras

En modo `hard` e `hybrid`, las tablas se representan como tablas Markdown y las figuras como descripciones textuales. Esto permite que los modelos de lenguaje recuperen el contenido estructural sin depender de la interpretación de imágenes durante la generación. Para casos donde la imagen es indispensable, `pdfstruct` guarda los recortes en el directorio de imágenes configurado.

### 9.3. Trazabilidad

La metadata de `ExtractionResult` incluye el extractor usado, el número total de páginas, la cantidad de imágenes encontradas, advertencias de validación cruzada y, en modos avanzados, el número de páginas y elementos procesados por GLM-OCR. Esta trazabilidad es útil para filtrar resultados de baja confianza o para generar citas en respuestas de RAG.

Además, el uso de un namespace de logging propio (`pdfstruct`) permite a las aplicaciones que consumen la librería ajustar el nivel de detalle, redirigir la salida a archivos o sistemas de observabilidad, y correlacionar los eventos de extracción con el resto del pipeline. Para documentos de alto valor, recomendamos persistir tanto el Markdown como la metadata completa, incluyendo advertencias, tiempos y configuración activa.

### 9.4. Elección de modo según caso de uso

- Use `soft` para indexación masiva de PDFs bien formateados donde la velocidad es prioritaria.
- Use `hard` para documentos críticos con muchas tablas o figuras, donde la calidad justifica el tiempo de espera.
- Use `hybrid` para documentos largos con pocas tablas o figuras críticas distribuidas esporádicamente, o cuando se desea un balance medible entre tiempo y calidad.

Cuando se construye un pipeline de RAG, una estrategia recomendada es comenzar con el modo `soft` para todo el corpus y luego aplicar `hybrid` o `hard` de forma selectiva sobre las páginas que la validación cruzada marca como problemáticas o que contienen tablas y figuras detectadas automáticamente. Esta aproximación de dos etapas maximiza la cobertura sin incurrir en el costo total del OCR de página completa.

## 10. Estado actual y próximos pasos

A junio de 2026, `pdfstruct` se encuentra en la versión 0.3.0, preparándose para publicación en PyPI. La rama estable es `release/0.3.0` y el tag correspondiente es `v0.3.0`. Los avances incluyen:

- Extracción base funcional con PyMuPDF4LLM.
- Integración con GLM-OCR vía Ollama en modo `hard`.
- Pipeline híbrido con YOLOv8-doclaynet en modo `hybrid`.
- Configuración persistente, excepciones propias, logging estructurado y CLI.
- Tests unitarios e integración con documentos reales.

El trabajo de la versión 0.3.0 se concentró en tres objetivos: eliminar dependencias pesadas, ofrecer una integración local con modelos de visión y diseñar un modo híbrido escalable. La eliminación de Marker simplificó el empaquetado y redujo el tamaño de la instalación base. La integración con Ollama, usando llamadas HTTP directas, mantiene el código simple y transparente. El modo híbrido, basado en YOLOv8-doclaynet, demostró en prototipo que es posible enriquecer solo las regiones críticas sin procesar cada página completa.

Los próximos pasos planeados incluyen:

- Fortalecer el `CrossValidator` con reglas más sofisticadas que la simple comparación de longitudes.
- Mejorar el manejo de figuras vectoriales y diagramas organizacionales.
- Optimizar el modo híbrido para ejecutarse en GPU cuando esté disponible.
- Publicar la primera versión estable en PyPI.
- Evaluar el impacto del modo híbrido en métricas de recuperación de RAG sobre el corpus PAHO.

## 11. Conclusión

`pdfstruct` es el resultado de una serie de decisiones pragmáticas orientadas a producir Markdown de alta calidad a partir de PDFs complejos. La eliminación de Marker, la adopción de GLM-OCR vía Ollama, la configuración visible y el desarrollo del modo híbrido responden a un objetivo común: equilibrar calidad, velocidad, facilidad de uso y reproducibilidad.

La librería no pretende ser un extractor universal perfecto, sino una herramienta especializada para documentos institucionales y pipelines de RAG. Los usuarios pueden elegir el modo que mejor se adapte a sus necesidades, desde extracción rápida hasta interpretación visual profunda, manteniendo siempre trazabilidad y control sobre la configuración.

Mirando hacia adelante, el principal desafío de `pdfstruct` será mantener esta simplicidad mientras incorpora mejoras en la precisión numérica, la cobertura de figuras vectoriales y la integración con GPU. La arquitectura modular existente proporciona una base sólida para estos avances sin comprometer la estabilidad de la API pública.

## Referencias

- PyMuPDF y PyMuPDF4LLM: https://pymupdf.readthedocs.io
- MarkItDown: https://github.com/microsoft/markitdown
- Ollama: https://ollama.com
- GLM-OCR: modelo multimodal disponible en Ollama.
- YOLOv8 y DocLayNet: modelo de detección de layout usado en modo híbrido.
- `pdfstruct` repositorio: código fuente, tests y experimentes.

---

## Anexo 1. Documentos utilizados en las pruebas

Las pruebas de `pdfstruct` se realizaron sobre un conjunto de 10 documentos del corpus `paho_pdfs`, correspondientes a publicaciones de la Organización Panamericana de la Salud (PAHO/OPAS/OPS). A continuación se listan los archivos PDF evaluados, junto con el título identificado, el idioma principal, el número de páginas y una breve descripción del tipo de contenido. Estos documentos representan una muestra diversa de layouts institucionales: políticas, informes técnicos, guías metodológicas, perfiles de país y organigramas.

| Archivo PDF | Título del documento | Idioma | Páginas | Tipo de contenido |
|-------------|----------------------|--------|---------|-------------------|
| `doc_02_link.1_politica-ingles-2030-english-final.pdf` | Policy on the Health Workforce 2030: Strengthening Human Resources for Health to Achieve Resilient Health Systems | Inglés | 40 | Política regional con capítulos estructurados y anexos |
| `doc_03_link.1_01_9789275129708_eng.pdf` | The health workforce in the Americas: Regional data and indicators | Inglés | 84 | Informe estadístico extenso con múltiples tablas y figuras |
| `doc_04_link.1_sub1_01_guatemala.pdf` | Human resources for health: Country Profile — Guatemala | Inglés | 1 | Perfil de país de una sola página con tabla resumida |
| `doc_05_link.1_iris3_01_9789275129791_eng.pdf` | Interprofessional health teams for integrated care | Inglés | 40 | Publicación técnica sobre equipos interprofesionales de salud |
| `doc_05_link.1_sub2_01_org-chart-may-20-2026.pdf` | Organizational Chart of the Pan American Sanitary Bureau | Inglés | 1 | Organigrama institucional con estructura jerárquica |
| `doc_06_link_01_OPSHSSHR250010_spa.pdf` | Mapeo de actores y diálogo estratégico para la gobernanza de los sistemas de información de recursos humanos para la salud | Español | 70 | Guía técnica sobre gobernanza de sistemas de información |
| `doc_07_link_01_OPSHSSHR250007_spa.pdf` | Mapeo de ocupaciones de salud: Una metodología para su aplicación en la Región de las Américas | Español | 38 | Metodología para clasificación de ocupaciones de salud |
| `doc_08_link_01_OPSHSSHR250009_spa.pdf` | Guía conceptual para el desarrollo de sistemas de información de recursos humanos para la salud | Español | 53 | Guía conceptual con marcos teóricos y ejemplos |
| `doc_09_link_01_OPSHSSHR250008_spa.pdf` | Evaluación de la madurez de los sistemas de información de recursos humanos para la salud | Español | 62 | Instrumento y guía de evaluación de madurez |
| `doc_18_link.2_01_9789275720035_por.pdf` | Ampliação do papel dos enfermeiros na atenção primária à saúde | Portugués | 54 | Publicación sobre enfermería en atención primaria |

### Características del corpus de prueba

En total, el corpus suma **463 páginas** distribuidas en tres idiomas: inglés (5 documentos), español (4 documentos) y portugués (1 documento). Los documentos en inglés cubren principalmente políticas regionales, datos estadísticos regionales y publicaciones técnicas. Los documentos en español forman parte de la serie de fortalecimiento de sistemas de información de recursos humanos para la salud en las Américas. El documento en portugués representa una publicación específica sobre el papel de la enfermería en Brasil y la Región.

La selección buscaba representar la variedad de desafíos que `pdfstruct` debe enfrentar:

- **Tablas densas y extensas**: especialmente en `doc_03`, que contiene decenas de tablas y figuras estadísticas.
- **Layouts complejos**: `doc_03` incluye capítulos, anexos, perfiles de país y contenido en dos columnas.
- **Documentos cortos o de una sola página**: `doc_04` y el organigrama de `doc_05_sub2` permiten evaluar la robustez en casos límite.
- **Figuras y organigramas**: `doc_05_sub2` es un caso puro de figura estructural con texto incrustado.
- **Multilingüismo**: los documentos en español y portugués permitieron probar el comportamiento del extractor con acentos, caracteres latinos y estructuras lingüísticas distintas al inglés.

### Resultados de extracción disponibles

Los resultados de las extracciones base (`soft`) y con GLM-OCR página completa (`hard`) se encuentran en el directorio `resultados4/`:

- `resultados4/markdown/`: resultados del modo base con PyMuPDF4LLM.
- `resultados4/markdown_glm_ocr/`: resultados del modo GLM-OCR página completa.
- `resultados4/imagenes/`: imágenes extraídas en modo base.
- `resultados4/imagenes_glm_ocr/`: imágenes extraídas con GLM-OCR.
- `resultados4/metadata.json`: metadata completa de cada extracción, incluyendo tiempos, extractores, cantidad de imágenes y advertencias de validación cruzada.
- `resultados4/resumen.md`: resumen tabular de las 20 extracciones realizadas (10 documentos × 2 modos).

### Uso como referencia de prueba

Estos 10 documentos constituyen el banco de pruebas principal de `pdfstruct` para validar regresiones y comparar mejoras entre versiones. Cuando se evalúa una nueva estrategia de extracción, como el modo `hybrid`, se recomienda comenzar por un subconjunto representativo de páginas de `doc_03`, dado que es el documento con mayor densidad de tablas, figuras y variaciones de layout. El prototipo híbrido, por ejemplo, se validó inicialmente sobre 10 páginas seleccionadas de `doc_03` antes de generalizarse a todo el pipeline de producción.

### Nota sobre precisión de datos numéricos

Aunque `pdfstruct` utiliza modelos de visión como GLM-OCR para mejorar la extracción de tablas y figuras, es importante recordar que estos modelos son probabilísticos. La probabilidad de error en la obtención de datos numéricos siempre existe, especialmente en tablas pequeñas, cifras con decimales o símbolos particulares. Por esta razón, los resultados numéricos obtenidos con modos `hard` e `hybrid` deben considerarse enriquecidos pero no infalibles, y se recomienda verificación humana cuando los datos sean utilizados para análisis críticos o toma de decisiones.

`pdfstruct` está en mejora continua. Cada nueva versión busca reducir estos errores, mejorar la precisión numérica, ampliar la cobertura de figuras vectoriales y optimizar los tiempos de inferencia, manteniendo siempre una arquitectura modular y reproducible.
