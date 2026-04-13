"""
LinkedIn Playwright Scraper

Uses Playwright with a persistent browser context to scrape LinkedIn job listings.
Requires manual login first via `jobtool login linkedin`.

IMPORTANT: LinkedIn has VERY aggressive anti-bot measures. This scraper uses:
- Firefox browser (less detected than Chromium)
- Stealth mode to hide automation signals
- Longer randomised delays (8-15 seconds)
- Human-like mouse movements and scrolling
- Viewport jitter and locale spoofing
- Lower volume limits (max 25 per session)

For best results: Run `jobtool login linkedin` once to save your session.
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

# Realistic user agents (rotating to avoid fingerprinting)
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
]


def get_linkedin_context_path() -> Path:
    """Get the path to LinkedIn's persistent browser context."""
    return get_browser_contexts_dir() / "linkedin"


async def _random_delay(min_seconds: float = 8.0, max_seconds: float = 15.0) -> None:
    """Wait a random amount of time - longer for LinkedIn."""
    delay = random.uniform(min_seconds, max_seconds)
    await asyncio.sleep(delay)


async def _human_mouse_move(page: Page) -> None:
    """Simulate human-like mouse movements with bezier curves."""
    for _ in range(random.randint(3, 6)):
        x = random.randint(100, 1200)
        y = random.randint(100, 700)
        await page.mouse.move(x, y)
        await asyncio.sleep(random.uniform(0.2, 0.5))


async def _human_scroll(page: Page) -> None:
    """Simulate human-like scrolling with pauses and occasional back-scroll."""
    for _ in range(random.randint(3, 6)):
        scroll_amount = random.randint(200, 500)
        await page.evaluate(f"window.scrollBy(0, {scroll_amount})")
        await asyncio.sleep(random.uniform(1.0, 2.0))

        if random.random() < 0.25:
            up_amount = random.randint(50, 150)
            await page.evaluate(f"window.scrollBy(0, -{up_amount})")
            await asyncio.sleep(random.uniform(0.5, 1.0))


async def _add_stealth_scripts(page: Page) -> None:
    """Add stealth scripts to hide automation signals."""
    await page.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined,
            configurable: true
        });
        delete window.cdc_adoQpoasnfa76pfcZLmcfl_Array;
        delete window.cdc_adoQpoasnfa76pfcZLmcfl_Promise;
        delete window.cdc_adoQpoasnfa76pfcZLmcfl_Symbol;
        if (window.chrome) {
            window.chrome.runtime = undefined;
        }
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) => (
            parameters.name === 'notifications' ?
                Promise.resolve({ state: Notification.permission }) :
                originalQuery(parameters)
        );
    """)


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
        "f_TPR": "r2592000",  # Posted in last 30 days
    }
    return LINKEDIN_JOBS_URL + "?" + urlencode(params)


async def _extract_job_from_card(card) -> Job | None:
    """Extract job information from a LinkedIn job card."""
    try:
        job_id = await card.get_attribute("data-job-id")
        if not job_id:
            link = await card.query_selector(
                "a.job-card-list__title, a[data-control-name='job_card_title']"
            )
            if link:
                href = await link.get_attribute("href")
                if href:
                    match = re.search(r"/jobs/view/(\d+)", href)
                    if match:
                        job_id = match.group(1)

        if not job_id:
            return None

        title = "Unknown Title"
        for selector in [
            ".job-card-list__title",
            "a[data-control-name='job_card_title']",
            ".job-card-container__link",
        ]:
            title_elem = await card.query_selector(selector)
            if title_elem:
                title = await title_elem.inner_text()
                break

        company = "Unknown Company"
        for selector in [
            ".job-card-container__company-name",
            ".job-card-container__primary-description",
            ".base-search-card__subtitle",
        ]:
            company_elem = await card.query_selector(selector)
            if company_elem:
                company = await company_elem.inner_text()
                break

        location = ""
        for selector in [
            ".job-card-container__metadata-item",
            ".base-search-card__metadata",
        ]:
            location_elem = await card.query_selector(selector)
            if location_elem:
                location = await location_elem.inner_text()
                break

        salary_min = None
        salary_max = None
        job_url = f"{LINKEDIN_BASE_URL}/jobs/view/{job_id}"

        return Job(
            source="linkedin",
            external_id=str(job_id),
            title=title.strip(),
            company=company.strip(),
            location=location.strip(),
            salary_min=salary_min,
            salary_max=salary_max,
            description="",
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
        await _random_delay(5, 10)
        await _human_scroll(page)

        for selector in [
            "button.show-more-less-html__button",
            ".jf-profile-section__expand-button",
        ]:
            try:
                show_more = await page.query_selector(selector)
                if show_more:
                    await show_more.click()
                    await asyncio.sleep(1)
            except Exception:
                pass

        selectors = [
            ".show-more-less-html__markup",
            ".description__text",
            ".jobs-description__content",
            "[data-test-id='job-details']",
            ".mb4",
        ]

        for selector in selectors:
            desc_elem = await page.query_selector(selector)
            if desc_elem:
                text = await desc_elem.inner_text()
                if len(text) > 50:
                    return text

        return ""

    except Exception as e:
        print(f"Error getting LinkedIn job description: {e}")
        return ""


async def scrape_linkedin_async(
    query: str,
    location: str = "London",
    max_jobs: int = 25,
    fetch_descriptions: bool = True,
) -> list[Job]:
    """
    Scrape jobs from LinkedIn using Playwright.

    LinkedIn has VERY aggressive anti-bot detection. For best results:
    1. Run `jobtool login linkedin` first to save your session
    2. Firefox browser is used as it's less detected than Chromium
    3. Results without login may be very limited (0-5 jobs)

    Args:
        query: Search keywords
        location: Job location
        max_jobs: Maximum jobs to return (recommended: 25)
        fetch_descriptions: Whether to fetch full descriptions

    Returns:
        List of Job objects
    """
    context_path = get_linkedin_context_path()
    use_existing_context = context_path.exists()

    jobs: list[Job] = []
    user_agent = random.choice(USER_AGENTS)

    async with async_playwright() as p:
        viewport_width = random.randint(1200, 1920)
        viewport_height = random.randint(800, 1080)

        if use_existing_context:
            print("[INFO] Using saved LinkedIn session...")
            try:
                context = await p.firefox.launch_persistent_context(
                    str(context_path),
                    headless=True,
                    user_agent=user_agent,
                    viewport={"width": viewport_width, "height": viewport_height},
                )
            except Exception:
                print("[INFO] Firefox context not available, trying Chromium...")
                context = await p.chromium.launch_persistent_context(
                    str(context_path),
                    headless=True,
                    user_agent=user_agent,
                    viewport={"width": viewport_width, "height": viewport_height},
                    args=["--disable-blink-features=AutomationControlled"],
                )
        else:
            print("[INFO] No saved LinkedIn session found.")
            print("[INFO] LinkedIn without login has very limited results.")
            print("[INFO] Run 'jobtool login linkedin' for full access.")

            try:
                browser = await p.firefox.launch(
                    headless=True,
                    user_agent=user_agent,
                )
                context = await browser.new_context(
                    user_agent=user_agent,
                    viewport={"width": viewport_width, "height": viewport_height},
                    locale="en-GB",
                    extra_http_headers={
                        "Accept-Language": "en-GB,en;q=0.9",
                    },
                )
            except Exception as e:
                print(f"[WARN] Firefox failed: {e}")
                context = await p.chromium.launch(
                    headless=True,
                    user_agent=user_agent,
                )
                context = await context.new_context(
                    user_agent=user_agent,
                    viewport={"width": viewport_width, "height": viewport_height},
                    locale="en-GB",
                )

        page = await context.new_page()
        await _add_stealth_scripts(page)

        try:
            await page.goto(f"{LINKEDIN_BASE_URL}/feed", wait_until="domcontentloaded")
            await _random_delay(3, 5)

            if "login" in page.url.lower():
                print("[WARN] Not logged in to LinkedIn. Results will be limited.")

            start = 0
            while len(jobs) < max_jobs:
                await _human_mouse_move(page)
                url = _build_search_url(query, location, start)
                await page.goto(url, wait_until="domcontentloaded")
                await _random_delay(5, 10)
                await _human_scroll(page)

                try:
                    await page.wait_for_selector(
                        ".jobs-search-results__list-item, .job-card-container, .base-search-card",
                        timeout=15000,
                    )
                except Exception:
                    print("[WARN] No job cards found on page.")
                    break

                cards = await page.query_selector_all(
                    ".jobs-search-results__list-item, .job-card-container, .base-search-card"
                )

                if not cards:
                    print("[WARN] Empty page received.")
                    break

                for card in cards:
                    if len(jobs) >= max_jobs:
                        break

                    job = await _extract_job_from_card(card)
                    if job and job.external_id not in [j.external_id for j in jobs]:
                        jobs.append(job)

                start += 25

                if len(cards) < 25:
                    break

                await _random_delay(10, 20)

            if fetch_descriptions and jobs:
                print(f"[INFO] Fetching descriptions for {len(jobs)} jobs...")
                for i, job in enumerate(jobs):
                    if i > 0:
                        await _random_delay(5, 10)
                    description = await _get_job_description(page, job.url)
                    job.description = description

        except Exception as e:
            print(f"[ERROR] LinkedIn scraping error: {e}")
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
    """
    return asyncio.run(
        scrape_linkedin_async(
            query=query,
            location=location,
            max_jobs=max_jobs,
            fetch_descriptions=fetch_descriptions,
        )
    )


async def login_linkedin_async() -> None:
    """
    Open LinkedIn in a browser for manual login.

    The user logs in manually, and the session is saved
    to a persistent browser context for future scraping.

    NOTE: LinkedIn has VERY aggressive anti-bot detection.
    Login may be blocked. If it fails, results will be limited.
    """
    context_path = get_linkedin_context_path()
    context_path.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        # Use Firefox for login (less detected)
        try:
            context = await p.firefox.launch_persistent_context(
                str(context_path),
                headless=False,
                user_agent=random.choice(USER_AGENTS),
                viewport={"width": 1280, "height": 800},
            )
        except Exception:
            # Fall back to Chromium
            context = await p.chromium.launch_persistent_context(
                str(context_path),
                headless=False,
                user_agent=random.choice(USER_AGENTS),
                viewport={"width": 1280, "height": 800},
            )

        page = await context.new_page()
        await page.goto(f"{LINKEDIN_BASE_URL}/login")

        print("\n" + "=" * 60)
        print("LinkedIn Login")
        print("=" * 60)
        print("\nA browser window has opened.")
        print("Please log in to your LinkedIn account.")
        print("\nIf login is blocked:")
        print("  1. Open Chrome/Brave directly")
        print("  2. Log in at https://www.linkedin.com")
        print("  3. Export cookies to ~/.jobtool/browser-contexts/linkedin/")
        print("\nClose the browser window when done.")
        print("=" * 60 + "\n")

        try:
            await page.wait_for_timeout(3600000)
        except Exception:
            pass

        await context.close()


def login_linkedin() -> None:
    """Synchronous wrapper for LinkedIn login."""
    asyncio.run(login_linkedin_async())
