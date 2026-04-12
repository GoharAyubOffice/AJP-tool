"""
Interactive Review Loop

Walks the user through pending jobs one at a time,
displaying job details, generating CVs, and tracking applications.

Keyboard Shortcuts:
    o - Open application URL in browser
    s - Mark as submitted, advance to next
    x - Skip this job, advance to next
    n - Next job (no status change)
    p - Previous job
    e - Open CV in default editor/viewer
    r - Regenerate CV and cover letter
    q - Quit review loop
    ? - Show help
"""

import json
import webbrowser
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt

from jobtool.config import get_master_cv_path, get_applications_dir
from jobtool.db import (
    get_jobs_by_status,
    get_job_by_id,
    update_job_status,
    get_application_by_job_id,
    insert_application,
    update_application_status,
)
from jobtool.models import Job, MasterCV, Application


console = Console(legacy_windows=True)


HELP_TEXT = """
[bold]Review Loop Keyboard Shortcuts[/bold]

  [cyan]o[/cyan] - Open job URL in browser
  [cyan]s[/cyan] - Mark as SUBMITTED, go to next job
  [cyan]x[/cyan] - SKIP this job, go to next
  [cyan]n[/cyan] - Next job (no status change)
  [cyan]p[/cyan] - Previous job
  [cyan]e[/cyan] - Open CV file in viewer
  [cyan]r[/cyan] - Regenerate CV and cover letter
  [cyan]q[/cyan] - Quit review loop
  [cyan]?[/cyan] - Show this help

Press any key to continue...
"""


def _open_file(filepath: str) -> None:
    """Open a file with the system's default application."""
    path = Path(filepath)
    if not path.exists():
        console.print(f"[red]File not found:[/red] {filepath}")
        return

    try:
        if sys.platform == "win32":
            subprocess.run(["start", "", str(path)], shell=True, check=True)
        elif sys.platform == "darwin":
            subprocess.run(["open", str(path)], check=True)
        else:
            subprocess.run(["xdg-open", str(path)], check=True)
    except Exception as e:
        console.print(f"[red]Failed to open file:[/red] {e}")


def _open_url(url: str) -> None:
    """Open a URL in the default browser."""
    try:
        webbrowser.open(url)
        console.print(f"[green]Opened:[/green] {url}")
    except Exception as e:
        console.print(f"[red]Failed to open URL:[/red] {e}")
        console.print(f"URL: {url}")


def _display_job(job: Job, index: int, total: int, application: Application | None) -> None:
    """Display job details in a Rich panel."""
    # Build salary string
    if job.salary_min and job.salary_max:
        salary = f"£{job.salary_min:,} - £{job.salary_max:,}"
    elif job.salary_min:
        salary = f"£{job.salary_min:,}+"
    elif job.salary_max:
        salary = f"Up to £{job.salary_max:,}"
    else:
        salary = "Not specified"

    # Status indicator
    status_color = {
        "pending": "yellow",
        "submitted": "green",
        "skipped": "dim",
    }.get(job.status, "white")

    # Build header
    header = f"[bold]{job.title}[/bold] at [cyan]{job.company}[/cyan]"

    # Build details
    details = f"""
[bold]Location:[/bold] {job.location or 'Not specified'}
[bold]Salary:[/bold] {salary}
[bold]Source:[/bold] {job.source}
[bold]Status:[/bold] [{status_color}]{job.status}[/{status_color}]
[bold]URL:[/bold] {job.url}
"""

    # Add application info if exists
    if application:
        details += f"""
[bold green]Application Generated:[/bold green]
  CV: {application.cv_path or 'Not generated'}
  Cover Letter: {application.cover_letter_path or 'Not generated'}
"""

    # Job description (truncated if too long)
    description = job.description or "No description available"
    if len(description) > 1500:
        description = description[:1500] + "...\n[dim](truncated)[/dim]"

    console.print(Panel(
        f"{header}\n{details}\n[bold]Description:[/bold]\n{description}",
        title=f"Job {index + 1} of {total} (ID: {job.id})",
        border_style="blue",
    ))


def _show_shortcuts() -> None:
    """Display shortcut reminder."""
    console.print(
        "[dim][o]pen URL  [s]ubmitted  [x]skip  [n]ext  [p]rev  "
        "[e]dit CV  [r]egenerate  [q]uit  [?]help[/dim]"
    )


def _get_key() -> str:
    """Get a single keypress from the user."""
    return Prompt.ask(
        "[bold]Action[/bold]",
        choices=["o", "s", "x", "n", "p", "e", "r", "q", "?"],
        default="n",
    )


def _generate_for_job(job: Job, master_cv: MasterCV) -> Application | None:
    """Generate CV and cover letter for a job."""
    from jobtool.ai.tailor import generate_application, AIGenerationError
    from jobtool.renderer.docx_renderer import render_cv, render_cover_letter, slugify
    from jobtool.renderer.pdf import docx_to_pdf, is_libreoffice_installed

    console.print("[blue]Generating CV and cover letter...[/blue]")

    try:
        # Determine output directory
        company_slug = slugify(job.company)
        title_slug = slugify(job.title)
        date_str = datetime.now().strftime("%Y-%m-%d")
        output_dir = get_applications_dir() / f"{company_slug}-{title_slug}-{date_str}"
        output_dir.mkdir(parents=True, exist_ok=True)

        # Generate with AI
        tailored_cv, cover_letter = generate_application(master_cv, job)

        # Render DOCX
        cv_path = render_cv(tailored_cv, output_dir, job.title)
        cl_path = render_cover_letter(
            cover_letter,
            output_dir,
            master_cv.personalDetails.fullName,
            job.title,
        )

        # Convert to PDF if possible
        cv_pdf_path = None
        cl_pdf_path = None
        if is_libreoffice_installed():
            try:
                cv_pdf_path = docx_to_pdf(cv_path)
                cl_pdf_path = docx_to_pdf(cl_path)
            except Exception:
                pass

        # Create application record
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

        console.print("[green]CV and cover letter generated![/green]")
        return application

    except AIGenerationError as e:
        console.print(f"[red]Generation failed:[/red] {e}")
        return None
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        return None


def run_review_loop(status: str = "pending") -> None:
    """
    Run the interactive review loop.

    Args:
        status: Filter jobs by status (default: pending)
    """
    # Load Master CV
    master_cv_path = get_master_cv_path()
    if not master_cv_path.exists():
        console.print("[red]Master CV not found.[/red] Run 'jobtool init' first.")
        return

    try:
        with open(master_cv_path, "r", encoding="utf-8") as f:
            master_cv = MasterCV.model_validate(json.load(f))
    except Exception as e:
        console.print(f"[red]Failed to load Master CV:[/red] {e}")
        return

    # Get jobs
    jobs = get_jobs_by_status(status=status)

    if not jobs:
        console.print(f"[yellow]No {status} jobs found.[/yellow]")
        console.print("Run 'jobtool scrape' to fetch new jobs.")
        return

    console.print(Panel.fit(
        f"[bold blue]Review Loop[/bold blue]\n\n"
        f"Found {len(jobs)} {status} jobs.\n"
        f"Press [bold]?[/bold] for help at any time.",
        border_style="blue",
    ))

    current_index = 0

    while True:
        # Clear screen and display current job
        console.clear()

        job = jobs[current_index]
        application = get_application_by_job_id(job.id)

        # Auto-generate if no application exists
        if not application and job.status == "pending":
            application = _generate_for_job(job, master_cv)

        _display_job(job, current_index, len(jobs), application)
        _show_shortcuts()

        # Get user action
        action = _get_key()

        if action == "q":
            console.print("[yellow]Exiting review loop.[/yellow]")
            break

        elif action == "?":
            console.print(Panel(HELP_TEXT, title="Help", border_style="cyan"))
            Prompt.ask("Press Enter to continue")

        elif action == "o":
            _open_url(job.url)
            Prompt.ask("Press Enter to continue")

        elif action == "e":
            if application and application.cv_path:
                _open_file(application.cv_path)
            else:
                console.print("[yellow]No CV generated yet.[/yellow]")
            Prompt.ask("Press Enter to continue")

        elif action == "s":
            # Mark as submitted
            update_job_status(job.id, "submitted")
            if application:
                update_application_status(
                    application.id,
                    "submitted",
                    submitted_at=datetime.now().isoformat(),
                )
            console.print(f"[green]Marked as submitted:[/green] {job.title}")

            # Move to next pending job
            jobs = get_jobs_by_status(status="pending")
            if not jobs:
                console.print("[green]All jobs reviewed![/green]")
                break
            current_index = 0

        elif action == "x":
            # Skip job
            update_job_status(job.id, "skipped")
            console.print(f"[dim]Skipped:[/dim] {job.title}")

            # Move to next pending job
            jobs = get_jobs_by_status(status="pending")
            if not jobs:
                console.print("[green]All jobs reviewed![/green]")
                break
            current_index = 0

        elif action == "n":
            # Next job
            if current_index < len(jobs) - 1:
                current_index += 1
            else:
                console.print("[yellow]Already at last job.[/yellow]")
                Prompt.ask("Press Enter to continue")

        elif action == "p":
            # Previous job
            if current_index > 0:
                current_index -= 1
            else:
                console.print("[yellow]Already at first job.[/yellow]")
                Prompt.ask("Press Enter to continue")

        elif action == "r":
            # Regenerate
            console.print("[blue]Regenerating...[/blue]")
            application = _generate_for_job(job, master_cv)
            Prompt.ask("Press Enter to continue")

    console.print("\n[bold]Review session complete.[/bold]")
