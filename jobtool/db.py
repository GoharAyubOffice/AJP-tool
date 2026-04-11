"""SQLite database schema and operations."""

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from jobtool.config import get_db_path
from jobtool.models import Job, Application


# ============================================================================
# Schema Definition
# ============================================================================

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    external_id TEXT NOT NULL,
    title TEXT NOT NULL,
    company TEXT NOT NULL,
    location TEXT,
    salary_min INTEGER,
    salary_max INTEGER,
    description TEXT NOT NULL,
    url TEXT NOT NULL,
    posted_date TEXT,
    scraped_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    UNIQUE(source, external_id)
);

CREATE TABLE IF NOT EXISTS applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL REFERENCES jobs(id),
    cv_path TEXT,
    cv_pdf_path TEXT,
    cover_letter_path TEXT,
    cover_letter_pdf_path TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    submitted_at TEXT,
    notes TEXT,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_jobs_source ON jobs(source);
CREATE INDEX IF NOT EXISTS idx_applications_job_id ON applications(job_id);
CREATE INDEX IF NOT EXISTS idx_applications_status ON applications(status);
"""


# ============================================================================
# Connection Management
# ============================================================================

def get_connection(db_path: Path | None = None) -> sqlite3.Connection:
    """Get a database connection with row factory enabled."""
    if db_path is None:
        db_path = get_db_path()
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def init_schema(db_path: Path | None = None) -> None:
    """Create the database schema if it doesn't exist."""
    conn = get_connection(db_path)
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


# ============================================================================
# Job Operations
# ============================================================================

def insert_job(job: Job, db_path: Path | None = None) -> int | None:
    """
    Insert a job into the database.

    Uses INSERT OR IGNORE to handle duplicates (by source + external_id).
    Returns the job ID if inserted, None if it was a duplicate.
    """
    conn = get_connection(db_path)
    try:
        cursor = conn.execute(
            """
            INSERT OR IGNORE INTO jobs
            (source, external_id, title, company, location, salary_min, salary_max,
             description, url, posted_date, scraped_at, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job.source,
                job.external_id,
                job.title,
                job.company,
                job.location,
                job.salary_min,
                job.salary_max,
                job.description,
                job.url,
                job.posted_date,
                job.scraped_at,
                job.status,
            ),
        )
        conn.commit()
        if cursor.rowcount > 0:
            return cursor.lastrowid
        return None
    finally:
        conn.close()


def get_job_by_id(job_id: int, db_path: Path | None = None) -> Job | None:
    """Get a single job by its ID."""
    conn = get_connection(db_path)
    try:
        cursor = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
        row = cursor.fetchone()
        if row:
            return Job(**dict(row))
        return None
    finally:
        conn.close()


def get_jobs_by_status(
    status: str = "pending",
    source: str | None = None,
    limit: int | None = None,
    db_path: Path | None = None,
) -> list[Job]:
    """Get jobs filtered by status and optionally source."""
    conn = get_connection(db_path)
    try:
        query = "SELECT * FROM jobs WHERE status = ?"
        params: list[Any] = [status]

        if source:
            query += " AND source = ?"
            params.append(source)

        query += " ORDER BY scraped_at DESC"

        if limit:
            query += " LIMIT ?"
            params.append(limit)

        cursor = conn.execute(query, params)
        return [Job(**dict(row)) for row in cursor.fetchall()]
    finally:
        conn.close()


def get_all_jobs(
    source: str | None = None,
    status: str | None = None,
    limit: int | None = None,
    db_path: Path | None = None,
) -> list[Job]:
    """Get all jobs with optional filters."""
    conn = get_connection(db_path)
    try:
        query = "SELECT * FROM jobs WHERE 1=1"
        params: list[Any] = []

        if source:
            query += " AND source = ?"
            params.append(source)

        if status:
            query += " AND status = ?"
            params.append(status)

        query += " ORDER BY scraped_at DESC"

        if limit:
            query += " LIMIT ?"
            params.append(limit)

        cursor = conn.execute(query, params)
        return [Job(**dict(row)) for row in cursor.fetchall()]
    finally:
        conn.close()


def update_job_status(job_id: int, status: str, db_path: Path | None = None) -> bool:
    """Update a job's status. Returns True if the job was found and updated."""
    conn = get_connection(db_path)
    try:
        cursor = conn.execute(
            "UPDATE jobs SET status = ? WHERE id = ?",
            (status, job_id),
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def count_jobs_by_status(db_path: Path | None = None) -> dict[str, int]:
    """Get counts of jobs grouped by status."""
    conn = get_connection(db_path)
    try:
        cursor = conn.execute(
            "SELECT status, COUNT(*) as count FROM jobs GROUP BY status"
        )
        return {row["status"]: row["count"] for row in cursor.fetchall()}
    finally:
        conn.close()


def count_jobs_by_source(db_path: Path | None = None) -> dict[str, int]:
    """Get counts of jobs grouped by source."""
    conn = get_connection(db_path)
    try:
        cursor = conn.execute(
            "SELECT source, COUNT(*) as count FROM jobs GROUP BY source"
        )
        return {row["source"]: row["count"] for row in cursor.fetchall()}
    finally:
        conn.close()


# ============================================================================
# Application Operations
# ============================================================================

def insert_application(application: Application, db_path: Path | None = None) -> int:
    """Insert an application into the database. Returns the application ID."""
    conn = get_connection(db_path)
    try:
        cursor = conn.execute(
            """
            INSERT INTO applications
            (job_id, cv_path, cv_pdf_path, cover_letter_path, cover_letter_pdf_path,
             status, submitted_at, notes, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                application.job_id,
                application.cv_path,
                application.cv_pdf_path,
                application.cover_letter_path,
                application.cover_letter_pdf_path,
                application.status,
                application.submitted_at,
                application.notes,
                application.created_at,
            ),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def get_application_by_job_id(job_id: int, db_path: Path | None = None) -> Application | None:
    """Get an application by its job ID."""
    conn = get_connection(db_path)
    try:
        cursor = conn.execute(
            "SELECT * FROM applications WHERE job_id = ?", (job_id,)
        )
        row = cursor.fetchone()
        if row:
            return Application(**dict(row))
        return None
    finally:
        conn.close()


def get_applications(
    status: str | None = None,
    limit: int | None = None,
    days: int | None = None,
    db_path: Path | None = None,
) -> list[Application]:
    """Get applications with optional filters."""
    conn = get_connection(db_path)
    try:
        query = "SELECT * FROM applications WHERE 1=1"
        params: list[Any] = []

        if status:
            query += " AND status = ?"
            params.append(status)

        if days:
            cutoff = datetime.now().isoformat()[:10]  # Just date part
            query += " AND created_at >= date(?, '-' || ? || ' days')"
            params.extend([cutoff, days])

        query += " ORDER BY created_at DESC"

        if limit:
            query += " LIMIT ?"
            params.append(limit)

        cursor = conn.execute(query, params)
        return [Application(**dict(row)) for row in cursor.fetchall()]
    finally:
        conn.close()


def update_application(
    application_id: int,
    cv_path: str | None = None,
    cv_pdf_path: str | None = None,
    cover_letter_path: str | None = None,
    cover_letter_pdf_path: str | None = None,
    status: str | None = None,
    submitted_at: str | None = None,
    notes: str | None = None,
    db_path: Path | None = None,
) -> bool:
    """Update an application's fields. Only non-None values are updated."""
    conn = get_connection(db_path)
    try:
        updates = []
        params = []

        if cv_path is not None:
            updates.append("cv_path = ?")
            params.append(cv_path)
        if cv_pdf_path is not None:
            updates.append("cv_pdf_path = ?")
            params.append(cv_pdf_path)
        if cover_letter_path is not None:
            updates.append("cover_letter_path = ?")
            params.append(cover_letter_path)
        if cover_letter_pdf_path is not None:
            updates.append("cover_letter_pdf_path = ?")
            params.append(cover_letter_pdf_path)
        if status is not None:
            updates.append("status = ?")
            params.append(status)
        if submitted_at is not None:
            updates.append("submitted_at = ?")
            params.append(submitted_at)
        if notes is not None:
            updates.append("notes = ?")
            params.append(notes)

        if not updates:
            return False

        params.append(application_id)
        query = f"UPDATE applications SET {', '.join(updates)} WHERE id = ?"

        cursor = conn.execute(query, params)
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def update_application_status(
    application_id: int,
    status: str,
    submitted_at: str | None = None,
    db_path: Path | None = None,
) -> bool:
    """Update an application's status and optionally submitted_at timestamp."""
    return update_application(
        application_id,
        status=status,
        submitted_at=submitted_at,
        db_path=db_path,
    )
