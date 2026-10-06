import json
import logging
import re
from typing import Any, Dict, List

from config import settings

logger = logging.getLogger(__name__)

RANKING_PROMPT_TEMPLATE = """You are an expert technical recruiter matching a candidate to open roles.

CANDIDATE PROFILE:
- Target titles: {target_titles}
- Core skills: {core_skills}
- Experience level: {min_years}-{max_years} years
- Summary: {summary}

Below is a numbered list of {count} candidate job postings. Pick the {top_n} best-fit postings for
this candidate and rank them best-first. For each, give a fit score from 0-100 and a one-sentence
reason tied to the candidate's actual skills/background.

Respond with ONLY a JSON array, no markdown fences, no extra commentary. Each element:
{{"index": <int, the posting's number below>, "score": <int 0-100>, "reason": "<one sentence>"}}

JOB POSTINGS:
{job_list}
"""

CLAUDE_MODELS = [
    "claude-haiku-4-5",
    "claude-3-5-haiku-20241022",
    "claude-3-haiku-20240307",
]

# Candidate jobs beyond this count aren't sent to Claude in one call -- keeps the prompt (and
# cost) bounded on days with a very large scraped pool. The best top_n are still picked from
# whichever jobs are included, newest first.
MAX_CANDIDATES_PER_CALL = 150


def _fallback_rank(candidate_jobs: List[Dict[str, Any]], top_n: int) -> List[Dict[str, Any]]:
    """Used when Claude is unavailable -- just takes the newest postings with no real
    scoring, so a resume report still goes out rather than being silently skipped."""
    ranked = sorted(candidate_jobs, key=lambda j: j.get("date_posted", "") or "0000-00-00", reverse=True)[:top_n]
    for job in ranked:
        job["match_score"] = None
        job["match_reason"] = "AI ranking unavailable -- sorted by posting date"
    return ranked


def rank_jobs_for_resume(
    profile: Dict[str, Any],
    candidate_jobs: List[Dict[str, Any]],
    top_n: int,
) -> List[Dict[str, Any]]:
    """
    Ranks candidate_jobs by fit against a resume profile using a single batched Claude call
    (not one call per job), and returns the top_n best matches with match_score/match_reason
    attached, best first.
    """
    if not candidate_jobs:
        return []

    if not settings.USE_AI_FILTER or not settings.CLAUDE_API_KEY:
        logger.warning("Resume matching: AI filter disabled or no CLAUDE_API_KEY -- falling back to newest-first.")
        return _fallback_rank(candidate_jobs, top_n)

    pool = candidate_jobs[:MAX_CANDIDATES_PER_CALL]

    job_list_lines = []
    for i, job in enumerate(pool):
        desc = re.sub(r"<[^>]+>", " ", job.get("description", "") or "")
        desc = re.sub(r"\s+", " ", desc).strip()[:300]
        job_list_lines.append(
            f"{i}. {job.get('title', 'Unknown')} at {job.get('company', 'Unknown')} "
            f"({job.get('location', 'Unknown')}) -- {desc}"
        )

    prompt = RANKING_PROMPT_TEMPLATE.format(
        target_titles=", ".join(profile.get("target_titles") or []) or "Not specified",
        core_skills=", ".join(profile.get("core_skills") or []) or "Not specified",
        min_years=profile.get("min_years", 1),
        max_years=profile.get("max_years", 6),
        summary=profile.get("summary", "Not specified"),
        count=len(pool),
        top_n=min(top_n, len(pool)),
        job_list="\n".join(job_list_lines),
    )

    try:
        import anthropic

        client = anthropic.Anthropic(api_key=settings.CLAUDE_API_KEY)

        response_text = None
        for model_name in CLAUDE_MODELS:
            try:
                message = client.messages.create(
                    model=model_name,
                    max_tokens=4000,
                    messages=[{"role": "user", "content": prompt}],
                )
                response_text = message.content[0].text.strip()
                break
            except Exception as model_err:
                if "not_found_error" in str(model_err) or "404" in str(model_err):
                    logger.warning(f"[Claude] Model '{model_name}' not available for resume ranking, trying next...")
                    continue
                raise

        if response_text is None:
            logger.warning("Resume matching: all Claude models failed. Falling back to newest-first.")
            return _fallback_rank(candidate_jobs, top_n)

        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", response_text.strip())
        rankings = json.loads(cleaned)

        ranked_jobs = []
        for entry in rankings:
            idx = entry.get("index")
            if idx is None or not (0 <= idx < len(pool)):
                continue
            job = dict(pool[idx])
            job["match_score"] = entry.get("score")
            job["match_reason"] = entry.get("reason", "")
            ranked_jobs.append(job)

        if not ranked_jobs:
            logger.warning("Resume matching: Claude returned no usable rankings. Falling back to newest-first.")
            return _fallback_rank(candidate_jobs, top_n)

        return ranked_jobs[:top_n]

    except Exception as e:
        logger.error(f"Resume matching: Claude ranking failed: {str(e)}", exc_info=True)
        return _fallback_rank(candidate_jobs, top_n)
