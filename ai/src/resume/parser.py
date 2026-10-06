import io
import json
import logging
import re
from typing import Any, Dict

from config import settings

logger = logging.getLogger(__name__)

DEFAULT_MIN_YEARS = 1
DEFAULT_MAX_YEARS = 6

PROFILE_PROMPT_TEMPLATE = """You are an expert technical recruiter. Read the resume text below and extract a
structured candidate profile as a single JSON object, with exactly these keys:

- "candidate_name": the candidate's full name as it appears on the resume (string)
- "target_titles": 3-6 job titles this candidate should be matched against, most relevant first (array of strings)
- "core_skills": 8-15 of the candidate's strongest, most distinctive technical skills/tools (array of strings)
- "min_years": the low end of total professional experience this candidate realistically qualifies for (integer)
- "max_years": the high end of total professional experience this candidate realistically qualifies for (integer)
- "summary": a 2-3 sentence summary of the candidate's background and ideal next role (string)

Respond with ONLY the JSON object, no markdown fences, no extra commentary.

RESUME TEXT:
{resume_text}
"""

# Same fallback chain used for job filtering (see src/filters/ai_filter.py) -- newest first,
# falling back to a baseline model that's universally available.
CLAUDE_MODELS = [
    "claude-haiku-4-5",
    "claude-3-5-haiku-20241022",
    "claude-3-haiku-20240307",
]


def extract_text_from_resume(filename: str, file_bytes: bytes) -> str:
    """
    Extracts plain text from an uploaded resume file. Supports PDF (.pdf) and Word (.docx).
    Raises ValueError for unsupported file types or unreadable files.
    """
    ext = (filename.rsplit(".", 1)[-1] if "." in filename else "").lower()

    if ext == "pdf":
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(file_bytes))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
    elif ext == "docx":
        import docx

        document = docx.Document(io.BytesIO(file_bytes))
        text = "\n".join(p.text for p in document.paragraphs)
    else:
        raise ValueError(f"Unsupported resume file type: .{ext}. Only .pdf and .docx are supported.")

    text = text.strip()
    if not text:
        raise ValueError("Could not extract any text from the resume -- it may be a scanned image without a text layer.")
    return text


def _default_profile(resume_text: str) -> Dict[str, Any]:
    """Fallback profile used when Claude is unavailable, so an upload still succeeds."""
    return {
        "candidate_name": "Unknown Candidate",
        "target_titles": [],
        "core_skills": [],
        "min_years": DEFAULT_MIN_YEARS,
        "max_years": DEFAULT_MAX_YEARS,
        "summary": resume_text[:300],
    }


def extract_profile_with_ai(resume_text: str) -> Dict[str, Any]:
    """
    Calls Claude once to turn raw resume text into a structured matching profile. Runs only
    at upload time (and on re-upload) -- never on the daily matching run -- to keep API cost
    independent of how many jobs are scraped each day.

    Falls back to a generic profile (default 1-6 year experience range, no AI unavailable)
    rather than raising, so an upload never fails outright just because Claude is down.
    """
    if not settings.USE_AI_FILTER or not settings.CLAUDE_API_KEY:
        logger.warning("Resume upload: AI filter disabled or no CLAUDE_API_KEY -- using a generic profile.")
        return _default_profile(resume_text)

    try:
        import anthropic

        client = anthropic.Anthropic(api_key=settings.CLAUDE_API_KEY)
        prompt = PROFILE_PROMPT_TEMPLATE.format(resume_text=resume_text[:12000])

        response_text = None
        for model_name in CLAUDE_MODELS:
            try:
                message = client.messages.create(
                    model=model_name,
                    max_tokens=800,
                    messages=[{"role": "user", "content": prompt}],
                )
                response_text = message.content[0].text.strip()
                break
            except Exception as model_err:
                if "not_found_error" in str(model_err) or "404" in str(model_err):
                    logger.warning(f"[Claude] Model '{model_name}' not available for resume parsing, trying next...")
                    continue
                raise

        if response_text is None:
            logger.warning("Resume upload: all Claude models failed. Using a generic profile.")
            return _default_profile(resume_text)

        # Strip markdown fences if Claude wraps the JSON in them despite instructions.
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", response_text.strip())
        profile = json.loads(cleaned)

        profile.setdefault("candidate_name", "Unknown Candidate")
        profile.setdefault("target_titles", [])
        profile.setdefault("core_skills", [])
        profile.setdefault("min_years", DEFAULT_MIN_YEARS)
        profile.setdefault("max_years", DEFAULT_MAX_YEARS)
        profile.setdefault("summary", "")
        profile["min_years"] = int(profile["min_years"])
        profile["max_years"] = int(profile["max_years"])
        return profile

    except Exception as e:
        logger.error(f"Resume upload: Claude profile extraction failed: {str(e)}", exc_info=True)
        return _default_profile(resume_text)
