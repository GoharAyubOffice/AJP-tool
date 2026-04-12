"""
Tests for job scrapers.

These tests verify the scraper implementations work correctly.
Some tests require API keys and network access.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from jobtool.models import Job
from jobtool.scrapers.reed import (
    scrape_reed,
    get_job_details,
    _parse_job,
    _get_auth_header,
    ReedAPIError,
    ReedAPIKeyMissing,
)


class TestReedParser:
    """Test Reed API response parsing."""

    def test_parse_job_basic(self):
        """Test parsing a basic job response."""
        data = {
            "jobId": 12345,
            "jobTitle": "Data Entry Clerk",
            "employerName": "Acme Corp",
            "locationName": "London",
            "minimumSalary": 25000,
            "maximumSalary": 30000,
            "jobDescription": "A great job opportunity...",
            "jobUrl": "https://www.reed.co.uk/jobs/data-entry/12345",
            "date": "01/04/2026",
        }

        job = _parse_job(data)

        assert job.source == "reed"
        assert job.external_id == "12345"
        assert job.title == "Data Entry Clerk"
        assert job.company == "Acme Corp"
        assert job.location == "London"
        assert job.salary_min == 25000
        assert job.salary_max == 30000
        assert job.status == "pending"

    def test_parse_job_missing_salary(self):
        """Test parsing job with no salary info."""
        data = {
            "jobId": 12345,
            "jobTitle": "Junior Developer",
            "employerName": "Tech Co",
            "locationName": "Manchester",
            "jobDescription": "Great opportunity",
            "jobUrl": "https://www.reed.co.uk/jobs/dev/12345",
        }

        job = _parse_job(data)

        assert job.salary_min is None
        assert job.salary_max is None

    def test_parse_job_with_full_description(self):
        """Test parsing with full description override."""
        data = {
            "jobId": 12345,
            "jobTitle": "Admin",
            "employerName": "Company",
            "locationName": "London",
            "jobDescription": "Short desc",
            "jobUrl": "https://www.reed.co.uk/jobs/admin/12345",
        }

        full_desc = "This is the full, detailed job description..."
        job = _parse_job(data, full_description=full_desc)

        assert job.description == full_desc


class TestReedAuth:
    """Test Reed API authentication."""

    def test_auth_header_missing_key(self):
        """Test error when API key is missing."""
        with patch("jobtool.scrapers.reed.get_reed_api_key", return_value=None):
            with pytest.raises(ReedAPIKeyMissing):
                _get_auth_header()

    def test_auth_header_format(self):
        """Test auth header is correctly formatted."""
        with patch("jobtool.scrapers.reed.get_reed_api_key", return_value="test-key"):
            header = _get_auth_header()

            assert "Authorization" in header
            assert header["Authorization"].startswith("Basic ")


class TestReedScraper:
    """Test Reed scraper functionality."""

    @patch("jobtool.scrapers.reed._get_auth_header")
    @patch("jobtool.scrapers.reed.httpx.Client")
    def test_scrape_reed_success(self, mock_client_class, mock_auth):
        """Test successful scrape returns jobs."""
        mock_auth.return_value = {"Authorization": "Basic test"}

        # Mock the HTTP client
        mock_client = MagicMock()
        mock_client_class.return_value.__enter__ = Mock(return_value=mock_client)
        mock_client_class.return_value.__exit__ = Mock(return_value=False)

        # Mock search response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "results": [
                {
                    "jobId": 1,
                    "jobTitle": "Test Job",
                    "employerName": "Test Co",
                    "locationName": "London",
                    "jobDescription": "Test description",
                    "jobUrl": "https://reed.co.uk/jobs/1",
                }
            ],
            "totalResults": 1,
        }
        mock_client.get.return_value = mock_response

        jobs = scrape_reed(
            query="test",
            location="London",
            max_jobs=1,
            fetch_full_descriptions=False,
        )

        assert len(jobs) == 1
        assert jobs[0].title == "Test Job"
        assert jobs[0].source == "reed"

    @patch("jobtool.scrapers.reed._get_auth_header")
    @patch("jobtool.scrapers.reed.httpx.Client")
    def test_scrape_reed_auth_error(self, mock_client_class, mock_auth):
        """Test auth error is handled."""
        mock_auth.return_value = {"Authorization": "Basic bad"}

        mock_client = MagicMock()
        mock_client_class.return_value.__enter__ = Mock(return_value=mock_client)
        mock_client_class.return_value.__exit__ = Mock(return_value=False)

        mock_response = Mock()
        mock_response.status_code = 401
        mock_client.get.return_value = mock_response

        with pytest.raises(ReedAPIError, match="Invalid Reed API key"):
            scrape_reed("test", "London", max_jobs=1, fetch_full_descriptions=False)


class TestJobModel:
    """Test Job model validation."""

    def test_job_creation(self):
        """Test creating a valid Job."""
        job = Job(
            source="reed",
            external_id="123",
            title="Test Job",
            company="Test Co",
            location="London",
            description="A test job",
            url="https://example.com/job/123",
            scraped_at=datetime.now().isoformat(),
        )

        assert job.status == "pending"
        assert job.id is None  # Not yet in database

    def test_job_with_salary(self):
        """Test Job with salary range."""
        job = Job(
            source="indeed",
            external_id="456",
            title="Developer",
            company="Tech Co",
            location="Manchester",
            salary_min=40000,
            salary_max=50000,
            description="Developer role",
            url="https://example.com/job/456",
            scraped_at=datetime.now().isoformat(),
        )

        assert job.salary_min == 40000
        assert job.salary_max == 50000


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
