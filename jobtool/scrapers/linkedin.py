"""
LinkedIn Playwright Scraper

Uses Playwright with multiple methods to scrape LinkedIn job listings.
Supports manual login via browser or connecting to existing Chrome session.

Anti-detection methods:
- Enhanced stealth scripts to hide automation signals
- Firefox browser (less detected than Chromium)
- Critical Chrome args to block automation detection
- Option to connect to existing Chrome via remote debugging (bypasses all detection)

Login options (in order of effectiveness):
1. Connect to existing Chrome where you're already logged in
2. Use Firefox with stealth mode
3. Use Chromium with maximum stealth args
"""

import asyncio
import json
import os
import random
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode

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

# Realistic user agents
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]

# Critical Chrome args to hide automation
CHROME_AUTOMATION_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--disable-automation",
    "--no-first-run",
    "--no-service-autorun",
    "--password-store=basic",
    "--disable-default-apps",
    "--disable-extensions",
    "--disable-background-networking",
    "--disable-sync",
    "--disable-translate",
    "--metrics-recording-only",
    "--mute-audio",
    "--no-default-browser-check",
    "--no-pings",
    "--single-process",
    "--disable-gpu",
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--disable-setuid-sandbox",
    "--window-position=0,0",
    "--ignore-certificate-errors",
    "--ignore-certificate-errors-spki-list",
    "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
]


def get_linkedin_context_path() -> Path:
    """Get the path to LinkedIn's persistent browser context."""
    return get_browser_contexts_dir() / "linkedin"


async def _random_delay(min_seconds: float = 5.0, max_seconds: float = 12.0) -> None:
    """Wait a random amount of time."""
    delay = random.uniform(min_seconds, max_seconds)
    await asyncio.sleep(delay)


async def _human_mouse_move(page: Page) -> None:
    """Simulate human-like mouse movements."""
    for _ in range(random.randint(2, 4)):
        x = random.randint(100, 1200)
        y = random.randint(100, 700)
        await page.mouse.move(x, y)
        await asyncio.sleep(random.uniform(0.2, 0.5))


async def _human_scroll(page: Page) -> None:
    """Simulate human-like scrolling with pauses."""
    for _ in range(random.randint(2, 4)):
        scroll_amount = random.randint(150, 400)
        await page.evaluate(f"window.scrollBy(0, {scroll_amount})")
        await asyncio.sleep(random.uniform(0.5, 1.5))

        if random.random() < 0.2:
            up_amount = random.randint(50, 100)
            await page.evaluate(f"window.scrollBy(0, -{up_amount})")
            await asyncio.sleep(random.uniform(0.3, 0.6))


async def _add_stealth_scripts(page: Page) -> None:
    """Add comprehensive stealth scripts to hide automation signals."""
    await page.add_init_script("""
        // Remove webdriver property
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined,
            configurable: true
        });
        
        // Remove automation-specific properties
        delete window.cdc_adoQpoasnfa76pfcZLmcfl_Array;
        delete window.cdc_adoQpoasnfa76pfcZLmcfl_Promise;
        delete window.cdc_adoQpoasnfa76pfcZLmcfl_Symbol;
        
        // Spoof chrome object
        if (!window.chrome) window.chrome = {};
        if (!window.chrome.runtime) window.chrome.runtime = {};
        
        // Override permissions query
        const originalQuery = window.navigator.permissions.query;
        window.navigator.permissions.query = (parameters) => (
            parameters.name === 'notifications' ?
                Promise.resolve({ state: Notification.permission }) :
                originalQuery(parameters)
        );

        // Spoof plugins (real Chrome has plugins)
        Object.defineProperty(navigator, 'plugins', {
            get: () => [
                { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer' },
                { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai' },
                { name: 'Native Client', filename: 'internal-nacl-plugin' }
            ],
            configurable: true
        });

        // Spoof languages
        Object.defineProperty(navigator, 'languages', {
            get: () => ['en-GB', 'en-US', 'en'],
            configurable: true
        });

        // Remove automation-related event listeners
        const originalAddEventListener = window.addEventListener;
        window.addEventListener = function(type, listener, options) {
            if (type === 'beforeinput' && listener.toString().includes('automated')) {
                return;
            }
            return originalAddEventListener.call(this, type, listener, options);
        };
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
        "f_TPR": "r2592000",
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
        await _random_delay(3, 6)
        await _human_scroll(page)

        for selector in [
            "button.show-more-less-html__button",
            ".jf-profile-section__expand-button",
        ]:
            try:
                show_more = await page.query_selector(selector)
                if show_more:
                    await show_more.click()
                    await asyncio.sleep(0.5)
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


async def _connect_to_existing_chrome() -> tuple | None:
    """
    Try to connect to an existing Chrome browser running with remote debugging.

    To use this:
    1. Close all Chrome windows
    2. Open Run dialog (Win+R)
    3. Paste this path with your Chrome path:
       "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --profile-directory=Default
    4. Log into LinkedIn in that Chrome window (keep it open!)
    5. Run jobtool with --connect-existing flag

    Returns:
        Tuple of (context, page) if successful, None if failed
    """
    try:
        async with async_playwright() as p:
            # Try to connect to Chrome via CDP
            browser = await p.chromium.connect_over_cdp("http://localhost:9222")

            # Get ALL existing pages (tabs)
            existing_pages = browser.pages
            print(f"[INFO] Found {len(existing_pages)} existing tabs")

            # Look for LinkedIn in existing tabs
            linkedin_page = None
            for page in existing_pages:
                try:
                    url = page.url
                    if (
                        url
                        and "linkedin.com" in url.lower()
                        and "login" not in url.lower()
                    ):
                        linkedin_page = page
                        print(f"[SUCCESS] Found existing LinkedIn tab: {url[:50]}...")
                        break
                except Exception:
                    pass

            if not linkedin_page:
                print("[WARN] No logged-in LinkedIn tab found.")
                print("[INFO] Please open LinkedIn in Chrome and log in first.")
                await browser.close()
                return None

            # Get cookies from the LinkedIn page's context
            try:
                cookies = await linkedin_page.context.cookies()
                print(f"[INFO] Got {len(cookies)} cookies from LinkedIn")
            except Exception as e:
                print(f"[WARN] Could not get cookies: {e}")
                await browser.close()
                return None

            # Create a new context with those cookies
            new_context = await browser.new_context()
            await new_context.add_cookies(cookies)

            # Create a new page in this context
            new_page = await new_context.new_page()

            # Test that we can access LinkedIn with these cookies
            await new_page.goto(f"{LINKEDIN_BASE_URL}/feed", timeout=10000)
            await asyncio.sleep(1)

            if "login" in new_page.url.lower():
                print("[WARN] Cookies did not grant access - please log in again")
                await browser.close()
                return None

            print("[SUCCESS] Connected to existing LinkedIn session!")
            return (new_context, new_page)

    except Exception as e:
        print(f"[WARN] Could not connect to existing Chrome: {e}")
        return None


async def scrape_linkedin_async(
    query: str,
    location: str = "London",
    max_jobs: int = 25,
    fetch_descriptions: bool = True,
) -> list[Job]:
    """
    Scrape jobs from LinkedIn using Playwright.

    For best results, run `jobtool login linkedin` first.

    Args:
        query: Search keywords
        location: Job location
        max_jobs: Maximum jobs to return
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

        context = None
        page = None

        if use_existing_context:
            print("[INFO] Using saved LinkedIn session...")
            try:
                # Try Firefox first (less detected)
                context = await p.firefox.launch_persistent_context(
                    str(context_path),
                    headless=True,
                    user_agent=user_agent,
                    viewport={"width": viewport_width, "height": viewport_height},
                )
            except Exception:
                # Fall back to Chromium with stealth args
                try:
                    context = await p.chromium.launch_persistent_context(
                        str(context_path),
                        headless=True,
                        user_agent=user_agent,
                        viewport={"width": viewport_width, "height": viewport_height},
                        args=CHROME_AUTOMATION_ARGS,
                    )
                except Exception as e:
                    print(f"[WARN] Could not use saved context: {e}")
                    context = None
        else:
            print("[INFO] No saved LinkedIn session. Trying Firefox...")

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
                try:
                    context = await p.chromium.launch(
                        headless=True,
                        user_agent=user_agent,
                    )
                    context = await context.new_context(
                        user_agent=user_agent,
                        viewport={"width": viewport_width, "height": viewport_height},
                        locale="en-GB",
                        args=CHROME_AUTOMATION_ARGS,
                    )
                except Exception as e2:
                    print(f"[WARN] Chromium failed: {e2}")
                    context = None

        if context is None:
            print("[ERROR] Could not create browser context")
            return []

        page = await context.new_page()
        await _add_stealth_scripts(page)

        try:
            await page.goto(f"{LINKEDIN_BASE_URL}/feed", wait_until="domcontentloaded")
            await _random_delay(2, 4)

            if "login" in page.url.lower():
                print("[WARN] Not logged in to LinkedIn. Results will be limited.")
                print("[INFO] Run 'jobtool login linkedin' for full access.")

            start = 0
            while len(jobs) < max_jobs:
                await _human_mouse_move(page)
                url = _build_search_url(query, location, start)
                await page.goto(url, wait_until="domcontentloaded")
                await _random_delay(3, 7)
                await _human_scroll(page)

                try:
                    await page.wait_for_selector(
                        ".jobs-search-results__list-item, .job-card-container, .base-search-card",
                        timeout=10000,
                    )
                except Exception:
                    break

                cards = await page.query_selector_all(
                    ".jobs-search-results__list-item, .job-card-container, .base-search-card"
                )

                if not cards:
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

                await _random_delay(6, 12)

            if fetch_descriptions and jobs:
                print(f"[INFO] Fetching descriptions for {len(jobs)} jobs...")
                for i, job in enumerate(jobs):
                    if i > 0:
                        await _random_delay(3, 6)
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
    """Synchronous wrapper for LinkedIn scraper."""
    return asyncio.run(
        scrape_linkedin_async(
            query=query,
            location=location,
            max_jobs=max_jobs,
            fetch_descriptions=fetch_descriptions,
        )
    )


async def login_linkedin_async(use_existing: bool = False) -> None:
    """
    Open LinkedIn in a browser for manual login.

    The session is saved to a persistent browser context for future scraping.

    Args:
        use_existing: If True, try to connect to existing Chrome with remote debugging
                      instead of launching a new browser
    """
    context_path = get_linkedin_context_path()
    context_path.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        context = None
        page = None
        connected_to_existing = False

        if use_existing:
            # Try to connect to existing Chrome
            print("[INFO] Trying to connect to existing Chrome...")
            print(
                "[INFO] Make sure Chrome is running with --remote-debugging-port=9222"
            )
            result = await _connect_to_existing_chrome()
            if result:
                context, page = result
                connected_to_existing = True
            else:
                print("[ERROR] Could not connect to Chrome with remote debugging.")
                print(
                    "[ERROR] Make sure Chrome is open with: --remote-debugging-port=9222"
                )
                print("[ERROR] OR remove --connect-existing to use automated browser")
                return

        if context is None:
            # Launch Firefox for login (less detected)
            print("[INFO] Launching Firefox browser for login...")
            try:
                context = await p.firefox.launch_persistent_context(
                    str(context_path),
                    headless=False,
                    user_agent=random.choice(USER_AGENTS),
                    viewport={"width": 1280, "height": 800},
                    firefox_user_prefs={
                        "media.navigator.streams.fake": True,
                        "media.navigator.enabled": True,
                        "browser.private.browsing.autostart": False,
                    },
                )
            except Exception as e:
                print(f"[WARN] Firefox failed: {e}")
                print("[INFO] Trying Chromium...")
                # Fall back to Chromium with stealth args
                try:
                    context = await p.chromium.launch_persistent_context(
                        str(context_path),
                        headless=False,
                        user_agent=random.choice(USER_AGENTS),
                        viewport={"width": 1280, "height": 800},
                        args=CHROME_AUTOMATION_ARGS,
                    )
                except Exception as e2:
                    print(f"[ERROR] Chromium also failed: {e2}")
                    print(
                        "[ERROR] Please try running Chrome manually with remote debugging."
                    )
                    return

            page = await context.new_page()
            await _add_stealth_scripts(page)
            await page.goto(f"{LINKEDIN_BASE_URL}/login")

        if connected_to_existing:
            print("\n" + "=" * 60)
            print("LinkedIn Session Connected")
            print("=" * 60)
            print("\n[OK] Successfully connected to your existing Chrome session!")
            print("[OK] Your logged-in LinkedIn session will be used for scraping.")
            print("\nYou can now run: jobtool scrape 'data entry' --sources linkedin")
            print("=" * 60 + "\n")
        else:
            print("\n" + "=" * 60)
            print("LinkedIn Login")
            print("=" * 60)
            print("\nA browser window has opened.")
            print("Please log in to your LinkedIn account.")
            print("\nIf login shows 'Browser not secure':")
            print("  1. Press Ctrl+C to cancel")
            print("  2. Open Run dialog (Win+R)")
            print("  3. Paste this command:")
            print(
                '     "C:\Program Files\Google\Chrome\Application\chrome.exe" --remote-debugging-port=9222 --profile-directory=Default'
            )
            print("  4. Press Enter - Chrome will open")
            print("  5. Log into LinkedIn manually in that Chrome")
            print("  6. Then run: jobtool login linkedin --connect-existing")
            print("\nClose the browser window when done.")
            print("=" * 60 + "\n")

            try:
                await page.wait_for_timeout(3600000)
            except Exception:
                pass

        # Save session
        try:
            storage = await context.storage_state()
            (context_path / "storage_state.json").write_text(json.dumps(storage))
            print("[INFO] Session saved!")
        except Exception as e:
            print(f"[WARN] Could not save session: {e}")

        await context.close()


def login_linkedin(use_existing: bool = False) -> None:
    """Synchronous wrapper for LinkedIn login."""
    asyncio.run(login_linkedin_async(use_existing=use_existing))
