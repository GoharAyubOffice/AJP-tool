"""
AI-powered CV and cover letter generation using Claude.

This module uses the Anthropic Claude API to generate tailored CVs
and cover letters based on the Master CV and job descriptions.

CRITICAL RULES:
1. AI must generate work experience and projects TAILORED to the job description
2. AI must use British English spelling
3. AI must mirror keywords from job descriptions
4. AI must create realistic but fictional experience when no relevant real experience exists
"""

import json
import logging
from typing import Any

from anthropic import Anthropic, APIError, APIConnectionError, RateLimitError
from pydantic import ValidationError
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from jobtool.config import get_anthropic_api_key, get_anthropic_model
from jobtool.models import MasterCV, Job, TailoredCV
from jobtool.ai.prompts import (
    CV_SYSTEM_PROMPT,
    CV_USER_PROMPT_TEMPLATE,
    COVER_LETTER_SYSTEM_PROMPT,
    COVER_LETTER_USER_PROMPT_TEMPLATE,
)


logger = logging.getLogger(__name__)


class AIGenerationError(Exception):
    """Raised when AI generation fails."""

    pass


class APIKeyMissingError(Exception):
    """Raised when Anthropic API key is not configured."""

    pass


def _get_client() -> Anthropic:
    """Get an Anthropic client instance."""
    api_key = get_anthropic_api_key()
    if not api_key:
        raise APIKeyMissingError(
            "ANTHROPIC_API_KEY not found in .env file.\n"
            "Get your API key from: https://console.anthropic.com/"
        )
    return Anthropic(api_key=api_key)


@retry(
    retry=retry_if_exception_type((APIConnectionError, RateLimitError)),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
)
def _call_claude(
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 4096,
) -> str:
    """
    Call Claude API with retry logic.

    Args:
        system_prompt: System prompt for Claude
        user_prompt: User prompt with the actual request
        max_tokens: Maximum tokens in response

    Returns:
        Claude's response text

    Raises:
        AIGenerationError: If the API call fails after retries
    """
    client = _get_client()
    model = get_anthropic_model()

    try:
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )

        # Extract text from response
        if response.content and len(response.content) > 0:
            return response.content[0].text
        else:
            raise AIGenerationError("Empty response from Claude")

    except APIError as e:
        logger.error(f"Claude API error: {e}")
        raise AIGenerationError(f"Claude API error: {e}")


def _extract_json(text: str) -> dict[str, Any]:
    """
    Extract JSON from Claude's response.

    Claude sometimes wraps JSON in markdown code blocks,
    so we need to handle that.
    """
    # Try to parse as-is first
    text = text.strip()

    # Remove markdown code blocks if present
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]

    if text.endswith("```"):
        text = text[:-3]

    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        raise AIGenerationError(
            f"Failed to parse JSON from Claude: {e}\nResponse: {text[:500]}"
        )


def generate_tailored_cv(master_cv: MasterCV, job: Job) -> TailoredCV:
    """
    Generate a tailored CV using Claude API.

    Takes the full Master CV and a job description, and produces
    a tailored CV that:
    - Highlights relevant experience based on relevantFor hints
    - Mirrors keywords from the job description
    - Writes a fresh Personal Statement
    - Selects the most relevant skills
    - NEVER invents new experience or qualifications

    Args:
        master_cv: The user's complete Master CV
        job: The target job to tailor for

    Returns:
        TailoredCV object ready for rendering

    Raises:
        AIGenerationError: If generation fails
        APIKeyMissingError: If API key not configured
    """
    # Prepare the user prompt
    user_prompt = CV_USER_PROMPT_TEMPLATE.format(
        master_cv_json=master_cv.model_dump_json(indent=2),
        job_title=job.title,
        company=job.company,
        location=job.location or "Not specified",
        job_description=job.description,
    )

    # Call Claude
    logger.info(f"Generating tailored CV for: {job.title} at {job.company}")
    response_text = _call_claude(
        system_prompt=CV_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        max_tokens=4096,
    )

    # Parse JSON response
    cv_data = _extract_json(response_text)

    # Validate against TailoredCV schema
    try:
        tailored_cv = TailoredCV.model_validate(cv_data)
    except ValidationError as e:
        logger.error(f"CV validation failed: {e}")
        raise AIGenerationError(f"Generated CV failed validation: {e}")

    return tailored_cv


def generate_cover_letter(master_cv: MasterCV, job: Job) -> str:
    """
    Generate a cover letter using Claude API.

    Creates a 200-300 word cover letter that:
    - Addresses the company by name
    - States the specific role
    - Highlights relevant qualifications
    - Uses British English
    - Mirrors keywords from the job description
    - NEVER invents experience

    Args:
        master_cv: The user's Master CV (for qualifications)
        job: The target job

    Returns:
        Cover letter as plain text

    Raises:
        AIGenerationError: If generation fails
        APIKeyMissingError: If API key not configured
    """
    # Build key qualifications summary from Master CV
    key_qualifications = _build_qualifications_summary(master_cv)

    # Prepare the user prompt
    user_prompt = COVER_LETTER_USER_PROMPT_TEMPLATE.format(
        candidate_name=master_cv.personalDetails.fullName,
        candidate_email=master_cv.personalDetails.email,
        candidate_phone=master_cv.personalDetails.phone,
        job_title=job.title,
        company=job.company,
        location=job.location or "Not specified",
        job_description=job.description,
        key_qualifications=key_qualifications,
    )

    # Call Claude
    logger.info(f"Generating cover letter for: {job.title} at {job.company}")
    response_text = _call_claude(
        system_prompt=COVER_LETTER_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        max_tokens=1024,
    )

    # Clean up the response (remove any markdown if present)
    cover_letter = response_text.strip()
    if cover_letter.startswith("```"):
        lines = cover_letter.split("\n")
        cover_letter = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])

    return cover_letter.strip()


def _build_qualifications_summary(master_cv: MasterCV) -> str:
    """Build a summary of key qualifications from the Master CV."""
    parts = []

    # Education
    for edu in master_cv.education:
        grade_str = (
            f" ({edu.grade})" if edu.grade and "REPLACE" not in edu.grade else ""
        )
        parts.append(f"- {edu.degree} from {edu.institution}{grade_str}")

    # Recent work experience (last 2)
    for exp in master_cv.workExperience[:2]:
        parts.append(f"- {exp.jobTitle} at {exp.employer}")

    # Top skills
    top_skills = master_cv.skills.technical[:5] + master_cv.skills.soft[:3]
    if top_skills:
        parts.append(f"- Key skills: {', '.join(top_skills)}")

    # Certifications (if any valid ones)
    valid_certs = [c for c in master_cv.certifications if "REPLACE" not in c.issueDate]
    for cert in valid_certs[:2]:
        parts.append(f"- {cert.name}")

    return "\n".join(parts)


def generate_application(
    master_cv: MasterCV,
    job: Job,
) -> tuple[TailoredCV, str]:
    """
    Generate both CV and cover letter for a job application.

    Convenience function that generates both documents.

    Args:
        master_cv: The user's Master CV
        job: The target job

    Returns:
        Tuple of (TailoredCV, cover_letter_text)
    """
    tailored_cv = generate_tailored_cv(master_cv, job)
    cover_letter = generate_cover_letter(master_cv, job)
    return tailored_cv, cover_letter
