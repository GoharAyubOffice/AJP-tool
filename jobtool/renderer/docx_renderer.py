"""ATS-compliant DOCX renderer - to be implemented Day 2 (CRITICAL)."""

from pathlib import Path

from jobtool.models import TailoredCV


def render_cv(cv: TailoredCV, output_path: Path) -> None:
    """
    Render a tailored CV to an ATS-compliant DOCX file.

    CRITICAL: This is the most important module in the project.
    All ATS compliance rules must be enforced here.

    Rules enforced:
    - Single column only (no Tables, no text boxes)
    - Arial font (11pt body, 14pt headings, 18pt name)
    - All content in document body (no headers/footers)
    - Exact section labels
    - Solid round bullets only
    - 2cm margins
    - British English

    TODO: Implement in Day 2
    """
    raise NotImplementedError("DOCX renderer not yet implemented")


def render_cover_letter(text: str, output_path: Path, candidate_name: str) -> None:
    """
    Render a cover letter to a DOCX file.

    TODO: Implement in Day 2
    """
    raise NotImplementedError("Cover letter renderer not yet implemented")
