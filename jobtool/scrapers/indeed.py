"""
Indeed Playwright Scraper

Uses Playwright with a persistent browser context to scrape Indeed job listings.
Requires manual login first via `jobtool login indeed`.

Anti-detection measures:
- Persistent browser context (maintains cookies/session)
- Randomised delays between page loads (3-8 seconds)
- Realistic user agent
- Human-like scrolling behaviour
"""

import asyncio
import random
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode

from playwright.async_api import async_playwright, Page, BrowserContext

from jobtool.config import get_browser_contexts_dir
from jobtool.models import Job


class IndeedScraperError(Exception):
    """Raised when Indeed scraping fails."""
    pass


class IndeedLoginRequired(Exception):
    """Raised when Indeed login is required."""
    pass


# Indeed UK base URL
INDEED_BASE_URL = "https://uk.indeed.com"

# Realistic user agent
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def get_indeed_context_path() -> Path:
    """Get the path to Indeed's persistent browser context."""
    return get_browser_contexts_dir() / "indeed"


async def _random_delay(min_seconds: float = 3.0, max_seconds: float = 8.0) -> None:
    """Wait a random amount of time to appear human."""
    delay = random.uniform(min_seconds, max_seconds)
    await asyncio.sleep(delay)


async def _human_scroll(page: Page) -> None:
    """Simulate human-like scrolling."""
    # Scroll down in chunks
    for _ in range(random.randint(2, 4)):
        scroll_amount = random.randint(200, 500)
        await page.evaluate(f"window.scrollBy(0, {scroll_amount})")
        await asyncio.sleep(random.uniform(0.5, 1.5))


def _build_search_url(
    query: str,
    location: str,
    start: int = 0,
) -> str:
    """Build Indeed search URL."""
    params = {
        "q": query,
        "l": location,
        "start": start,
    }
    return f"{INDEED_BASE_URL}/jobs?" + urlencode(params)


async def _extract_job_from_card(page: Page, card) -> Job | None:
    """Extract job information from a job card element."""
    try:
        # Get job ID from data attribute or link
        job_id = await card.get_attribute("data-jk")
        if not job_id:
            # Try to extract from link
            link = await card.query_selector("a[data-jk]")
            if link:
                job_id = await link.get_attribute("data-jk")

        if not job_id:
            return None

        # Get title
        title_elem = await card.query_selector("h2.jobTitle span")
        if not title_elem:
            title_elem = await card.query_selector(".jobTitle")
        title = await title_elem.inner_text() if title_elem else "Unknown Title"

        # Get company
        company_elem = await card.query_selector("[data-testid='company-name']")
        if not company_elem:
            company_elem = await card.query_selector(".companyName")
        company = await company_elem.inner_text() if company_elem else "Unknown Company"

        # Get location
        location_elem = await card.query_selector("[data-testid='text-location']")
        if not location_elem:
            location_elem = await card.query_selector(".companyLocation")
        location = await location_elem.inner_text() if location_elem else ""

        # Get salary (if shown)
        salary_elem = await card.query_selector("[data-testid='attribute_snippet_testid']")
        salary_min = None
        salary_max = None
        if salary_elem:
            salary_text = await salary_elem.inner_text()
            # Try to parse salary (e.g., "£25,000 - £30,000 a year")
            salary_match = re.findall(r'£([\d,]+)', salary_text)
            if len(salary_match) >= 1:
                salary_min = int(salary_match[0].replace(",", ""))
            if len(salary_match) >= 2:
                salary_max = int(salary_match[1].replace(",", ""))

        # Build job URL
        job_url = f"{INDEED_BASE_URL}/viewjob?jk={job_id}"

        return Job(
            source="indeed",
            external_id=job_id,
            title=title.strip(),
            company=company.strip(),
            location=location.strip(),
            salary_min=salary_min,
            salary_max=salary_max,
            description="",  # Will be fetched separately
            url=job_url,
            scraped_at=datetime.now().isoformat(),
            status="pending",
        )

    except Exception as e:
        print(f"Error extracting job card: {e}")
        return None


async def _get_job_description(page: Page, job_url: str) -> str:
    """Navigate to job page and extract full description."""
    try:
        await page.goto(job_url, wait_until="domcontentloaded")
        await _random_delay(2, 4)

        # Try different selectors for job description
        selectors = [
            "#jobDescriptionText",
            "[data-testid='jobDescriptionText']",
            ".jobsearch-jobDescriptionText",
            ".job-description",
        ]

        for selector in selectors:
            desc_elem = await page.query_selector(selector)
            if desc_elem:
                return await desc_elem.inner_text()

        return ""

    except Exception as e:
        print(f"Error getting job description: {e}")
        return ""


async def scrape_indeed_async(
    query: str,
    location: str = "London",
    max_jobs: int = 50,
    fetch_descriptions: bool = True,
) -> list[Job]:
    """
    Scrape jobs from Indeed using Playwright.

    Args:
        query: Search keywords
        location: Job location
        max_jobs: Maximum jobs to return
        fetch_descriptions: Whether to fetch full descriptions (slower)

    Returns:
        List of Job objects
    """
    context_path = get_indeed_context_path()

    if not context_path.exists():
        raise IndeedLoginRequired(
            "Indeed browser context not found. Run 'jobtool login indeed' first."
        )

    jobs: list[Job] = []

    async with async_playwright() as p:
        # Launch browser with persistent context
        context = await p.chromium.launch_persistent_context(
            str(context_path),
            headless=True,
            user_agent=USER_AGENT,
            viewport={"width": 1920, "height": 1080},
        )

        page = await context.new_page()

        try:
            start = 0
            while len(jobs) < max_jobs:
                # Build search URL
                url = _build_search_url(query, location, start)

                # Navigate to search results
                await page.goto(url, wait_until="domcontentloaded")
                await _random_delay()
                await _human_scroll(page)

                # Find job cards
                cards = await page.query_selector_all(".job_seen_beacon, .jobsearch-ResultsList > li")

                if not cards:
                    break

                for card in cards:
                    if len(jobs) >= max_jobs:
                        break

                    job = await _extract_job_from_card(page, card)
                    if job:
                        jobs.append(job)

                # Check if there are more pages
                next_button = await page.query_selector("[data-testid='pagination-page-next']")
                if not next_button:
                    break

                start += 15  # Indeed shows 15 jobs per page
                await _random_delay()

            # Fetch full descriptions if requested
            if fetch_descriptions:
                for i, job in enumerate(jobs):
                    if i > 0:
                        await _random_delay(2, 5)
                    description = await _get_job_description(page, job.url)
                    job.description = description

        finally:
            await context.close()

    return jobs


def scrape_indeed(
    query: str,
    location: str = "London",
    max_jobs: int = 50,
    fetch_descriptions: bool = True,
) -> list[Job]:
    """
    Synchronous wrapper for Indeed scraper.

    Args:
        query: Search keywords
        location: Job location
        max_jobs: Maximum jobs to return
        fetch_descriptions: Whether to fetch full descriptions

    Returns:
        List of Job objects
    """
    return asyncio.run(scrape_indeed_async(
        query=query,
        location=location,
        max_jobs=max_jobs,
        fetch_descriptions=fetch_descriptions,
    ))


async def login_indeed_async() -> None:
    """
    Open Indeed in a browser for manual login.

    The user logs in manually, and the session is saved
    to a persistent browser context for future scraping.
    """
    context_path = get_indeed_context_path()
    context_path.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        # Launch browser in headed mode for login
        context = await p.chromium.launch_persistent_context(
            str(context_path),
            headless=False,  # Show browser for manual login
            user_agent=USER_AGENT,
            viewport={"width": 1280, "height": 800},
        )

        page = await context.new_page()

        # Navigate to Indeed login
        await page.goto(f"{INDEED_BASE_URL}/account/login")

        print("\n" + "=" * 60)
        print("Indeed Login")
        print("=" * 60)
        print("\nA browser window has opened.")
        print("Please log in to your Indeed account.")
        print("\nOnce logged in, close the browser window or press Ctrl+C.")
        print("Your session will be saved for future scraping.")
        print("=" * 60 + "\n")

        # Wait for user to close or navigate away from login
        try:
            # Wait indefinitely until browser is closed
            await page.wait_for_timeout(3600000)  # 1 hour max
        except Exception:
            pass

        await context.close()


def login_indeed() -> None:
    """Synchronous wrapper for Indeed login."""
    asyncio.run(login_indeed_async())
