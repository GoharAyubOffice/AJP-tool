"""CLI commands for JobAutoApply."""

import json
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from pydantic import ValidationError

from jobtool import __version__
from jobtool.config import (
    get_data_dir,
    get_master_cv_path,
    get_applications_dir,
    get_browser_contexts_dir,
    get_logs_dir,
    INIT_DIRECTORIES,
)
from jobtool.db import init_schema
from jobtool.models import MasterCV

# ============================================================================
# App Setup
# ============================================================================

app = typer.Typer(
    name="jobtool",
    help="JobAutoApply - UK job application CLI with ATS-compliant CV generation",
    no_args_is_help=True,
)

master_cv_app = typer.Typer(help="Master CV management commands")
app.add_typer(master_cv_app, name="master-cv")

# Use legacy_windows=True for better Windows compatibility
console = Console(legacy_windows=True)


def print_success(message: str) -> None:
    """Print a success message in green."""
    console.print(f"[green][OK][/green] {message}")


def print_error(message: str) -> None:
    """Print an error message in red."""
    console.print(f"[red][ERROR][/red] {message}")


def print_warning(message: str) -> None:
    """Print a warning message in yellow."""
    console.print(f"[yellow][WARN][/yellow] {message}")


def print_info(message: str) -> None:
    """Print an info message in blue."""
    console.print(f"[blue][INFO][/blue] {message}")


# ============================================================================
# Version Callback
# ============================================================================

def version_callback(value: bool) -> None:
    if value:
        console.print(f"jobtool version {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        None,
        "--version",
        "-v",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit",
    ),
) -> None:
    """JobAutoApply - UK job application CLI with ATS-compliant CV generation."""
    pass


# ============================================================================
# Init Command
# ============================================================================

@app.command()
def init() -> None:
    """
    Initialise data directory and SQLite schema.

    Creates ~/.jobtool/ with subdirectories for applications,
    browser-contexts, and logs. Safe to re-run.
    """
    console.print(Panel.fit(
        "[bold blue]JobAutoApply[/bold blue] - Initialising...",
        border_style="blue",
    ))

    created_dirs = []
    existing_dirs = []

    # Create all directories
    for get_dir_func in INIT_DIRECTORIES:
        dir_path = get_dir_func()
        if dir_path.exists():
            existing_dirs.append(dir_path)
        else:
            dir_path.mkdir(parents=True, exist_ok=True)
            created_dirs.append(dir_path)

    # Create/update SQLite schema
    init_schema()

    # Report results
    console.print()

    if created_dirs:
        for d in created_dirs:
            print_success(f"Created {d}")

    if existing_dirs:
        for d in existing_dirs:
            print_info(f"Already exists: {d}")

    print_success(f"Database ready at {get_data_dir() / 'jobtool.db'}")

    # Check for Master CV
    master_cv_path = get_master_cv_path()
    if not master_cv_path.exists():
        console.print()
        print_warning(f"Master CV not found at {master_cv_path}")
        print_info("Copy master-cv-starter.json to that location and edit with your details.")
        print_info("Then run: jobtool master-cv validate")
    else:
        print_success(f"Master CV found at {master_cv_path}")

    console.print()
    console.print(Panel.fit(
        "[green]Initialisation complete![/green]\n\n"
        "Next steps:\n"
        "1. Copy your .env file with API keys\n"
        "2. Set up your Master CV at ~/.jobtool/master-cv.json\n"
        "3. Run: jobtool master-cv validate",
        border_style="green",
    ))


# ============================================================================
# Master CV Commands
# ============================================================================

@master_cv_app.command("validate")
def master_cv_validate(
    path: Path = typer.Option(
        None,
        "--path",
        "-p",
        help="Path to Master CV JSON (defaults to ~/.jobtool/master-cv.json)",
    ),
) -> None:
    """
    Validate Master CV JSON against the schema.

    Checks that the Master CV file exists, is valid JSON,
    and conforms to the expected Pydantic schema.
    """
    cv_path = path or get_master_cv_path()

    console.print(Panel.fit(
        f"[bold blue]Validating Master CV[/bold blue]\n{cv_path}",
        border_style="blue",
    ))
    console.print()

    # Check file exists
    if not cv_path.exists():
        print_error(f"File not found: {cv_path}")
        print_info("Create your Master CV from the starter template:")
        print_info("  cp master-cv-starter.json ~/.jobtool/master-cv.json")
        raise typer.Exit(1)

    # Try to parse JSON
    try:
        with open(cv_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print_error(f"Invalid JSON: {e}")
        raise typer.Exit(1)

    # Validate against Pydantic schema
    try:
        cv = MasterCV.model_validate(data)
    except ValidationError as e:
        print_error("Schema validation failed:")
        console.print()
        for error in e.errors():
            loc = " -> ".join(str(x) for x in error["loc"])
            msg = error["msg"]
            console.print(f"  [red]*[/red] {loc}: {msg}")
        console.print()
        raise typer.Exit(1)

    # Check for placeholder values
    placeholders = []

    # Check personal details
    pd = cv.personalDetails
    if "REPLACE_WITH" in pd.phone:
        placeholders.append("personalDetails.phone")
    if "REPLACE_WITH" in pd.email:
        placeholders.append("personalDetails.email")
    if pd.linkedin and "REPLACE_WITH" in pd.linkedin:
        placeholders.append("personalDetails.linkedin")
    if pd.github and "REPLACE_WITH" in pd.github:
        placeholders.append("personalDetails.github")
    if pd.website and "REPLACE_WITH" in pd.website:
        placeholders.append("personalDetails.website")

    # Check education grades
    for i, edu in enumerate(cv.education):
        if edu.grade and "REPLACE_WITH" in edu.grade:
            placeholders.append(f"education[{i}].grade")

    # Check certifications
    for i, cert in enumerate(cv.certifications):
        if "REPLACE_WITH" in cert.issueDate:
            placeholders.append(f"certifications[{i}].issueDate")
        if cert.expiryDate and "REPLACE_WITH" in cert.expiryDate:
            placeholders.append(f"certifications[{i}].expiryDate")
        if "REPLACE_WITH" in cert.issuer:
            placeholders.append(f"certifications[{i}].issuer")

    # Check projects
    for i, proj in enumerate(cv.projects):
        if proj.url and "REPLACE_WITH" in proj.url:
            placeholders.append(f"projects[{i}].url")

    # Report validation success
    print_success("JSON structure is valid")
    print_success("Schema validation passed")

    # Summary table
    console.print()
    table = Table(title="Master CV Summary", show_header=True)
    table.add_column("Section", style="cyan")
    table.add_column("Count", justify="right")

    table.add_row("Work Experience", str(len(cv.workExperience)))
    table.add_row("Education", str(len(cv.education)))
    table.add_row("Technical Skills", str(len(cv.skills.technical)))
    table.add_row("Soft Skills", str(len(cv.skills.soft)))
    table.add_row("Tools", str(len(cv.skills.tools)))
    table.add_row("Certifications", str(len(cv.certifications)))
    table.add_row("Languages", str(len(cv.languages)))
    table.add_row("Projects", str(len(cv.projects)))
    table.add_row("Achievements", str(len(cv.achievements)))

    console.print(table)

    # Warn about placeholders
    if placeholders:
        console.print()
        print_warning(f"Found {len(placeholders)} placeholder value(s) to fill in:")
        for p in placeholders:
            console.print(f"  [yellow]*[/yellow] {p}")
        console.print()
        print_info("Edit your Master CV and replace these before generating CVs.")
    else:
        console.print()
        print_success("No placeholder values found - Master CV is ready!")


@master_cv_app.command("edit")
def master_cv_edit(
    path: Path = typer.Option(
        None,
        "--path",
        "-p",
        help="Path to Master CV JSON (defaults to ~/.jobtool/master-cv.json)",
    ),
) -> None:
    """
    Open Master CV in your default editor.

    Uses $EDITOR environment variable (defaults to notepad on Windows, nano on Unix).
    """
    import os
    import subprocess

    cv_path = path or get_master_cv_path()

    if not cv_path.exists():
        print_error(f"File not found: {cv_path}")
        raise typer.Exit(1)

    editor = os.environ.get("EDITOR")
    if not editor:
        # Default editors by platform
        if sys.platform == "win32":
            editor = "notepad"
        else:
            editor = "nano"

    print_info(f"Opening {cv_path} in {editor}...")
    subprocess.run([editor, str(cv_path)])


# ============================================================================
# Stub Commands (to be implemented in later sprints)
# ============================================================================

@app.command()
def login(
    source: str = typer.Argument(..., help="Job board to log into (indeed, linkedin)"),
) -> None:
    """
    Log into a job board using Playwright browser.

    Opens a browser window for manual login. Session is saved
    for future scraping.
    """
    if source not in ("indeed", "linkedin"):
        print_error(f"Unknown source: {source}")
        print_info("Valid sources: indeed, linkedin")
        raise typer.Exit(1)

    print_warning("Login command not yet implemented (Day 4)")
    raise typer.Exit(0)


@app.command()
def scrape(
    query: str = typer.Argument(..., help="Search query (e.g., 'data entry')"),
    location: str = typer.Option("London", "--location", "-l", help="Job location"),
    sources: str = typer.Option("reed", "--sources", "-s", help="Comma-separated sources"),
    max_jobs: int = typer.Option(50, "--max", "-m", help="Max jobs per source"),
    salary_min: int = typer.Option(None, "--salary-min", help="Minimum salary filter"),
    posted: str = typer.Option(None, "--posted", help="Posted filter: today, week, month"),
) -> None:
    """
    Scrape jobs from specified sources.

    Fetches job listings matching the query and saves them to the database.
    """
    print_warning("Scrape command not yet implemented (Day 3-4)")
    raise typer.Exit(0)


@app.command("list")
def list_jobs(
    status: str = typer.Option(None, "--status", "-s", help="Filter by status"),
    source: str = typer.Option(None, "--source", help="Filter by source"),
) -> None:
    """
    List jobs in the database.

    Shows a table of scraped jobs with their status.
    """
    print_warning("List command not yet implemented (Day 5)")
    raise typer.Exit(0)


@app.command()
def generate(
    job_id: int = typer.Argument(..., help="Job ID to generate CV for"),
) -> None:
    """
    Generate tailored CV and cover letter for a job.

    Uses Claude AI to create ATS-compliant documents.
    """
    print_warning("Generate command not yet implemented (Day 3)")
    raise typer.Exit(0)


@app.command()
def review() -> None:
    """
    Interactive review loop for pending jobs.

    Step through jobs one at a time, generating CVs and submitting applications.
    """
    print_warning("Review command not yet implemented (Day 5)")
    raise typer.Exit(0)


@app.command()
def apply(
    url: str = typer.Argument(..., help="Job URL to apply to"),
) -> None:
    """
    Quick apply to a single job by URL.

    Scrapes the job, generates CV, and opens the application page.
    """
    print_warning("Apply command not yet implemented (Day 5)")
    raise typer.Exit(0)


@app.command()
def history(
    week: bool = typer.Option(False, "--week", help="Show only last 7 days"),
    month: bool = typer.Option(False, "--month", help="Show only last 30 days"),
    status: str = typer.Option(None, "--status", "-s", help="Filter by status"),
) -> None:
    """
    Show application history.

    Lists past applications with dates, companies, and statuses.
    """
    print_warning("History command not yet implemented (Day 5)")
    raise typer.Exit(0)


# ============================================================================
# Renderer Test Command (Day 2)
# ============================================================================

@app.command("render-test")
def render_test(
    cv_path: Path = typer.Option(
        None,
        "--cv",
        "-c",
        help="Path to Master CV JSON (defaults to test fixture)",
    ),
    output_dir: Path = typer.Option(
        None,
        "--output",
        "-o",
        help="Output directory (defaults to current directory)",
    ),
    job_title: str = typer.Option(
        "Data Entry Clerk",
        "--job-title",
        "-j",
        help="Job title for filename",
    ),
    pdf: bool = typer.Option(
        False,
        "--pdf",
        "-p",
        help="Also generate PDF (requires LibreOffice)",
    ),
) -> None:
    """
    Test the ATS-compliant DOCX renderer.

    Generates a sample CV from the Master CV or test fixture.
    Use this to validate ATS compliance before production use.

    After running, you should:
    1. Open the DOCX in Microsoft Word to verify formatting
    2. Upload to Jobscan to verify ATS parse success
    """
    from jobtool.renderer.docx_renderer import render_cv

    # Determine CV source
    if cv_path is None:
        # Try test fixture first, then user's Master CV
        fixture_path = Path(__file__).parent.parent / "tests" / "fixtures" / "sample-master-cv.json"
        if fixture_path.exists():
            cv_path = fixture_path
            print_info(f"Using test fixture: {cv_path}")
        else:
            cv_path = get_master_cv_path()
            print_info(f"Using Master CV: {cv_path}")

    if not cv_path.exists():
        print_error(f"CV file not found: {cv_path}")
        raise typer.Exit(1)

    # Load and validate CV
    try:
        with open(cv_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        cv = MasterCV.model_validate(data)
    except json.JSONDecodeError as e:
        print_error(f"Invalid JSON: {e}")
        raise typer.Exit(1)
    except ValidationError as e:
        print_error(f"Schema validation failed: {e}")
        raise typer.Exit(1)

    # Determine output directory
    if output_dir is None:
        output_dir = Path.cwd()

    output_dir.mkdir(parents=True, exist_ok=True)

    # Render the CV
    console.print(Panel.fit(
        "[bold blue]Rendering ATS-Compliant CV[/bold blue]",
        border_style="blue",
    ))

    try:
        output_file = render_cv(cv, output_dir, job_title)
        print_success(f"CV generated: {output_file}")
    except Exception as e:
        print_error(f"Render failed: {e}")
        raise typer.Exit(1)

    # PDF conversion if requested
    if pdf:
        from jobtool.renderer.pdf import docx_to_pdf, LibreOfficeNotFoundError

        try:
            pdf_file = docx_to_pdf(output_file)
            print_success(f"PDF generated: {pdf_file}")
        except LibreOfficeNotFoundError as e:
            print_warning(f"PDF skipped: {e}")
        except Exception as e:
            print_error(f"PDF conversion failed: {e}")

    # Print verification checklist
    console.print()
    console.print(Panel(
        "[bold]ATS Compliance Checklist[/bold]\n\n"
        "Open the DOCX file and verify:\n"
        "  1. Single column layout (no tables)\n"
        "  2. Arial font throughout (11pt body, 14pt headings, 18pt name)\n"
        "  3. Standard section headings (Personal Statement, Work Experience, etc.)\n"
        "  4. Contact details in body (not header/footer)\n"
        "  5. Solid round bullets\n"
        "  6. 2cm margins\n"
        "  7. Ends with 'References available on request'\n\n"
        "[bold]Then upload to Jobscan to verify parse success.[/bold]",
        title="Next Steps",
        border_style="yellow",
    ))


# ============================================================================
# Entry Point
# ============================================================================

if __name__ == "__main__":
    app()
