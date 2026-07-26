"""
One-off repair script for companies stored with ats='playwright'.

Those rows were created by the bulk import scripts, which hardcoded ats='playwright' with a
guessed careers_url (e.g. "https://templehealthcareers.com"). Many of those domains do not
exist, which produced the daily ERR_NAME_NOT_RESOLVED / timeout errors, and the browser
fallback never returned real job listings anyway.

This script probes the Greenhouse, Lever, and Ashby APIs for each such company using token
guesses derived from its name, and converts the ones that match into proper API-backed rows.
Companies with no working ATS are left untouched and listed at the end so they can be fixed
or deleted from the dashboard.

Usage:
    python fix_playwright_companies.py            # dry run, shows what would change
    python fix_playwright_companies.py --apply    # writes the changes
"""
import re
import sys
import logging
import requests
from typing import List, Optional, Tuple

from db import SessionLocal, Company

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("fix_playwright")

TIMEOUT = 8
API_ATS = {"greenhouse", "lever", "ashby"}


def token_candidates(name: str) -> List[str]:
    """Builds plausible ATS slugs from a company name, most likely first."""
    # Drop parenthetical qualifiers the import scripts added, e.g. "Visa (CA)" -> "Visa"
    base = re.sub(r"\([^)]*\)", " ", name)
    # Drop common corporate suffixes and separators
    base = re.sub(r"\b(inc|llc|ltd|corp|corporation|co|company|group|health|holdings)\b", " ", base, flags=re.I)
    base = base.replace("&", " and ")
    words = re.findall(r"[a-z0-9]+", base.lower())
    if not words:
        return []

    joined = "".join(words)
    hyphen = "-".join(words)
    candidates = [joined, hyphen, words[0]]
    if len(words) > 1:
        candidates.append("".join(words[:2]))

    # Preserve order, drop duplicates and 1-character slugs
    seen, out = set(), []
    for c in candidates:
        if len(c) > 1 and c not in seen:
            seen.add(c)
            out.append(c)
    return out


def _has_jobs(url: str, extract) -> bool:
    try:
        r = requests.get(url, timeout=TIMEOUT)
        if r.status_code != 200:
            return False
        return len(extract(r.json())) > 0
    except Exception:
        return False


def verify_token(token: str) -> Optional[str]:
    """Returns the ATS name if `token` resolves to a live job board, else None."""
    if _has_jobs(f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs",
                 lambda j: j.get("jobs", [])):
        return "greenhouse"
    if _has_jobs(f"https://api.ashbyhq.com/posting-api/job-board/{token}",
                 lambda j: j.get("jobs", [])):
        return "ashby"
    if _has_jobs(f"https://api.lever.co/v0/postings/{token}?mode=json",
                 lambda j: j if isinstance(j, list) else []):
        return "lever"
    return None


def find_ats(company: Company, taken_tokens: set) -> Optional[Tuple[str, str]]:
    """Probes token guesses for a company. Returns (ats, token) on the first hit."""
    for token in token_candidates(company.name):
        if token in taken_tokens:
            continue
        ats = verify_token(token)
        if ats:
            return ats, token
    return None


def main(apply: bool) -> int:
    db = SessionLocal()
    try:
        broken = [c for c in db.query(Company).all()
                  if (c.ats or "").lower() not in API_ATS or not (c.token or "").strip()]
        taken = {(c.token or "").strip().lower()
                 for c in db.query(Company).all() if (c.token or "").strip()}

        if not broken:
            logger.info("No companies need repair — every row already has an ATS API token.")
            return 0

        logger.info(f"Probing {len(broken)} companies without a usable ATS token...\n")

        fixed, unfixable = [], []
        for i, company in enumerate(broken, 1):
            result = find_ats(company, taken)
            if result:
                ats, token = result
                fixed.append((company, ats, token))
                taken.add(token)
                logger.info(f"  [{i}/{len(broken)}] FOUND   {company.name} -> {ats}/{token}")
                if apply:
                    company.ats = ats
                    company.token = token
            else:
                unfixable.append(company)
                logger.info(f"  [{i}/{len(broken)}] no ATS  {company.name}")

        if apply:
            db.commit()

        logger.info("\n" + "=" * 60)
        logger.info(f"Recovered : {len(fixed)}")
        logger.info(f"No ATS    : {len(unfixable)}")
        logger.info("=" * 60)

        if unfixable:
            logger.info("\nThese have no public ATS API and will be skipped by the daily run.")
            logger.info("Delete them from the dashboard, or add a token if you know it:\n")
            for c in unfixable[:40]:
                logger.info(f"  - {c.name}")
            if len(unfixable) > 40:
                logger.info(f"  ... and {len(unfixable) - 40} more")

        if apply:
            logger.info(f"\nApplied: {len(fixed)} companies now scrape via a real ATS API.")
        else:
            logger.info("\nDry run — nothing was written. Re-run with --apply to save these changes.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main(apply="--apply" in sys.argv))
