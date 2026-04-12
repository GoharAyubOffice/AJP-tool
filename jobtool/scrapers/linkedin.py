"""
LinkedIn Playwright Scraper

Uses Playwright with a persistent browser context to scrape LinkedIn job listings.
Requires manual login first via `jobtool login linkedin`.

IMPORTANT: LinkedIn has aggressive anti-bot measures. This scraper uses:
- Persistent browser context (maintains cookies/fingerprint)
- Longer randomised delays (5-12 seconds)
- Human-like mouse movements
- Viewport jitter
- Realistic scrolling patterns
- Lower volume limits (max 50 per session recommended)
"""

import asyncio
import random
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode, quote

from playwright.async_api import async_playwright, Page, BrowserContext

from jobtool.config import get_browser_contexts_dir
from jobtool.models import Job


class LinkedInScraperError(Exception):
    """Raised when LinkedIn scraping fails."""
    pass


class LinkedInLoginRequired(Exception):
    """Raised when LinkedIn login is required."""
    pass


# LinkedIn base URL
LINKEDIN_BASE_URL = "https://www.linkedin.com"
LINKEDIN_JOBS_URL = f"{LINKEDIN_BASE_URL}/jobs/search"

# Realistic user agent
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def get_linkedin_context_path() -> Path:
    """Get the path to LinkedIn's persistent browser context."""
    return get_browser_contexts_dir() / "linkedin"


async def _random_delay(min_seconds: float = 5.0, max_seconds: float = 12.0) -> None:
    """Wait a random amount of time - longer for LinkedIn."""
    delay = random.uniform(min_seconds, max_seconds)
    await asyncio.sleep(delay)


async def _human_mouse_move(page: Page) -> None:
    """Simulate random mouse movements."""
    for _ in range(random.randint(2, 5)):
        x = random.randint(100, 1200)
        y = random.randint(100, 700)
        await page.mouse.move(x, y)
        await asyncio.sleep(random.uniform(0.1, 0.3))


async def _human_scroll(page: Page) -> None:
    """Simulate human-like scrolling with pauses."""
    for _ in range(random.randint(3, 6)):
        scroll_amount = random.randint(150, 400)
        await page.evaluate(f"window.scrollBy(0, {scroll_amount})")
        await asyncio.sleep(random.uniform(0.8, 2.0))

        # Occasionally scroll up a bit (humans do this)
        if random.random() < 0.2:
            up_amount = random.randint(50, 150)
            await page.evaluate(f"window.scrollBy(0, -{up_amount})")
            await asyncio.sleep(random.uniform(0.3, 0.8))


def _build_search_url(
    query: str,
    location: str,
    start: int = 0,
) -> str:
    """Build LinkedIn job search URL."""
    params = {
        "keywords": query,
        "location": location,
        "start": start,
        "f_TPR": "r86400",  # Posted in last 24 hours
    }
    return LINKEDIN_JOBS_URL + "?" + urlencode(params)


async def _extract_job_from_card(card) -> Job | None:
    """Extract job information from a LinkedIn job card."""
    try:
        # Get job ID from data attribute
        job_id = await card.get_attribute("data-job-id")
        if not job_id:
            # Try to extract from href
            link = await card.query_selector("a.job-card-list__title")
            if link:
                href = await link.get_attribute("href")
                if href:
                    match = re.search(r'/jobs/view/(\d+)', href)
                    if match:
                        job_id = match.group(1)

        if not job_id:
            return None

        # Get title
        title_elem = await card.query_selector(".job-card-list__title")
        if not title_elem:
            title_elem = await card.query_selector("a[data-control-name='job_card_title']")
        title = await title_elem.inner_text() if title_elem else "Unknown Title"

        # Get company
        company_elem = await card.query_selector(".job-card-container__company-name")
        if not company_elem:
            company_elem = await card.query_selector(".job-card-container__primary-description")
        company = await company_elem.inner_text() if company_elem else "Unknown Company"

        # Get location
        location_elem = await card.query_selector(".job-card-container__metadata-item")
        location = await location_elem.inner_text() if location_elem else ""

        # LinkedIn rarely shows salary in search results
        salary_min = None
        salary_max = None

        # Build job URL
        job_url = f"{LINKEDIN_BASE_URL}/jobs/view/{job_id}"

        return Job(
            source="linkedin",
            external_id=str(job_id),
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
        print(f"Error extracting LinkedIn job card: {e}")
        return None


async def _get_job_description(page: Page, job_url: str) -> str:
    """Navigate to job page and extract full description."""
    try:
        await _human_mouse_move(page)
        await page.goto(job_url, wait_until="domcontentloaded")
        await _random_delay(3, 6)
        await _human_scroll(page)

        # Try to expand "Show more" if present
        show_more = await page.query_selector("button.show-more-less-html__button")
        if show_more:
            await show_more.click()
            await asyncio.sleep(1)

        # Try different selectors for job description
        selectors = [
            ".show-more-less-html__markup",
            ".description__text",
            ".jobs-description__content",
            "[data-test-id='job-details']",
        ]

        for selector in selectors:
            desc_elem = await page.query_selector(selector)
            if desc_elem:
                return await desc_elem.inner_text()

        return ""

    except Exception as e:
        print(f"Error getting LinkedIn job description: {e}")
        return ""


async def scrape_linkedin_async(
    query: str,
    location: str = "London",
    max_jobs: int = 25,  # Lower default for LinkedIn
    fetch_descriptions: bool = True,
) -> list[Job]:
    """
    Scrape jobs from LinkedIn using Playwright.

    CAUTION: LinkedIn has aggressive anti-bot measures.
    Keep max_jobs low (25-50) and don't run too frequently.

    Args:
        query: Search keywords
        location: Job location
        max_jobs: Maximum jobs to return (recommended: 25-50)
        fetch_descriptions: Whether to fetch full descriptions

    Returns:
        List of Job objects
    """
    context_path = get_linkedin_context_path()

    if not context_path.exists():
        raise LinkedInLoginRequired(
            "LinkedIn browser context not found. Run 'jobtool login linkedin' first."
        )

    jobs: list[Job] = []

    async with async_playwright() as p:
        # Launch browser with persistent context
        # Add some randomness to viewport
        viewport_width = random.randint(1200, 1920)
        viewport_height = random.randint(800, 1080)

        context = await p.chromium.launch_persistent_context(
            str(context_path),
            headless=True,
            user_agent=USER_AGENT,
            viewport={"width": viewport_width, "height": viewport_height},
        )

        page = await context.new_page()

        try:
            start = 0
            while len(jobs) < max_jobs:
                # Random mouse movement before navigation
                await _human_mouse_move(page)

                # Build search URL
                url = _build_search_url(query, location, start)

                # Navigate to search results
                await page.goto(url, wait_until="domcontentloaded")
                await _random_delay()
                await _human_scroll(page)

                # Wait for job cards to load
                await page.wait_for_selector(
                    ".jobs-search-results__list-item, .job-card-container",
                    timeout=10000
                )

                # Find job cards
                cards = await page.query_selector_all(
                    ".jobs-search-results__list-item, .job-card-container"
                )

                if not cards:
                    break

                for card in cards:
                    if len(jobs) >= max_jobs:
                        break

                    job = await _extract_job_from_card(card)
                    if job and job.external_id not in [j.external_id for j in jobs]:
                        jobs.append(job)

                # LinkedIn shows 25 jobs per page
                start += 25

                # Check if we've reached the end
                if len(cards) < 25:
                    break

                await _random_delay(8, 15)  # Longer delay between pages

            # Fetch full descriptions if requested
            if fetch_descriptions:
                for i, job in enumerate(jobs):
                    if i > 0:
                        await _random_delay(5, 10)  # Longer delays for LinkedIn
                    description = await _get_job_description(page, job.url)
                    job.description = description

        finally:
            await context.close()

    return jobs


def scrape_linkedin(
    query: str,
    location: str = "London",
    max_jobs: int = 25,
    fetch_descriptions: bool = True,
) -> list[Job]:
    """
    Synchronous wrapper for LinkedIn scraper.

    Args:
        query: Search keywords
        location: Job location
        max_jobs: Maximum jobs to return
        fetch_descriptions: Whether to fetch full descriptions

    Returns:
        List of Job objects
    """
    return asyncio.run(scrape_linkedin_async(
        query=query,
        location=location,
        max_jobs=max_jobs,
        fetch_descriptions=fetch_descriptions,
    ))


async def login_linkedin_async() -> None:
    """
    Open LinkedIn in a browser for manual login.

    The user logs in manually, and the session is saved
    to a persistent browser context for future scraping.
    """
    context_path = get_linkedin_context_path()
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

        # Navigate to LinkedIn login
        await page.goto(f"{LINKEDIN_BASE_URL}/login")

        print("\n" + "=" * 60)
        print("LinkedIn Login")
        print("=" * 60)
        print("\nA browser window has opened.")
        print("Please log in to your LinkedIn account.")
        print("\nIMPORTANT: Use a secondary LinkedIn account if possible,")
        print("as scraping may risk account restrictions.")
        print("\nOnce logged in, close the browser window or press Ctrl+C.")
        print("Your session will be saved for future scraping.")
        print("=" * 60 + "\n")

        # Wait for user to close or navigate away from login
        try:
            await page.wait_for_timeout(3600000)  # 1 hour max
        except Exception:
            pass

        await context.close()


def login_linkedin() -> None:
    """Synchronous wrapper for LinkedIn login."""
    asyncio.run(login_linkedin_async())
