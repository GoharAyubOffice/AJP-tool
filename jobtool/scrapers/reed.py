"""Reed API scraper - to be implemented Day 3."""

from jobtool.models import Job


def scrape_reed(
    query: str,
    location: str = "London",
    max_jobs: int = 50,
    salary_min: int | None = None,
    posted: str | None = None,
) -> list[Job]:
    """
    Scrape jobs from Reed API.

    TODO: Implement in Day 3
    """
    raise NotImplementedError("Reed scraper not yet implemented")
