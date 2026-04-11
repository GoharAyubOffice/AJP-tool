"""Pydantic v2 models for MasterCV, Job, and Application."""

from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator


# ============================================================================
# Master CV Models
# ============================================================================

class PersonalDetails(BaseModel):
    """Personal contact information."""
    fullName: str
    city: str
    region: str
    country: str
    phone: str
    email: str
    linkedin: str | None = None
    github: str | None = None
    website: str | None = None


class WorkExperience(BaseModel):
    """A single work experience entry."""
    jobTitle: str
    employer: str
    location: str
    startDate: str  # YYYY-MM format
    endDate: str  # YYYY-MM or "Present"
    type: Literal["full-time", "part-time", "freelance", "self-employed"]
    summary: str
    bullets: list[str]
    keywords: list[str] = Field(default_factory=list)
    skillsUsed: list[str] = Field(default_factory=list)
    relevantFor: list[str] = Field(default_factory=list)

    @field_validator("startDate")
    @classmethod
    def validate_start_date(cls, v: str) -> str:
        """Validate start date is in YYYY-MM format."""
        if not v:
            raise ValueError("startDate is required")
        parts = v.split("-")
        if len(parts) != 2:
            raise ValueError(f"startDate must be in YYYY-MM format, got: {v}")
        year, month = parts
        if not (year.isdigit() and len(year) == 4):
            raise ValueError(f"startDate year must be 4 digits, got: {year}")
        if not (month.isdigit() and 1 <= int(month) <= 12):
            raise ValueError(f"startDate month must be 01-12, got: {month}")
        return v

    @field_validator("endDate")
    @classmethod
    def validate_end_date(cls, v: str) -> str:
        """Validate end date is in YYYY-MM format or 'Present'."""
        if not v:
            raise ValueError("endDate is required")
        if v.lower() == "present":
            return "Present"
        parts = v.split("-")
        if len(parts) != 2:
            raise ValueError(f"endDate must be in YYYY-MM format or 'Present', got: {v}")
        year, month = parts
        if not (year.isdigit() and len(year) == 4):
            raise ValueError(f"endDate year must be 4 digits, got: {year}")
        if not (month.isdigit() and 1 <= int(month) <= 12):
            raise ValueError(f"endDate month must be 01-12, got: {month}")
        return v


class Education(BaseModel):
    """A single education entry."""
    degree: str
    institution: str
    location: str
    startDate: str  # YYYY-MM format
    endDate: str  # YYYY-MM format
    grade: str | None = None
    highlights: list[str] = Field(default_factory=list)


class Skills(BaseModel):
    """Skills categorised by type."""
    technical: list[str] = Field(default_factory=list)
    soft: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    domains: list[str] = Field(default_factory=list)


class Certification(BaseModel):
    """A professional certification."""
    name: str
    issuer: str
    issueDate: str
    expiryDate: str | None = None
    credentialId: str | None = None


class Language(BaseModel):
    """A language proficiency entry."""
    language: str
    proficiency: str  # e.g., "Native", "Fluent", "Conversational"


class Project(BaseModel):
    """A personal or professional project."""
    name: str
    description: str
    url: str | None = None
    technologies: list[str] = Field(default_factory=list)


class MasterCV(BaseModel):
    """
    The complete Master CV schema.

    This is the single source of truth for all CV generation.
    The AI will select from this data but never invent new content.
    """
    version: str = "2.0"
    lastUpdated: str
    personalDetails: PersonalDetails
    rightToWork: str
    personalStatement: str
    workExperience: list[WorkExperience]
    education: list[Education]
    skills: Skills
    certifications: list[Certification] = Field(default_factory=list)
    languages: list[Language] = Field(default_factory=list)
    projects: list[Project] = Field(default_factory=list)
    achievements: list[str] = Field(default_factory=list)
    references: str = "Available on request"

    # Allow extra fields like "_instructions" in the JSON
    model_config = ConfigDict(extra="ignore")


# ============================================================================
# Job Models
# ============================================================================

class Job(BaseModel):
    """A scraped job listing."""
    id: int | None = None  # Set by database
    source: Literal["reed", "indeed", "linkedin"]
    external_id: str  # ID from the source
    title: str
    company: str
    location: str | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    description: str
    url: str
    posted_date: str | None = None
    scraped_at: str  # ISO format timestamp
    status: Literal["pending", "submitted", "skipped"] = "pending"


# ============================================================================
# Application Models
# ============================================================================

class Application(BaseModel):
    """A generated application for a job."""
    id: int | None = None  # Set by database
    job_id: int
    cv_path: str | None = None
    cv_pdf_path: str | None = None
    cover_letter_path: str | None = None
    cover_letter_pdf_path: str | None = None
    status: Literal["pending", "submitted", "rejected", "interview", "offer"] = "pending"
    submitted_at: str | None = None
    notes: str | None = None
    created_at: str  # ISO format timestamp


# ============================================================================
# Tailored CV (output from AI generation)
# ============================================================================

class TailoredCV(BaseModel):
    """
    A tailored CV generated by AI for a specific job.

    This follows the same structure as MasterCV but may have
    fewer work experiences, different bullet ordering, and
    a customised personal statement.
    """
    personalDetails: PersonalDetails
    personalStatement: str
    workExperience: list[WorkExperience]
    education: list[Education]
    skills: Skills
    certifications: list[Certification] = Field(default_factory=list)
    languages: list[Language] = Field(default_factory=list)
    references: str = "Available on request"
