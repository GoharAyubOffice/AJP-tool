"""LinkedIn Playwright scraper - to be implemented Day 4."""

from jobtool.models import Job


async def scrape_linkedin(
    query: str,
    location: str = "London",
    max_jobs: int = 50,
) -> list[Job]:
    """
    Scrape jobs from LinkedIn using Playwright.

    TODO: Implement in Day 4
    """
    raise NotImplementedError("LinkedIn scraper not yet implemented")
