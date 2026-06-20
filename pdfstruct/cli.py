"""
pdfstruct/cli.py

Interfaz de línea de comandos para pdfstruct.
"""

import typer
from pathlib import Path
from rich.console import Console

from .core import PdfStruct

app = typer.Typer(
    help="pdfstruct - Extractor de documentos a Markdown de alta calidad",
    add_completion=False
)
console = Console()


@app.command()
def extract(
    document: Path = typer.Argument(..., help="Ruta al documento (PDF, DOCX, PPTX, etc.)"),
    output: Path = typer.Option(
        None,
        "--output", "-o",
        help="Ruta del archivo Markdown de salida"
    ),
    images_dir: Path = typer.Option(
        "pdf_images",
        "--images-dir",
        help="Carpeta donde guardar las imágenes extraídas (solo para PDFs)"
    ),
):
    """
    Extrae un documento a Markdown usando el extractor más adecuado.
    """
    console.print(f"[bold blue]Procesando:[/bold blue] {document}")

    try:
        struct = PdfStruct(images_output_dir=str(images_dir))
        result = struct.extract(document)

        if output is None:
            output = document.with_suffix(".structured.md")

        output = Path(output)
        output.write_text(result.markdown, encoding="utf-8")

        console.print(f"[green]✓ Markdown guardado en:[/green] {output}")
        console.print(f"[green]✓ Extractor:[/green] {result.metadata.get('extractor', 'desconocido')}")

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
