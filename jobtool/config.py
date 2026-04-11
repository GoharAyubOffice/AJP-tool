"""Configuration loading and path management."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env file from current directory or parent directories
load_dotenv()


def get_data_dir() -> Path:
    """Get the data directory path, expanding ~ to user home."""
    data_dir = os.getenv("DATA_DIR", "~/.jobtool")
    return Path(data_dir).expanduser()


def get_master_cv_path() -> Path:
    """Get the Master CV JSON file path."""
    master_cv_path = os.getenv("MASTER_CV_PATH", "~/.jobtool/master-cv.json")
    return Path(master_cv_path).expanduser()


def get_db_path() -> Path:
    """Get the SQLite database path."""
    return get_data_dir() / "jobtool.db"


def get_applications_dir() -> Path:
    """Get the applications output directory."""
    return get_data_dir() / "applications"


def get_browser_contexts_dir() -> Path:
    """Get the Playwright browser contexts directory."""
    return get_data_dir() / "browser-contexts"


def get_logs_dir() -> Path:
    """Get the logs directory."""
    return get_data_dir() / "logs"


def get_reed_api_key() -> str | None:
    """Get the Reed API key from environment."""
    return os.getenv("REED_API_KEY")


def get_anthropic_api_key() -> str | None:
    """Get the Anthropic API key from environment."""
    return os.getenv("ANTHROPIC_API_KEY")


def get_anthropic_model() -> str:
    """Get the Anthropic model to use."""
    return os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")


# Directory structure to create on init
INIT_DIRECTORIES = [
    get_data_dir,
    get_applications_dir,
    get_browser_contexts_dir,
    lambda: get_browser_contexts_dir() / "indeed",
    lambda: get_browser_contexts_dir() / "linkedin",
    get_logs_dir,
]
