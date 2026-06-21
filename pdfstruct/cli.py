"""
pdfstruct/cli.py

Interfaz de línea de comandos para pdfstruct.
"""

import typer
from pathlib import Path
from rich.console import Console

from .config import GlmOcrConfig
from .core import PdfStruct

app = typer.Typer(
    help="pdfstruct - Extractor de documentos a Markdown de alta calidad",
    add_completion=False,
)
console = Console()


def _bool_option(value: str) -> bool:
    """Convierte una cadena de opción booleana a bool."""
    return value.lower() in ("1", "true", "yes", "on")


@app.command(name="extract")
def extract(
    document: Path = typer.Argument(
        ..., help="Ruta al documento (PDF, DOCX, PPTX, etc.)"
    ),
    output: Path = typer.Option(
        None, "--output", "-o", help="Ruta del archivo Markdown de salida"
    ),
    images_dir: Path = typer.Option(
        "pdf_images",
        "--images-dir",
        help="Carpeta donde guardar las imágenes extraídas (solo para PDFs)",
    ),
    glm_ocr_enabled: str = typer.Option(
        "false",
        "--glm-ocr-enabled",
        help="Activa GLM-OCR via Ollama para enriquecer tablas y figuras",
    ),
    glm_ocr_url: str = typer.Option(
        "http://localhost:11434", "--glm-ocr-url", help="URL del servidor Ollama"
    ),
    glm_ocr_model: str = typer.Option(
        "glm-ocr:latest", "--glm-ocr-model", help="Nombre del modelo GLM-OCR en Ollama"
    ),
    glm_ocr_timeout: int = typer.Option(
        600, "--glm-ocr-timeout", help="Timeout en segundos para peticiones a Ollama"
    ),
):
    """
    Extrae un documento a Markdown usando el extractor más adecuado.
    """
    console.print(f"[bold blue]Procesando:[/bold blue] {document}")

    glm_ocr_config = GlmOcrConfig.from_settings(
        enabled=_bool_option(glm_ocr_enabled),
        url=glm_ocr_url,
        model=glm_ocr_model,
        timeout=glm_ocr_timeout,
        images_dir=images_dir,
    )

    try:
        struct = PdfStruct(
            images_output_dir=str(images_dir),
            glm_ocr_config=glm_ocr_config,
        )

        if output is None:
            output = document.with_suffix(".structured.md")

        output = Path(output)
        result = struct.extract(document, output_path=output)

        output.write_text(result.markdown, encoding="utf-8")

        console.print(f"[green]✓ Markdown guardado en:[/green] {output}")

        if "ollama_pages_processed" in result.metadata:
            console.print(
                f"[green]✓ Páginas procesadas con GLM-OCR:[/green] "
                f"{result.metadata['ollama_pages_processed']}"
            )
        if "ollama_figures_processed" in result.metadata:
            console.print(
                f"[green]✓ Figuras enriquecidas con GLM-OCR:[/green] "
                f"{result.metadata['ollama_figures_processed']}"
            )

        warnings = result.metadata.get("cross_validation_warnings", [])
        if warnings:
            console.print("[yellow]⚠ Advertencias de validación cruzada:[/yellow]")
            for w in warnings:
                console.print(f"  - {w}")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
