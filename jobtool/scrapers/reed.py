"""
Reed API Scraper

Uses the Reed Jobseeker API to fetch job listings.
API Documentation: https://www.reed.co.uk/developers/jobseeker

The Reed API uses HTTP Basic Auth with your API key as the username
and an empty password.
"""

import base64
from datetime import datetime
from typing import Any

import httpx

from jobtool.config import get_reed_api_key
from jobtool.models import Job


# Reed API endpoints
REED_API_BASE = "https://www.reed.co.uk/api/1.0"
REED_SEARCH_ENDPOINT = f"{REED_API_BASE}/search"
REED_DETAILS_ENDPOINT = f"{REED_API_BASE}/jobs"


class ReedAPIError(Exception):
    """Raised when Reed API returns an error."""
    pass


class ReedAPIKeyMissing(Exception):
    """Raised when Reed API key is not configured."""
    pass


def _get_auth_header() -> dict[str, str]:
    """
    Get the Authorization header for Reed API.

    Reed uses HTTP Basic Auth with API key as username and empty password.
    """
    api_key = get_reed_api_key()
    if not api_key:
        raise ReedAPIKeyMissing(
            "REED_API_KEY not found in .env file.\n"
            "Get your API key from: https://www.reed.co.uk/developers/jobseeker"
        )

    # Basic auth: base64(username:password) where password is empty
    credentials = base64.b64encode(f"{api_key}:".encode()).decode()
    return {"Authorization": f"Basic {credentials}"}


def _parse_job(data: dict[str, Any], full_description: str | None = None) -> Job:
    """
    Parse a Reed API job response into our Job model.

    Args:
        data: Job data from Reed API
        full_description: Full job description (from details endpoint)
    """
    # Parse salary
    salary_min = None
    salary_max = None

    if data.get("minimumSalary"):
        try:
            salary_min = int(float(data["minimumSalary"]))
        except (ValueError, TypeError):
            pass

    if data.get("maximumSalary"):
        try:
            salary_max = int(float(data["maximumSalary"]))
        except (ValueError, TypeError):
            pass

    # Use full description if available, otherwise use the short description
    description = full_description or data.get("jobDescription", "")

    # Build the job URL
    job_url = data.get("jobUrl", f"https://www.reed.co.uk/jobs/{data['jobId']}")

    return Job(
        source="reed",
        external_id=str(data["jobId"]),
        title=data.get("jobTitle", "Unknown Title"),
        company=data.get("employerName", "Unknown Company"),
        location=data.get("locationName", ""),
        salary_min=salary_min,
        salary_max=salary_max,
        description=description,
        url=job_url,
        posted_date=data.get("date", ""),
        scraped_at=datetime.now().isoformat(),
        status="pending",
    )


def get_job_details(job_id: int | str) -> dict[str, Any]:
    """
    Fetch full job details from Reed API.

    The search endpoint only returns a short description.
    This endpoint returns the full job description.
    """
    headers = _get_auth_header()

    with httpx.Client(timeout=30.0) as client:
        response = client.get(
            f"{REED_DETAILS_ENDPOINT}/{job_id}",
            headers=headers,
        )

        if response.status_code == 401:
            raise ReedAPIError("Invalid Reed API key")
        elif response.status_code == 404:
            raise ReedAPIError(f"Job {job_id} not found")
        elif response.status_code != 200:
            raise ReedAPIError(f"Reed API error: {response.status_code} - {response.text}")

        return response.json()


def scrape_reed(
    query: str,
    location: str = "London",
    max_jobs: int = 50,
    salary_min: int | None = None,
    salary_max: int | None = None,
    posted_days: int | None = None,
    full_time: bool | None = None,
    part_time: bool | None = None,
    contract: bool | None = None,
    permanent: bool | None = None,
    fetch_full_descriptions: bool = True,
) -> list[Job]:
    """
    Scrape jobs from Reed API.

    Args:
        query: Search keywords (e.g., "data entry")
        location: Location to search (e.g., "London")
        max_jobs: Maximum number of jobs to return
        salary_min: Minimum salary filter
        salary_max: Maximum salary filter
        posted_days: Only jobs posted within this many days
        full_time: Include full-time jobs
        part_time: Include part-time jobs
        contract: Include contract jobs
        permanent: Include permanent jobs
        fetch_full_descriptions: If True, fetch full descriptions (slower but better)

    Returns:
        List of Job objects

    Raises:
        ReedAPIKeyMissing: If API key not configured
        ReedAPIError: If API returns an error
    """
    headers = _get_auth_header()

    # Build query parameters
    params: dict[str, Any] = {
        "keywords": query,
        "locationName": location,
        "resultsToTake": min(max_jobs, 100),  # Reed API max is 100 per request
    }

    if salary_min:
        params["minimumSalary"] = salary_min
    if salary_max:
        params["maximumSalary"] = salary_max
    if posted_days:
        params["postedByRecruiter"] = True  # This enables date filtering
    if full_time is not None:
        params["fullTime"] = full_time
    if part_time is not None:
        params["partTime"] = part_time
    if contract is not None:
        params["contract"] = contract
    if permanent is not None:
        params["permanent"] = permanent

    jobs: list[Job] = []
    results_to_skip = 0

    with httpx.Client(timeout=30.0) as client:
        while len(jobs) < max_jobs:
            # Add pagination
            params["resultsToSkip"] = results_to_skip
            params["resultsToTake"] = min(max_jobs - len(jobs), 100)

            response = client.get(
                REED_SEARCH_ENDPOINT,
                headers=headers,
                params=params,
            )

            if response.status_code == 401:
                raise ReedAPIError(
                    "Invalid Reed API key. Check your REED_API_KEY in .env"
                )
            elif response.status_code != 200:
                raise ReedAPIError(
                    f"Reed API error: {response.status_code} - {response.text}"
                )

            data = response.json()
            results = data.get("results", [])

            if not results:
                break  # No more results

            for job_data in results:
                if len(jobs) >= max_jobs:
                    break

                # Optionally fetch full description
                full_description = None
                if fetch_full_descriptions:
                    try:
                        details = get_job_details(job_data["jobId"])
                        full_description = details.get("jobDescription", "")
                    except ReedAPIError:
                        # If we can't get details, use the short description
                        pass

                job = _parse_job(job_data, full_description)
                jobs.append(job)

            # Check if there are more results
            total_results = data.get("totalResults", 0)
            results_to_skip += len(results)

            if results_to_skip >= total_results:
                break  # No more pages

    return jobs


def search_reed_quick(
    query: str,
    location: str = "London",
    max_jobs: int = 20,
) -> list[Job]:
    """
    Quick search without fetching full descriptions.

    Faster but returns shorter job descriptions.
    Use this for initial browsing, then fetch full details
    for jobs you're interested in.
    """
    return scrape_reed(
        query=query,
        location=location,
        max_jobs=max_jobs,
        fetch_full_descriptions=False,
    )
