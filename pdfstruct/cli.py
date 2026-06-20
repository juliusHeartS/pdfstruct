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
        help="Carpeta donde guardar las imágenes extraídas (solo PDFs)"
    ),
):
    """
    Extrae un documento a Markdown usando MarkItDown.
    """
    console.print(f"[bold blue]Procesando documento:[/bold blue] {document}")

    try:
        struct = PdfStruct(images_output_dir=str(images_dir))
        result = struct.extract(document)

        if output is None:
            output = document.with_suffix(".structured.md")

        output = Path(output)
        output.write_text(result.markdown, encoding="utf-8")

        console.print(f"[green]✓ Markdown guardado en:[/green] {output}")
        console.print(f"[green]✓ Tipo de archivo:[/green] {result.metadata.get('file_type')}")
        console.print(f"[green]✓ Es PDF:[/green] {result.metadata.get('is_pdf', False)}")

        if result.images_dir:
            console.print(f"[green]✓ Imágenes extraídas en:[/green] {result.images_dir}")

    except Exception as e:
        console.print(f"[red]Error al procesar el documento:[/red] {e}")
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()