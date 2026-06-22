"""Prueba rápida end-to-end del modo híbrido en la librería."""

from pathlib import Path

from pdfstruct import PdfStruct

PDF_PATH = Path("resultados4/pdfs/doc_03_link.1_01_9789275129708_eng.pdf")
OUTPUT_PATH = Path("experiments/layout_detection/hybrid_library_output.md")


def main() -> None:
    struct = PdfStruct(mode="hybrid")
    result = struct.extract(
        PDF_PATH,
        output_path=OUTPUT_PATH,
        max_pages=3,
        progress_callback=lambda stage, current, total: print(
            f"{stage}: {current}/{total}"
        ),
    )
    OUTPUT_PATH.write_text(result.markdown, encoding="utf-8")
    print(f"Saved to {OUTPUT_PATH}")
    print("Metadata:", result.metadata)
    print("---")
    print(result.markdown[:2000])


if __name__ == "__main__":
    main()
