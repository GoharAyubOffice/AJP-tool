"""
Interactive terminal menu for JobAutoApply.

Provides a user-friendly menu-driven interface for all job application tasks.
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

import questionary
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import print as rprint

from jobtool.config import (
    get_data_dir,
    get_master_cv_path,
    get_applications_dir,
    get_browser_contexts_dir,
)
from jobtool.db import (
    init_schema,
    get_all_jobs,
    get_job_by_id,
    insert_job,
    insert_application,
    get_all_applications,
    get_application_by_job_id,
)
from jobtool.models import MasterCV, Job, Application
from jobtool.scrapers.reed import scrape_reed, ReedAPIError, ReedAPIKeyMissing
from jobtool.ai.tailor import (
    generate_application,
    AIGenerationError,
    APIKeyMissingError,
)
from jobtool.renderer.docx_renderer import render_cv, render_cover_letter, slugify
from jobtool.renderer.pdf import docx_to_pdf, is_libreoffice_installed

console = Console()


def clear_screen():
    """Clear the terminal screen."""
    os.system("cls" if sys.platform == "win32" else "clear")


def print_banner():
    """Print the application banner."""
    banner = """
╔══════════════════════════════════════════════════════════╗
║              JOBTOOL - Interactive Job Manager          ║
╚══════════════════════════════════════════════════════════╝
"""
    rprint("[bold blue]" + banner + "[/bold blue]")


def print_success(msg: str):
    """Print success message."""
    console.print(f"[green]✓[/green] {msg}")


def print_error(msg: str):
    """Print error message."""
    console.print(f"[red]✗[/red] {msg}")


def print_info(msg: str):
    """Print info message."""
    console.print(f"[cyan]ℹ[/cyan] {msg}")


def print_warning(msg: str):
    """Print warning message."""
    console.print(f"[yellow]⚠[/yellow] {msg}")


def confirm(prompt: str) -> bool:
    """Ask for confirmation."""
    response = questionary.confirm(prompt).ask()
    return response


def select_choice(title: str, choices: list) -> str:
    """Ask user to select from a list of choices."""
    return questionary.select(title, choices=choices).ask()


def ask_text(prompt: str, default: str = "") -> str:
    """Ask user for text input."""
    if default:
        return questionary.text(prompt, default=default).ask()
    return questionary.text(prompt).ask()


def load_master_cv() -> Optional[MasterCV]:
    """Load and return the Master CV."""
    cv_path = get_master_cv_path()
    if not cv_path.exists():
        return None
    try:
        with open(cv_path, "r", encoding="utf-8") as f:
            return MasterCV.model_validate(json.load(f))
    except Exception:
        return None


def save_state(key: str, value):
    """Save state to ~/.jobtool/.state.json."""
    state_file = get_data_dir() / ".state.json"
    state = {}
    if state_file.exists():
        try:
            with open(state_file, "r") as f:
                state = json.load(f)
        except Exception:
            pass
    state[key] = value
    with open(state_file, "w") as f:
        json.dump(state, f)


def load_state(key: str, default=None):
    """Load state from ~/.jobtool/.state.json."""
    state_file = get_data_dir() / ".state.json"
    if not state_file.exists():
        return default
    try:
        with open(state_file, "r") as f:
            state = json.load(f)
            return state.get(key, default)
    except Exception:
        return default


# ============================================================================
# Setup Functions
# ============================================================================


def setup_menu():
    """Setup sub-menu."""
    clear_screen()
    print_banner()
    rprint("\n[bold yellow]SETUP MENU[/bold yellow]\n")

    choices = [
        "Initialize Database",
        "Edit Master CV",
        "Validate Master CV",
        "Check API Keys",
        "Login to Indeed",
        "Login to LinkedIn",
        "Back to Main Menu",
    ]

    choice = select_choice("What would you like to do?", choices)

    if choice == "Initialize Database":
        init_database()
    elif choice == "Edit Master CV":
        edit_master_cv()
    elif choice == "Validate Master CV":
        validate_master_cv()
    elif choice == "Check API Keys":
        check_api_keys()
    elif choice == "Login to Indeed":
        login_indeed()
    elif choice == "Login to LinkedIn":
        login_linkedin()


def init_database():
    """Initialize the database."""
    clear_screen()
    print_banner()
    rprint("\n[bold yellow]INITIALIZING DATABASE[/bold yellow]\n")

    try:
        init_schema()
        from jobtool.config import INIT_DIRECTORIES

        for get_dir in INIT_DIRECTORIES:
            dir_path = get_dir()
            dir_path.mkdir(parents=True, exist_ok=True)
        print_success("Database initialized successfully!")
    except Exception as e:
        print_error(f"Failed to initialize: {e}")

    input("\nPress Enter to continue...")


def edit_master_cv():
    """Edit the Master CV."""
    cv_path = get_master_cv_path()
    if not cv_path.exists():
        print_warning(
            "Master CV not found. Please run 'jobtool master-cv edit' after creating it."
        )
        input("\nPress Enter to continue...")
        return

    import subprocess

    editor = os.environ.get("EDITOR", "notepad" if sys.platform == "win32" else "nano")
    subprocess.run([editor, str(cv_path)])
    print_success("Master CV opened in editor.")


def validate_master_cv():
    """Validate the Master CV."""
    cv_path = get_master_cv_path()
    if not cv_path.exists():
        print_error("Master CV not found.")
        input("\nPress Enter to continue...")
        return

    try:
        with open(cv_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        cv = MasterCV.model_validate(data)
        print_success("Master CV is valid!")
    except json.JSONDecodeError as e:
        print_error(f"Invalid JSON: {e}")
    except Exception as e:
        print_error(f"Validation failed: {e}")

    input("\nPress Enter to continue...")


def check_api_keys():
    """Check if API keys are configured."""
    from dotenv import load_dotenv

    load_dotenv()

    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "")
    reed_key = os.getenv("REED_API_KEY", "")

    clear_screen()
    print_banner()
    rprint("\n[bold yellow]API KEYS STATUS[/bold yellow]\n")

    if anthropic_key:
        masked = (
            anthropic_key[:8] + "..." + anthropic_key[-4:]
            if len(anthropic_key) > 12
            else "***"
        )
        print_success(f"ANTHROPIC_API_KEY: {masked}")
    else:
        print_error("ANTHROPIC_API_KEY: Not set")

    if reed_key:
        masked = reed_key[:8] + "..." if len(reed_key) > 8 else "***"
        print_success(f"REED_API_KEY: {masked}")
    else:
        print_warning("REED_API_KEY: Not set (Reed scraping will use mock data)")

    input("\nPress Enter to continue...")


def login_indeed():
    """Login to Indeed via browser."""
    clear_screen()
    print_banner()
    rprint("\n[bold yellow]LOGIN TO INDEED[/bold yellow]\n")

    print_info("A browser window will open.")
    print_info("Please log in to your Indeed account.")
    print_info("Close the browser when done.\n")

    try:
        from jobtool.scrapers.indeed import login_indeed

        login_indeed()
        print_success("Indeed login complete!")
    except Exception as e:
        print_error(f"Login failed: {e}")

    input("\nPress Enter to continue...")


def login_linkedin():
    """Login to LinkedIn via browser."""
    clear_screen()
    print_banner()
    rprint("\n[bold yellow]LOGIN TO LINKEDIN[/bold yellow]\n")

    print_info("Choose login method:")
    choices = [
        "Connect to existing Chrome (recommended)",
        "Use automated browser",
    ]
    choice = select_choice("", choices)

    if choice == "Connect to existing Chrome (recommended)":
        print_info("\nMake sure Chrome is open with remote debugging.")
        print_info("Run this in PowerShell first:")
        print_info('  $env:DEBUG_PROFILE = "$env:TEMP\\chrome-jobtool-debug"')
        print_info(
            '  Start-Process -FilePath "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" -ArgumentList "--remote-debugging-port=9222","--user-data-dir=$env:DEBUG_PROFILE"'
        )
        print_info("\nThen log into LinkedIn in that Chrome window.\n")

        if confirm("Is Chrome open with LinkedIn logged in?"):
            try:
                from jobtool.scrapers.linkedin import login_linkedin

                login_linkedin(use_existing=True)
                print_success("LinkedIn login complete!")
            except Exception as e:
                print_error(f"Login failed: {e}")
    else:
        try:
            from jobtool.scrapers.linkedin import login_linkedin

            login_linkedin()
            print_success("LinkedIn login complete!")
        except Exception as e:
            print_error(f"Login failed: {e}")

    input("\nPress Enter to continue...")


# ============================================================================
# Scrape Jobs Functions
# ============================================================================


def scrape_jobs_menu():
    """Scrape jobs sub-menu."""
    clear_screen()
    print_banner()
    rprint("\n[bold yellow]SCRAPE JOBS[/bold yellow]\n")

    # Get search parameters
    query = ask_text("Search query", load_state("last_query", "data entry"))
    location = ask_text("Location", load_state("last_location", "London"))

    rprint("\n[bold]Select sources:[/bold]")
    sources = []

    if questionary.confirm("Scrape Reed?").ask():
        sources.append("reed")
    if questionary.confirm("Scrape Indeed?").ask():
        sources.append("indeed")
    if questionary.confirm("Scrape LinkedIn?").ask():
        sources.append("linkedin")

    if not sources:
        print_warning("No sources selected!")
        input("\nPress Enter to continue...")
        return

    max_jobs_str = ask_text("Max jobs per source", "20")
    try:
        max_jobs = int(max_jobs_str)
    except ValueError:
        max_jobs = 20

    # Save for next time
    save_state("last_query", query)
    save_state("last_location", location)

    # Scrape jobs
    clear_screen()
    print_banner()
    rprint(f"\n[bold yellow]SCRAPING {query} in {location}[/bold yellow]\n")

    total_new = 0
    total_dups = 0

    for source in sources:
        print_info(f"Scraping {source}...")

        try:
            if source == "reed":
                jobs = scrape_reed(
                    query=query,
                    location=location,
                    max_jobs=max_jobs,
                    fetch_full_descriptions=True,
                )
            elif source == "indeed":
                from jobtool.scrapers.indeed import scrape_indeed

                jobs = scrape_indeed(
                    query=query,
                    location=location,
                    max_jobs=max_jobs,
                    fetch_descriptions=True,
                )
            elif source == "linkedin":
                from jobtool.scrapers.linkedin import scrape_linkedin

                jobs = scrape_linkedin(
                    query=query,
                    location=location,
                    max_jobs=max_jobs,
                    fetch_descriptions=True,
                )

            new_count = 0
            dup_count = 0
            for job in jobs:
                result = insert_job(job)
                if result:
                    new_count += 1
                else:
                    dup_count += 1

            total_new += new_count
            total_dups += dup_count
            print_success(f"{source}: {new_count} new, {dup_count} duplicates")

        except Exception as e:
            print_error(f"{source}: {e}")

    rprint(f"\n[bold green]DONE![/bold green]")
    rprint(f"Total new jobs: {total_new}")
    rprint(f"Duplicates skipped: {total_dups}")

    input("\nPress Enter to continue...")


# ============================================================================
# List Jobs Functions
# ============================================================================


def list_jobs_menu():
    """List jobs sub-menu."""
    clear_screen()
    print_banner()
    rprint("\n[bold yellow]LIST JOBS[/bold yellow]\n")

    # Get filters
    choices = ["All", "Pending", "Submitted", "Skipped"]
    status_filter = select_choice("Filter by status", choices)
    status = None if status_filter == "All" else status_filter.lower()

    choices = ["All", "Reed", "Indeed", "LinkedIn"]
    source_filter = select_choice("Filter by source", choices)
    source = None if source_filter == "All" else source_filter.lower()

    limit_str = ask_text("Max jobs to show", "30")
    try:
        limit = int(limit_str)
    except ValueError:
        limit = 30

    # Fetch jobs
    jobs = get_all_jobs(source=source, status=status, limit=limit)

    clear_screen()
    print_banner()

    if not jobs:
        print_warning("No jobs found.")
        input("\nPress Enter to continue...")
        return

    # Display table
    table = Table(title=f"Jobs ({len(jobs)} shown)", show_header=True)
    table.add_column("ID", style="cyan", width=5)
    table.add_column("Title", max_width=25)
    table.add_column("Company", max_width=20)
    table.add_column("Source", width=8)
    table.add_column("Status", width=10)

    for job in jobs:
        status_style = {
            "pending": "[white]pending[/white]",
            "submitted": "[green]submitted[/green]",
            "skipped": "[dim]skipped[/dim]",
        }.get(job.status, job.status)

        table.add_row(
            str(job.id),
            job.title[:25],
            job.company[:20],
            job.source,
            status_style,
        )

    console.print(table)

    # Ask to select a job
    if questionary.confirm("\nGenerate CV for a job?").ask():
        job_id = ask_text("Enter job ID")
        try:
            generate_cv_for_job(int(job_id))
        except ValueError:
            print_error("Invalid job ID")

    input("\nPress Enter to continue...")


# ============================================================================
# Generate CV Functions
# ============================================================================


def generate_cv_for_job(job_id: int):
    """Generate CV for a specific job."""
    job = get_job_by_id(job_id)
    if not job:
        print_error(f"Job {job_id} not found")
        return

    master_cv = load_master_cv()
    if not master_cv:
        print_error("Master CV not found. Please set up your Master CV first.")
        return

    # Check if already generated
    existing = get_application_by_job_id(job_id)
    if (
        existing
        and existing.cv_path
        and questionary.confirm(
            f"CV already exists for job {job_id}. Regenerate?"
        ).ask()
        is False
    ):
        return

    clear_screen()
    print_banner()
    rprint(f"\n[bold yellow]GENERATING CV for[/bold yellow]")
    rprint(f"Job: {job.title}")
    rprint(f"Company: {job.company}\n")

    try:
        # Generate CV and cover letter
        print_info("Generating tailored CV with AI...")
        tailored_cv, cover_letter = generate_application(master_cv, job)

        # Determine output directory
        company_slug = slugify(job.company)
        title_slug = slugify(job.title)
        date_str = datetime.now().strftime("%Y-%m-%d")
        output_dir = get_applications_dir() / f"{company_slug}-{title_slug}-{date_str}"
        output_dir.mkdir(parents=True, exist_ok=True)

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

        # PDF conversion
        cv_pdf_path = None
        cl_pdf_path = None
        if is_libreoffice_installed():
            print_info("Converting to PDF...")
            try:
                cv_pdf_path = docx_to_pdf(cv_path)
                cl_pdf_path = docx_to_pdf(cl_path)
            except Exception as e:
                print_warning(f"PDF conversion failed: {e}")

        # Save to database
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

        print_success("CV and cover letter generated!")
        rprint(f"\n[green]CV:[/green] {cv_path}")
        rprint(f"[green]Cover Letter:[/green] {cl_path}")
        if cv_pdf_path:
            rprint(f"[green]CV PDF:[/green] {cv_pdf_path}")

    except APIKeyMissingError as e:
        print_error(str(e))
    except AIGenerationError as e:
        print_error(f"AI generation failed: {e}")
    except Exception as e:
        print_error(f"Generation failed: {e}")


def generate_cv_menu():
    """Generate CV sub-menu."""
    clear_screen()
    print_banner()
    rprint("\n[bold yellow]GENERATE CV[/bold yellow]\n")

    # Show pending jobs
    jobs = get_all_jobs(status="pending", limit=20)

    if not jobs:
        print_warning("No pending jobs found.")
        input("\nPress Enter to continue...")
        return

    table = Table(title="Pending Jobs", show_header=True)
    table.add_column("ID", style="cyan", width=5)
    table.add_column("Title", max_width=30)
    table.add_column("Company", max_width=20)
    table.add_column("Source", width=8)

    for job in jobs:
        table.add_row(
            str(job.id),
            job.title[:30],
            job.company[:20],
            job.source,
        )

    console.print(table)

    job_id_str = ask_text("\nEnter job ID to generate CV (or 'cancel' to go back)")
    if job_id_str.lower() == "cancel":
        return

    try:
        job_id = int(job_id_str)
        generate_cv_for_job(job_id)
    except ValueError:
        print_error("Invalid job ID")

    input("\nPress Enter to continue...")


# ============================================================================
# Review & Apply Functions
# ============================================================================


def review_apply_menu():
    """Review and apply sub-menu."""
    clear_screen()
    print_banner()
    rprint("\n[bold yellow]REVIEW & APPLY JOBS[/bold yellow]\n")

    jobs = get_all_jobs(status="pending", limit=50)

    if not jobs:
        print_warning("No pending jobs found. Scrape some jobs first!")
        input("\nPress Enter to continue...")
        return

    current_index = 0

    while True:
        clear_screen()
        print_banner()

        if current_index >= len(jobs):
            print_info("No more pending jobs!")
            break

        job = jobs[current_index]
        application = get_application_by_job_id(job.id)

        rprint(f"\n[bold cyan]Job {current_index + 1} of {len(jobs)}[/bold cyan]\n")
        rprint(f"[bold]Title:[/bold] {job.title}")
        rprint(f"[bold]Company:[/bold] {job.company}")
        rprint(f"[bold]Location:[/bold] {job.location or 'N/A'}")
        rprint(f"[bold]Source:[/bold] {job.source}")
        rprint(f"[bold]URL:[/bold] {job.url}")
        rprint(
            f"[bold]CV Status:[/bold] {'Generated' if application and application.cv_path else 'Not generated'}"
        )

        choices = []
        if not application or not application.cv_path:
            choices.append("Generate CV & Cover Letter")
        else:
            choices.append("Open CV Folder")
        choices.append("Open Job URL in Browser")
        choices.append("Mark as Submitted")
        choices.append("Skip Job")
        choices.append("Next Job")
        choices.append("Previous Job")
        choices.append("Back to Main Menu")

        action = select_choice("What to do?", choices)

        if action == "Generate CV & Cover Letter":
            generate_cv_for_job(job.id)
            # Refresh application status
            application = get_application_by_job_id(job.id)

        elif action == "Open CV Folder":
            if application and application.cv_path:
                import subprocess

                folder = str(Path(application.cv_path).parent)
                subprocess.run(["explorer", folder])
            else:
                print_warning("No CV generated yet")

        elif action == "Open Job URL in Browser":
            import webbrowser

            webbrowser.open(job.url)

        elif action == "Mark as Submitted":
            if application:
                from jobtool.db import update_application_status

                update_application_status(application.id, "submitted")
                print_success("Marked as submitted!")
            else:
                print_warning("Generate CV first before marking as submitted")

        elif action == "Skip Job":
            if application:
                from jobtool.db import update_application_status

                update_application_status(application.id, "skipped")
                print_success("Skipped!")
            # Move to next job
            jobs.pop(current_index)

        elif action == "Next Job":
            if current_index < len(jobs) - 1:
                current_index += 1
            else:
                print_info("Already at last job")

        elif action == "Previous Job":
            if current_index > 0:
                current_index -= 1
            else:
                print_info("Already at first job")

        elif action == "Back to Main Menu":
            break

    input("\nPress Enter to continue...")


# ============================================================================
# History Functions
# ============================================================================


def history_menu():
    """Show application history."""
    clear_screen()
    print_banner()
    rprint("\n[bold yellow]APPLICATION HISTORY[/bold yellow]\n")

    applications = get_all_applications(limit=50)

    if not applications:
        print_warning("No applications found.")
        input("\nPress Enter to continue...")
        return

    # Filter options
    choices = ["All", "Pending", "Submitted", "Rejected", "Interview"]
    status_filter = select_choice("Filter by status", choices)

    filtered = []
    for app, job in applications:
        if status_filter == "All" or app.status.lower() == status_filter.lower():
            filtered.append((app, job))

    if not filtered:
        print_warning(f"No {status_filter.lower()} applications found.")
        input("\nPress Enter to continue...")
        return

    # Display table
    table = Table(title=f"Applications ({len(filtered)} shown)", show_header=True)
    table.add_column("ID", style="cyan", width=4)
    table.add_column("Date", width=12)
    table.add_column("Company", max_width=20)
    table.add_column("Title", max_width=25)
    table.add_column("Status", width=10)
    table.add_column("CV", width=4)

    for app, job in filtered:
        if app.created_at:
            try:
                dt = datetime.fromisoformat(app.created_at.replace("Z", "+00:00"))
                date_str = dt.strftime("%Y-%m-%d")
            except Exception:
                date_str = "-"
        else:
            date_str = "-"

        status_style = {
            "pending": "[white]pending[/white]",
            "submitted": "[green]submitted[/green]",
            "rejected": "[red]rejected[/red]",
            "interview": "[cyan]interview[/cyan]",
        }.get(app.status, app.status)

        cv_indicator = "[green]✓[/green]" if app.cv_path else "[dim]✗[/dim]"

        table.add_row(
            str(app.id),
            date_str,
            (job.company if job else "Unknown")[:20],
            (job.title if job else "Unknown")[:25],
            status_style,
            cv_indicator,
        )

    console.print(table)

    # Summary
    total = len(filtered)
    submitted = sum(1 for app, _ in filtered if app.status == "submitted")
    pending = sum(1 for app, _ in filtered if app.status == "pending")

    rprint(
        f"\n[bold]Summary:[/bold] {total} applications - {submitted} submitted, {pending} pending"
    )

    input("\nPress Enter to continue...")


# ============================================================================
# Help Functions
# ============================================================================


def help_menu():
    """Show help information."""
    clear_screen()
    print_banner()

    help_text = """
[bold yellow]JOBTOOL HELP[/bold yellow]

[bold cyan]QUICK START:[/bold cyan]
1. [bold]Setup[/bold] → Configure Master CV and API keys
2. [bold]Scrape Jobs[/bold] → Find jobs from job boards
3. [bold]Generate CV[/bold] → Create tailored CV for a job
4. [bold]Review & Apply[/bold] → Review jobs and apply

[bold cyan]LINKEDIN SCRAPING:[/bold cyan]
1. Open Chrome with remote debugging:
   $env:DEBUG_PROFILE = "$env:TEMP\\chrome-jobtool-debug"
   Start-Process -FilePath "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe" -ArgumentList "--remote-debugging-port=9222","--user-data-dir=$env:DEBUG_PROFILE"
2. Log into LinkedIn in that Chrome
3. Use this tool to scrape

[bold cyan]KEYBOARD SHORTCUTS (in Review & Apply):[/bold cyan]
• o - Open job URL in browser
• s - Mark as submitted
• x - Skip this job
• n - Next job
• p - Previous job
• q - Quit to menu

[bold cyan]FOR MORE INFO:[/bold cyan]
See INSTRUCTIONS.md in the project folder
"""

    console.print(Panel(help_text, title="Help", border_style="blue"))

    input("\nPress Enter to continue...")


# ============================================================================
# Main Menu
# ============================================================================


def main_menu():
    """Main interactive menu."""
    while True:
        clear_screen()
        print_banner()

        rprint("\n[bold]What would you like to do?[/bold]\n")

        choices = [
            "🔍  Scrape Jobs",
            "📋  List Jobs",
            "📄  Generate CV",
            "✅  Review & Apply",
            "📊  Application History",
            "⚙️   Setup",
            "❓  Help",
            "🚪  Exit",
        ]

        choice = select_choice("", choices)

        if choice == "🔍  Scrape Jobs":
            scrape_jobs_menu()
        elif choice == "📋  List Jobs":
            list_jobs_menu()
        elif choice == "📄  Generate CV":
            generate_cv_menu()
        elif choice == "✅  Review & Apply":
            review_apply_menu()
        elif choice == "📊  Application History":
            history_menu()
        elif choice == "⚙️   Setup":
            setup_menu()
        elif choice == "❓  Help":
            help_menu()
        elif choice == "🚪  Exit":
            clear_screen()
            rprint("\n[bold blue]Thank you for using JobTool![/bold blue]\n")
            break


def run_interactive():
    """Entry point for the interactive menu."""
    try:
        main_menu()
    except KeyboardInterrupt:
        rprint("\n\n[bold yellow]Interrupted. Goodbye![/bold yellow]\n")
    except Exception as e:
        print_error(f"An error occurred: {e}")
        import traceback

        traceback.print_exc()
        input("\nPress Enter to exit...")


if __name__ == "__main__":
    run_interactive()
