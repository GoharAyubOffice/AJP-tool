"""DOCX to PDF conversion using LibreOffice - to be implemented Day 2."""

import subprocess
from pathlib import Path


def docx_to_pdf(docx_path: Path, output_dir: Path | None = None) -> Path:
    """
    Convert a DOCX file to PDF using LibreOffice headless.

    Args:
        docx_path: Path to the input DOCX file
        output_dir: Directory for the output PDF (defaults to same as DOCX)

    Returns:
        Path to the generated PDF file

    Requires LibreOffice to be installed:
        Windows: winget install TheDocumentFoundation.LibreOffice
        macOS: brew install libreoffice
        Linux: apt install libreoffice

    TODO: Implement in Day 2
    """
    if output_dir is None:
        output_dir = docx_path.parent

    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)

    # Run LibreOffice headless conversion
    subprocess.run(
        [
            "soffice",
            "--headless",
            "--convert-to", "pdf",
            "--outdir", str(output_dir),
            str(docx_path),
        ],
        check=True,
    )

    return output_dir / (docx_path.stem + ".pdf")
