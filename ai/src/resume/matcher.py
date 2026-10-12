import json
import logging
import re
from typing import Any, Dict, List

from config import settings

logger = logging.getLogger(__name__)

RANKING_PROMPT_TEMPLATE = """You are a strict, skeptical technical recruiter screening postings for one candidate.
Your job is precision, not volume -- a candidate who gets one genuinely relevant lead is served far
better than one who gets twenty near-misses mixed in with it.

CANDIDATE PROFILE:
- Target titles: {target_titles}
- Core skills: {core_skills}
- Experience level: {min_years}-{max_years} years
- Summary: {summary}

Below is a numbered list of {count} candidate job postings. Select ONLY the postings that are a
genuine match: the role itself (not just the industry or company) aligns with the candidate's
target titles, AND the posting's actual responsibilities/requirements substantively overlap with
the candidate's core skills -- not just a tangential mention of one shared buzzword. A posting in
a related field but a different function (e.g. a sales/support/ops role at a tech company, for an
engineering candidate) is NOT a match, no matter how senior or well-paid it is.

Select at most {top_n}, ranked best-first. If fewer than {top_n} postings are genuine matches,
return fewer -- do not include a weak or borderline posting just to reach {top_n}. Returning zero
results is the correct answer if nothing in the list is a real match. For each selected posting,
give an honest fit score from 0-100 (reserve 70+ for a posting you'd actually forward to this
candidate without caveats) and a one-sentence reason tied to specific overlap with their actual
skills/background.

Respond with ONLY a JSON array, no markdown fences, no extra commentary. Each element:
{{"index": <int, the posting's number below>, "score": <int 0-100>, "reason": "<one sentence>"}}

JOB POSTINGS:
{job_list}
"""

# A posting Claude itself scored below this is dropped even if it included it in the response --
# a floor beneath the prompt's own "70+ to actually forward" guidance, catching a model that
# includes a borderline pick despite being told not to.
MIN_MATCH_SCORE = 60

CLAUDE_MODELS = [
    "claude-haiku-4-5",
    "claude-3-5-haiku-20241022",
    "claude-3-haiku-20240307",
]

# Candidate jobs beyond this count aren't sent to Claude in one call -- keeps the prompt (and
# cost) bounded on days with a very large scraped pool (tens of thousands of candidates is
# normal). Which ones make the cut matters a lot, so _narrow_candidates below picks them by
# relevance + company diversity rather than arbitrary list order.
MAX_CANDIDATES_PER_CALL = 300


def _keyword_overlap_score(job: Dict[str, Any], profile: Dict[str, Any]) -> int:
    """Cheap, local relevance heuristic (no API call). Counts how many of the resume's
    target titles/skills appear in the job's title or description. Used both to decide which
    jobs are worth spending the one Claude call's limited slots on, AND as the fallback
    ranking signal itself when Claude is unavailable -- relevance must never degrade to pure
    recency, since a resume report sorted by date alone has no connection to the resume at
    all (confirmed in production: teller/warehouse/phlebotomist roles for a Data Engineer
    resume, simply because they were the most recently posted jobs that day)."""
    haystack = f"{job.get('title', '')} {job.get('description', '')}".lower()
    score = 0
    for title in profile.get("target_titles") or []:
        if title.lower() in haystack:
            score += 3  # a title match is a much stronger signal than a skill mention
    for skill in profile.get("core_skills") or []:
        if skill.lower() in haystack:
            score += 1
    return score


def _narrow_candidates(profile: Dict[str, Any], candidate_jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Reduces a (potentially huge) candidate pool to at most MAX_CANDIDATES_PER_CALL jobs,
    sorted best-first by _keyword_overlap_score, in two steps:

    1. At most one job per company -- the single best-scoring one. Without this, a company
       that posted the same role across many locations (seen in practice: one employer
       filling 15+ of the daily slots with near-duplicate listings) can crowd out every other
       company's jobs entirely. The rest of that company's postings are simply never
       considered today -- not recorded as sent, so they're still available for a future run
       instead of being wasted on duplicates.
    2. The remaining one-per-company jobs are sorted by relevance before truncating to
       MAX_CANDIDATES_PER_CALL, so if there are still more companies than that cap, the ones
       most likely to actually match the resume are the ones that survive.

    Both rank_jobs_for_resume's Claude path and its fallback build on this same narrowed,
    relevance-sorted pool -- Claude does finer-grained ranking on top of it when available,
    but even without Claude, the output is never just "whatever's newest."
    """
    best_per_company: Dict[str, Dict[str, Any]] = {}
    scores: Dict[int, int] = {}
    for job in candidate_jobs:
        company = job.get("company", "")
        score = _keyword_overlap_score(job, profile)
        scores[id(job)] = score
        current_best = best_per_company.get(company)
        if current_best is None or score > scores.get(id(current_best), 0):
            best_per_company[company] = job

    diverse = list(best_per_company.values())
    diverse.sort(key=lambda j: scores.get(id(j), 0), reverse=True)
    for job in diverse:
        job["_keyword_score"] = scores.get(id(job), 0)
    return diverse[:MAX_CANDIDATES_PER_CALL]


def _fallback_rank(pool: List[Dict[str, Any]], top_n: int) -> List[Dict[str, Any]]:
    """Used when Claude is unavailable. `pool` must already be the output of
    _narrow_candidates (one job per company, sorted best-first by keyword relevance) -- this
    just takes the top_n and labels them, it does no ranking of its own.

    Drops zero-overlap jobs entirely rather than padding the report up to top_n with them --
    a shorter, honest list of plausible matches beats a full one padded with jobs that share
    nothing with the resume (confirmed in production: a Data Engineer resume's report was
    filled out with Teller/Warehouse/Phlebotomist postings once real matches ran out)."""
    ranked = [job for job in pool if job.get("_keyword_score", 0) > 0][:top_n]
    for job in ranked:
        score = job.pop("_keyword_score", 0)
        job["match_score"] = None
        job["match_reason"] = f"AI ranking unavailable -- matched {score} resume keyword(s)"
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

    # One-job-per-company + relevance sort applies to every path below, Claude or not.
    pool = _narrow_candidates(profile, candidate_jobs)

    if not settings.USE_AI_FILTER or not settings.CLAUDE_API_KEY:
        logger.warning("Resume matching: AI filter disabled or no CLAUDE_API_KEY -- using keyword-relevance fallback.")
        return _fallback_rank(pool, top_n)

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
            logger.warning("Resume matching: all Claude models failed. Using keyword-relevance fallback.")
            return _fallback_rank(pool, top_n)

        try:
            cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", response_text.strip())
            rankings = json.loads(cleaned)
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning(f"Resume matching: Claude's response wasn't valid JSON ({e}). Using keyword-relevance fallback.")
            return _fallback_rank(pool, top_n)

        ranked_jobs = []
        for entry in rankings:
            idx = entry.get("index")
            score = entry.get("score", 0)
            if idx is None or not (0 <= idx < len(pool)):
                continue
            if score < MIN_MATCH_SCORE:
                continue  # Claude included it despite being told not to pad -- drop it anyway
            job = dict(pool[idx])
            job.pop("_keyword_score", None)
            job["match_score"] = score
            job["match_reason"] = entry.get("reason", "")
            ranked_jobs.append(job)

        # A successfully-parsed response with zero (or zero post-threshold) results is Claude
        # correctly reporting "nothing here is a real match" -- not a failure, so it's NOT a
        # fallback trigger. Falling back here would reintroduce the weak/irrelevant matches
        # Claude was specifically asked to reject.
        if not ranked_jobs:
            logger.info("Resume matching: Claude found no postings meeting the match bar today.")
        return ranked_jobs[:top_n]

    except Exception as e:
        logger.error(f"Resume matching: Claude ranking failed: {str(e)}", exc_info=True)
        return _fallback_rank(pool, top_n)
