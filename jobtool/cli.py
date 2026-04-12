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

    Examples:
        jobtool login indeed
        jobtool login linkedin
    """
    if source not in ("indeed", "linkedin"):
        print_error(f"Unknown source: {source}")
        print_info("Valid sources: indeed, linkedin")
        raise typer.Exit(1)

    console.print(Panel.fit(
        f"[bold blue]Login to {source.title()}[/bold blue]\n\n"
        "A browser window will open.\n"
        "Log in manually, then close the browser.",
        border_style="blue",
    ))

    try:
        if source == "indeed":
            from jobtool.scrapers.indeed import login_indeed
            login_indeed()
        elif source == "linkedin":
            from jobtool.scrapers.linkedin import login_linkedin
            login_linkedin()

        print_success(f"Session saved for {source.title()}")
        print_info(f"You can now run: jobtool scrape 'query' --sources {source}")

    except KeyboardInterrupt:
        print_info("Login cancelled")
    except Exception as e:
        print_error(f"Login failed: {e}")
        raise typer.Exit(1)


@app.command()
def scrape(
    query: str = typer.Argument(..., help="Search query (e.g., 'data entry')"),
    location: str = typer.Option("London", "--location", "-l", help="Job location"),
    sources: str = typer.Option("reed", "--sources", "-s", help="Comma-separated sources"),
    max_jobs: int = typer.Option(50, "--max", "-m", help="Max jobs per source"),
    salary_min: int = typer.Option(None, "--salary-min", help="Minimum salary filter"),
    posted: str = typer.Option(None, "--posted", help="Posted filter: today, week, month"),
    quick: bool = typer.Option(False, "--quick", "-q", help="Quick mode (shorter descriptions)"),
) -> None:
    """
    Scrape jobs from specified sources.

    Fetches job listings matching the query and saves them to the database.
    Currently supports: reed. Indeed and LinkedIn coming in Day 4.

    Examples:
        jobtool scrape "data entry" --location London --max 20
        jobtool scrape "software developer" -l Manchester -m 30
    """
    from jobtool.scrapers.reed import scrape_reed, ReedAPIError, ReedAPIKeyMissing
    from jobtool.db import insert_job

    source_list = [s.strip().lower() for s in sources.split(",")]

    console.print(Panel.fit(
        f"[bold blue]Scraping Jobs[/bold blue]\n"
        f"Query: {query}\n"
        f"Location: {location}\n"
        f"Sources: {', '.join(source_list)}\n"
        f"Max per source: {max_jobs}",
        border_style="blue",
    ))
    console.print()

    total_new = 0
    total_duplicate = 0

    for source in source_list:
        if source == "reed":
            try:
                print_info("Scraping Reed...")

                jobs = scrape_reed(
                    query=query,
                    location=location,
                    max_jobs=max_jobs,
                    salary_min=salary_min,
                    fetch_full_descriptions=not quick,
                )

                print_info(f"Found {len(jobs)} jobs, saving to database...")

                new_count = 0
                dup_count = 0
                for job in jobs:
                    result = insert_job(job)
                    if result:
                        new_count += 1
                    else:
                        dup_count += 1

                total_new += new_count
                total_duplicate += dup_count

                print_success(f"Reed: {new_count} new jobs, {dup_count} duplicates skipped")

            except ReedAPIKeyMissing as e:
                print_error(str(e))
                raise typer.Exit(1)
            except ReedAPIError as e:
                print_error(f"Reed API error: {e}")
            except Exception as e:
                print_error(f"Reed scraper failed: {e}")

        elif source == "indeed":
            try:
                from jobtool.scrapers.indeed import scrape_indeed, IndeedLoginRequired

                print_info("Scraping Indeed...")

                jobs = scrape_indeed(
                    query=query,
                    location=location,
                    max_jobs=max_jobs,
                    fetch_descriptions=not quick,
                )

                print_info(f"Found {len(jobs)} jobs, saving to database...")

                new_count = 0
                dup_count = 0
                for job in jobs:
                    result = insert_job(job)
                    if result:
                        new_count += 1
                    else:
                        dup_count += 1

                total_new += new_count
                total_duplicate += dup_count

                print_success(f"Indeed: {new_count} new jobs, {dup_count} duplicates skipped")

            except IndeedLoginRequired:
                print_warning("Indeed requires login. Run: jobtool login indeed")
            except Exception as e:
                print_error(f"Indeed scraper failed: {e}")

        elif source == "linkedin":
            try:
                from jobtool.scrapers.linkedin import scrape_linkedin, LinkedInLoginRequired

                print_info("Scraping LinkedIn (this may take a while)...")

                # LinkedIn has lower limits
                linkedin_max = min(max_jobs, 25)
                if max_jobs > 25:
                    print_warning(f"LinkedIn limited to {linkedin_max} jobs for safety")

                jobs = scrape_linkedin(
                    query=query,
                    location=location,
                    max_jobs=linkedin_max,
                    fetch_descriptions=not quick,
                )

                print_info(f"Found {len(jobs)} jobs, saving to database...")

                new_count = 0
                dup_count = 0
                for job in jobs:
                    result = insert_job(job)
                    if result:
                        new_count += 1
                    else:
                        dup_count += 1

                total_new += new_count
                total_duplicate += dup_count

                print_success(f"LinkedIn: {new_count} new jobs, {dup_count} duplicates skipped")

            except LinkedInLoginRequired:
                print_warning("LinkedIn requires login. Run: jobtool login linkedin")
            except Exception as e:
                print_error(f"LinkedIn scraper failed: {e}")

        else:
            print_error(f"Unknown source: {source}")

    # Summary
    console.print()
    console.print(Panel.fit(
        f"[bold green]Scraping Complete[/bold green]\n\n"
        f"New jobs added: {total_new}\n"
        f"Duplicates skipped: {total_duplicate}\n\n"
        f"Run [bold]jobtool list[/bold] to see jobs\n"
        f"Run [bold]jobtool generate <job_id>[/bold] to create CV",
        border_style="green",
    ))


@app.command("list")
def list_jobs(
    status: str = typer.Option(None, "--status", "-s", help="Filter by status"),
    source: str = typer.Option(None, "--source", help="Filter by source"),
    limit: int = typer.Option(20, "--limit", "-n", help="Max jobs to show"),
) -> None:
    """
    List jobs in the database.

    Shows a table of scraped jobs with their status.
    """
    from jobtool.db import get_all_jobs

    jobs = get_all_jobs(source=source, status=status, limit=limit)

    if not jobs:
        print_info("No jobs found. Run 'jobtool scrape' first.")
        return

    table = Table(title=f"Jobs ({len(jobs)} shown)", show_header=True)
    table.add_column("ID", style="cyan", width=5)
    table.add_column("Title", style="white", max_width=30)
    table.add_column("Company", style="yellow", max_width=20)
    table.add_column("Location", max_width=15)
    table.add_column("Salary", justify="right", max_width=15)
    table.add_column("Source", style="blue", width=8)
    table.add_column("Status", width=10)

    for job in jobs:
        # Format salary
        if job.salary_min and job.salary_max:
            salary = f"£{job.salary_min:,}-{job.salary_max:,}"
        elif job.salary_min:
            salary = f"£{job.salary_min:,}+"
        elif job.salary_max:
            salary = f"Up to £{job.salary_max:,}"
        else:
            salary = "-"

        # Status color
        status_style = {
            "pending": "[white]pending[/white]",
            "submitted": "[green]submitted[/green]",
            "skipped": "[dim]skipped[/dim]",
        }.get(job.status, job.status)

        table.add_row(
            str(job.id),
            job.title[:30],
            job.company[:20],
            (job.location or "-")[:15],
            salary,
            job.source,
            status_style,
        )

    console.print(table)


@app.command()
def generate(
    job_id: int = typer.Argument(..., help="Job ID to generate CV for"),
    output_dir: Path = typer.Option(
        None, "--output", "-o",
        help="Output directory (defaults to ~/.jobtool/applications/)",
    ),
) -> None:
    """
    Generate tailored CV and cover letter for a job.

    Uses Claude AI to create ATS-compliant documents tailored
    to the specific job description.

    Example:
        jobtool generate 42
    """
    from datetime import datetime

    from jobtool.db import get_job_by_id, insert_application, get_application_by_job_id
    from jobtool.ai.tailor import generate_application, AIGenerationError, APIKeyMissingError
    from jobtool.renderer.docx_renderer import render_cv, render_cover_letter, slugify
    from jobtool.renderer.pdf import docx_to_pdf, is_libreoffice_installed
    from jobtool.models import Application

    # Load job from database
    job = get_job_by_id(job_id)
    if not job:
        print_error(f"Job ID {job_id} not found. Run 'jobtool list' to see available jobs.")
        raise typer.Exit(1)

    # Check if already generated
    existing = get_application_by_job_id(job_id)
    if existing and existing.cv_path:
        print_warning(f"Application already exists for job {job_id}")
        print_info(f"CV: {existing.cv_path}")
        if existing.cover_letter_path:
            print_info(f"Cover Letter: {existing.cover_letter_path}")
        print_info("Use --force to regenerate (not yet implemented)")
        return

    # Load Master CV
    master_cv_path = get_master_cv_path()
    if not master_cv_path.exists():
        print_error(f"Master CV not found at {master_cv_path}")
        print_info("Run 'jobtool init' and set up your Master CV first.")
        raise typer.Exit(1)

    try:
        with open(master_cv_path, "r", encoding="utf-8") as f:
            master_cv = MasterCV.model_validate(json.load(f))
    except Exception as e:
        print_error(f"Failed to load Master CV: {e}")
        raise typer.Exit(1)

    # Determine output directory
    if output_dir is None:
        from jobtool.config import get_applications_dir
        company_slug = slugify(job.company)
        title_slug = slugify(job.title)
        date_str = datetime.now().strftime("%Y-%m-%d")
        output_dir = get_applications_dir() / f"{company_slug}-{title_slug}-{date_str}"

    output_dir.mkdir(parents=True, exist_ok=True)

    console.print(Panel.fit(
        f"[bold blue]Generating Application[/bold blue]\n\n"
        f"Job: {job.title}\n"
        f"Company: {job.company}\n"
        f"Location: {job.location or 'Not specified'}",
        border_style="blue",
    ))
    console.print()

    try:
        # Generate CV and cover letter
        print_info("Generating tailored CV with Claude...")
        tailored_cv, cover_letter = generate_application(master_cv, job)

        # Render CV
        print_info("Rendering CV to DOCX...")
        cv_path = render_cv(tailored_cv, output_dir, job.title)

        # Render cover letter
        print_info("Rendering cover letter...")
        cl_path = render_cover_letter(
            cover_letter,
            output_dir,
            master_cv.personalDetails.fullName,
            job.title,
        )

        # Convert to PDF if LibreOffice available
        cv_pdf_path = None
        cl_pdf_path = None

        if is_libreoffice_installed():
            print_info("Converting to PDF...")
            try:
                cv_pdf_path = docx_to_pdf(cv_path)
                cl_pdf_path = docx_to_pdf(cl_path)
            except Exception as e:
                print_warning(f"PDF conversion failed: {e}")

        print_info("Saving to database...")

        # Save application record
        application = Application(
            job_id=job_id,
            cv_path=str(cv_path),
            cv_pdf_path=str(cv_pdf_path) if cv_pdf_path else None,
            cover_letter_path=str(cl_path),
            cover_letter_pdf_path=str(cl_pdf_path) if cl_pdf_path else None,
            status="pending",
            created_at=datetime.now().isoformat(),
        )
        insert_application(application)

        # Success output
        console.print()
        print_success("Application generated!")
        console.print()

        console.print(Panel(
            f"[bold]CV:[/bold] {cv_path}\n"
            + (f"[bold]CV (PDF):[/bold] {cv_pdf_path}\n" if cv_pdf_path else "")
            + f"[bold]Cover Letter:[/bold] {cl_path}\n"
            + (f"[bold]Cover Letter (PDF):[/bold] {cl_pdf_path}\n" if cl_pdf_path else "")
            + f"\n[bold]Job URL:[/bold] {job.url}",
            title="Generated Files",
            border_style="green",
        ))

        console.print()
        print_info("Open the CV and cover letter to review before applying.")
        print_info(f"Job URL: {job.url}")

    except APIKeyMissingError as e:
        print_error(str(e))
        raise typer.Exit(1)
    except AIGenerationError as e:
        print_error(f"AI generation failed: {e}")
        raise typer.Exit(1)
    except Exception as e:
        print_error(f"Generation failed: {e}")
        raise typer.Exit(1)


@app.command()
def review(
    status: str = typer.Option("pending", "--status", "-s", help="Filter by status"),
) -> None:
    """
    Interactive review loop for pending jobs.

    Step through jobs one at a time, generating CVs and submitting applications.

    Keyboard shortcuts:
        o - Open job URL in browser
        s - Mark as submitted, go to next
        x - Skip this job, go to next
        n - Next job (no status change)
        p - Previous job
        e - Open CV file in viewer
        r - Regenerate CV and cover letter
        q - Quit review loop
        ? - Show help
    """
    from jobtool.review import run_review_loop
    run_review_loop(status=status)


@app.command()
def apply(
    url: str = typer.Argument(..., help="Job URL to apply to"),
) -> None:
    """
    Quick apply to a single job by URL.

    Creates a job entry from the URL, generates tailored CV and cover letter,
    then opens the application page in your browser.

    Supports Reed, Indeed, and LinkedIn job URLs.

    Example:
        jobtool apply "https://www.reed.co.uk/jobs/data-entry-clerk/12345"
    """
    import webbrowser
    import re
    from datetime import datetime

    from jobtool.db import insert_job, get_job_by_external_id, get_application_by_job_id, insert_application
    from jobtool.models import Job, Application

    console.print(Panel.fit(
        f"[bold blue]Quick Apply[/bold blue]\n\n"
        f"URL: {url[:60]}...",
        border_style="blue",
    ))
    console.print()

    # Determine source from URL
    if "reed.co.uk" in url:
        source = "reed"
        # Extract job ID from Reed URL
        match = re.search(r'/(\d+)\??', url)
        external_id = match.group(1) if match else None
    elif "indeed.com" in url or "indeed.co.uk" in url:
        source = "indeed"
        match = re.search(r'jk=([a-f0-9]+)', url)
        external_id = match.group(1) if match else None
    elif "linkedin.com" in url:
        source = "linkedin"
        match = re.search(r'/jobs/view/(\d+)', url)
        external_id = match.group(1) if match else None
    else:
        print_error("Unsupported job URL. Supported: Reed, Indeed, LinkedIn")
        raise typer.Exit(1)

    if not external_id:
        print_error("Could not extract job ID from URL")
        raise typer.Exit(1)

    # Check if job already exists
    existing_job = get_job_by_external_id(source, external_id)
    if existing_job:
        print_info(f"Job already in database (ID: {existing_job.id})")
        job = existing_job
    else:
        # Create minimal job entry
        print_info("Creating job entry...")
        job = Job(
            source=source,
            external_id=external_id,
            title="Manual Application",
            company="See job posting",
            location="",
            salary_min=None,
            salary_max=None,
            description="Job added via quick apply. Visit URL for details.",
            url=url,
            scraped_at=datetime.now().isoformat(),
            status="pending",
        )
        insert_job(job)
        # Get the inserted job with ID
        job = get_job_by_external_id(source, external_id)
        print_success(f"Job added (ID: {job.id})")

    # Check if application exists
    existing_app = get_application_by_job_id(job.id)
    if existing_app and existing_app.cv_path:
        print_info("Application already generated")
        print_info(f"CV: {existing_app.cv_path}")
    else:
        # Load Master CV
        master_cv_path = get_master_cv_path()
        if not master_cv_path.exists():
            print_warning("Master CV not found - skipping CV generation")
            print_info("Open the URL to apply manually")
        else:
            try:
                with open(master_cv_path, "r", encoding="utf-8") as f:
                    master_cv = MasterCV.model_validate(json.load(f))

                from jobtool.ai.tailor import generate_application, AIGenerationError
                from jobtool.renderer.docx_renderer import render_cv, render_cover_letter, slugify
                from jobtool.renderer.pdf import docx_to_pdf, is_libreoffice_installed

                # Determine output directory
                company_slug = slugify(job.company)
                title_slug = slugify(job.title)
                date_str = datetime.now().strftime("%Y-%m-%d")
                output_dir = get_applications_dir() / f"{company_slug}-{title_slug}-{date_str}"
                output_dir.mkdir(parents=True, exist_ok=True)

                print_info("Generating tailored CV...")
                tailored_cv, cover_letter = generate_application(master_cv, job)

                cv_path = render_cv(tailored_cv, output_dir, job.title)
                cl_path = render_cover_letter(
                    cover_letter,
                    output_dir,
                    master_cv.personalDetails.fullName,
                    job.title,
                )

                # PDF conversion
                cv_pdf_path = None
                cl_pdf_path = None
                if is_libreoffice_installed():
                    try:
                        cv_pdf_path = docx_to_pdf(cv_path)
                        cl_pdf_path = docx_to_pdf(cl_path)
                    except Exception:
                        pass

                application = Application(
                    job_id=job.id,
                    cv_path=str(cv_path),
                    cv_pdf_path=str(cv_pdf_path) if cv_pdf_path else None,
                    cover_letter_path=str(cl_path),
                    cover_letter_pdf_path=str(cl_pdf_path) if cl_pdf_path else None,
                    status="pending",
                    created_at=datetime.now().isoformat(),
                )
                insert_application(application)

                print_success("CV and cover letter generated!")
                print_info(f"CV: {cv_path}")

            except AIGenerationError as e:
                print_warning(f"CV generation failed: {e}")
            except Exception as e:
                print_warning(f"Error generating CV: {e}")

    # Open URL in browser
    print_info("Opening job URL in browser...")
    webbrowser.open(url)
    print_success("Done! Apply manually using your generated CV.")


@app.command()
def history(
    week: bool = typer.Option(False, "--week", help="Show only last 7 days"),
    month: bool = typer.Option(False, "--month", help="Show only last 30 days"),
    status: str = typer.Option(None, "--status", "-s", help="Filter by status"),
    limit: int = typer.Option(50, "--limit", "-n", help="Max records to show"),
) -> None:
    """
    Show application history.

    Lists past applications with dates, companies, and statuses.

    Examples:
        jobtool history
        jobtool history --week
        jobtool history --status submitted
    """
    from datetime import datetime, timedelta
    from jobtool.db import get_all_applications

    applications = get_all_applications(status=status, limit=limit)

    if not applications:
        print_info("No applications found.")
        print_info("Run 'jobtool review' or 'jobtool generate <job_id>' to create applications.")
        return

    # Filter by date if requested
    if week or month:
        now = datetime.now()
        if week:
            cutoff = now - timedelta(days=7)
        else:  # month
            cutoff = now - timedelta(days=30)

        filtered = []
        for app, job in applications:
            if app.created_at:
                try:
                    app_date = datetime.fromisoformat(app.created_at.replace("Z", "+00:00"))
                    if app_date.replace(tzinfo=None) >= cutoff:
                        filtered.append((app, job))
                except Exception:
                    filtered.append((app, job))  # Include if date parsing fails
            else:
                filtered.append((app, job))
        applications = filtered

    if not applications:
        time_range = "7 days" if week else "30 days"
        print_info(f"No applications in the last {time_range}.")
        return

    # Build table
    table = Table(title=f"Application History ({len(applications)} records)", show_header=True)
    table.add_column("ID", style="cyan", width=5)
    table.add_column("Date", width=12)
    table.add_column("Company", style="yellow", max_width=20)
    table.add_column("Title", style="white", max_width=25)
    table.add_column("Status", width=10)
    table.add_column("CV", width=6)

    for app, job in applications:
        # Format date
        if app.created_at:
            try:
                dt = datetime.fromisoformat(app.created_at.replace("Z", "+00:00"))
                date_str = dt.strftime("%Y-%m-%d")
            except Exception:
                date_str = app.created_at[:10] if len(app.created_at) >= 10 else "-"
        else:
            date_str = "-"

        # Status color
        status_style = {
            "pending": "[white]pending[/white]",
            "submitted": "[green]submitted[/green]",
            "rejected": "[red]rejected[/red]",
            "interview": "[cyan]interview[/cyan]",
        }.get(app.status, app.status)

        # CV indicator
        cv_indicator = "[green]Yes[/green]" if app.cv_path else "[dim]No[/dim]"

        table.add_row(
            str(app.id),
            date_str,
            (job.company if job else "Unknown")[:20],
            (job.title if job else "Unknown")[:25],
            status_style,
            cv_indicator,
        )

    console.print(table)

    # Summary stats
    console.print()
    total = len(applications)
    submitted = sum(1 for app, _ in applications if app.status == "submitted")
    pending = sum(1 for app, _ in applications if app.status == "pending")

    console.print(f"[bold]Summary:[/bold] {total} applications - "
                  f"[green]{submitted} submitted[/green], "
                  f"[white]{pending} pending[/white]")


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
