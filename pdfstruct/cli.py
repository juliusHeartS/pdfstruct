"""
pdfstruct/cli.py

Interfaz de línea de comandos para pdfstruct.
"""

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn

from .config import GlmOcrConfig
from .core import PdfStruct, ProgressCallback

app = typer.Typer(
    help="pdfstruct - Extractor de documentos a Markdown de alta calidad",
    add_completion=False,
)
console = Console()


def _bool_option(value: str) -> bool:
    """Convierte una cadena de opción booleana a bool."""
    return value.lower() in ("1", "true", "yes", "on")


def _make_progress_callback(progress: Progress, task_id: int) -> ProgressCallback:
    """Crea un callback que actualiza una tarea de rich Progress."""

    def callback(stage: str, current: int, total: int) -> None:
        if total is not None and progress.tasks[task_id].total != total:
            progress.update(task_id, total=total)
        progress.update(task_id, completed=current)

    return callback


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
    mode: str = typer.Option(
        "soft",
        "--mode",
        help="Modo de extracción: 'soft', 'hard' (GLM-OCR página completa) o 'hybrid' (YOLO + GLM-OCR por regiones)",
    ),
    progress_flag: bool = typer.Option(
        False,
        "--progress",
        help="Muestra una barra de progreso durante el procesamiento",
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
    if mode not in ("soft", "hard", "hybrid"):
        console.print(
            f"[red]Error:[/red] --mode debe ser 'soft', 'hard' o 'hybrid', se recibió '{mode}'"
        )
        raise typer.Exit(code=1)

    console.print(f"[bold blue]Procesando:[/bold blue] {document}")
    console.print(f"[bold blue]Modo:[/bold blue] {mode}")

    enabled = _bool_option(glm_ocr_enabled)
    if mode in ("hard", "hybrid"):
        enabled = True
    elif mode == "soft":
        enabled = False

    glm_ocr_config = GlmOcrConfig.from_settings(
        enabled=enabled,
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

        progress_callback: Optional[ProgressCallback] = None
        if progress_flag and mode in ("hard", "hybrid"):
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                TextColumn("({task.completed}/{task.total} páginas)"),
                console=console,
                transient=False,
            ) as progress:
                task_id = progress.add_task(
                    "GLM-OCR en progreso...", total=None, start=True
                )
                progress_callback = _make_progress_callback(progress, task_id)
                result = struct.extract(
                    document, output_path=output, progress_callback=progress_callback
                )
        else:
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
