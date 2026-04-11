"""DOCX to PDF conversion using LibreOffice."""

import shutil
import subprocess
from pathlib import Path


class LibreOfficeNotFoundError(Exception):
    """Raised when LibreOffice is not installed or not in PATH."""
    pass


def find_soffice() -> str | None:
    """
    Find the soffice executable.

    Returns the path to soffice if found, None otherwise.
    """
    # Check if soffice is in PATH
    soffice_path = shutil.which("soffice")
    if soffice_path:
        return soffice_path

    # Check common Windows installation paths
    common_paths = [
        r"C:\Program Files\LibreOffice\program\soffice.exe",
        r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
    ]

    for path in common_paths:
        if Path(path).exists():
            return path

    return None


def is_libreoffice_installed() -> bool:
    """Check if LibreOffice is installed and available."""
    return find_soffice() is not None


def docx_to_pdf(docx_path: Path, output_dir: Path | None = None) -> Path:
    """
    Convert a DOCX file to PDF using LibreOffice headless.

    Args:
        docx_path: Path to the input DOCX file
        output_dir: Directory for the output PDF (defaults to same as DOCX)

    Returns:
        Path to the generated PDF file

    Raises:
        LibreOfficeNotFoundError: If LibreOffice is not installed
        subprocess.CalledProcessError: If conversion fails
        FileNotFoundError: If the input DOCX doesn't exist

    Installation:
        Windows: winget install TheDocumentFoundation.LibreOffice
        macOS: brew install libreoffice
        Linux: apt install libreoffice
    """
    # Verify input file exists
    if not docx_path.exists():
        raise FileNotFoundError(f"DOCX file not found: {docx_path}")

    # Find soffice
    soffice = find_soffice()
    if not soffice:
        raise LibreOfficeNotFoundError(
            "LibreOffice is not installed or not in PATH.\n"
            "Install it with: winget install TheDocumentFoundation.LibreOffice\n"
            "Then restart your terminal."
        )

    if output_dir is None:
        output_dir = docx_path.parent

    # Ensure output directory exists
    output_dir.mkdir(parents=True, exist_ok=True)

    # Run LibreOffice headless conversion
    try:
        subprocess.run(
            [
                soffice,
                "--headless",
                "--convert-to", "pdf",
                "--outdir", str(output_dir),
                str(docx_path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        raise RuntimeError(
            f"PDF conversion failed: {e.stderr or e.stdout or 'Unknown error'}"
        )

    # Return path to generated PDF
    pdf_path = output_dir / (docx_path.stem + ".pdf")

    if not pdf_path.exists():
        raise RuntimeError(
            f"PDF conversion completed but output file not found: {pdf_path}"
        )

    return pdf_path


def convert_all_docx_to_pdf(directory: Path) -> list[Path]:
    """
    Convert all DOCX files in a directory to PDF.

    Args:
        directory: Directory containing DOCX files

    Returns:
        List of paths to generated PDF files
    """
    if not is_libreoffice_installed():
        raise LibreOfficeNotFoundError(
            "LibreOffice is not installed. Cannot convert to PDF."
        )

    pdf_files = []
    for docx_file in directory.glob("*.docx"):
        pdf_path = docx_to_pdf(docx_file)
        pdf_files.append(pdf_path)

    return pdf_files
