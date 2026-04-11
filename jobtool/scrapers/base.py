"""Base scraper protocol and utilities."""

from typing import Protocol

from jobtool.models import Job


class Scraper(Protocol):
    """Protocol that all scrapers must implement."""

    def scrape(
        self,
        query: str,
        location: str,
        max_jobs: int = 50,
    ) -> list[Job]:
        """
        Scrape jobs matching the query.

        Args:
            query: Search terms (e.g., "data entry")
            location: Job location (e.g., "London")
            max_jobs: Maximum number of jobs to return

        Returns:
            List of Job objects
        """
        ...
