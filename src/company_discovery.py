import json
import logging
import requests
from typing import List, Dict
from config import settings

logger = logging.getLogger(__name__)

COMPANIES_PATH = settings.BASE_DIR / "config" / "companies.json"

CLAUDE_DISCOVERY_PROMPT = """You are a cybersecurity recruitment expert who knows which US tech companies use Greenhouse or Ashby ATS.

Generate {count} companies that hire cybersecurity professionals in the US. Think broadly:
- Pure-play cybersecurity: endpoint, cloud security, SIEM, SOAR, IAM, GRC, threat intel, pen testing
- Tech companies with large security teams: fintech, cloud infra, SaaS, e-commerce, social media, payments
- Defense/government tech contractors with security roles
- Compliance/audit tech companies
- Data privacy and identity companies
- Newer startups in AI security, API security, supply chain security, DevSecOps

The Greenhouse API token is the slug in: boards-api.greenhouse.io/v1/boards/TOKEN/jobs
The Ashby API token is the slug in: api.ashbyhq.com/posting-api/job-board/TOKEN
Usually it's the company name in lowercase, no spaces (e.g., "crowdstrike", "paloaltonetworks").

DO NOT include any of these (already in database): {existing_names}

RESPONSE FORMAT (strict JSON array only, no other text):
[{{"name": "CompanyName", "ats": "greenhouse", "token": "companytoken"}}]"""


def discover_new_companies(target_count: int = 30) -> List[Dict]:
    if not settings.CLAUDE_API_KEY:
        logger.warning("No Claude API key for company discovery.")
        return []

    with open(COMPANIES_PATH, "r") as f:
        existing = json.load(f)

    existing_tokens = {c["token"] for c in existing}
    existing_names = ", ".join(c["name"] for c in existing)

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=settings.CLAUDE_API_KEY)

        prompt = CLAUDE_DISCOVERY_PROMPT.format(
            count=target_count,
            existing_names=existing_names[:3000],
        )

        MODELS = [
            "claude-haiku-4-5",
            "claude-3-5-haiku-20241022",
            "claude-3-haiku-20240307",
        ]

        response_text = None
        for model in MODELS:
            try:
                msg = client.messages.create(
                    model=model,
                    max_tokens=4000,
                    messages=[{"role": "user", "content": prompt}],
                )
                response_text = msg.content[0].text.strip()
                break
            except Exception as e:
                if "not_found" in str(e) or "404" in str(e):
                    continue
                raise

        if not response_text:
            logger.warning("Claude unavailable for company discovery.")
            return []

        # Parse JSON from response
        import re
        json_match = re.search(r'\[.*\]', response_text, re.DOTALL)
        if not json_match:
            logger.warning(f"Could not parse JSON from Claude response.")
            return []

        candidates = json.loads(json_match.group())
        logger.info(f"Claude suggested {len(candidates)} new companies.")

        # Validate each company actually has a working API
        verified = []
        for comp in candidates:
            token = comp.get("token", "").strip().lower()
            name = comp.get("name", "").strip()
            ats = comp.get("ats", "").strip().lower()

            if not token or not name or token in existing_tokens:
                continue

            # Try multiple token variations
            name_slug = name.lower().replace(" ", "").replace(".", "").replace("-", "")
            token_variants = list(dict.fromkeys([token, name_slug, name.lower().replace(" ", "-"), name.lower().replace(" ", "")]))

            found = False
            for tv in token_variants:
                if tv in existing_tokens:
                    continue
                if _verify_greenhouse(tv):
                    verified.append({"name": name, "ats": "greenhouse", "token": tv, "careers_url": ""})
                    existing_tokens.add(tv)
                    found = True
                    break
                if _verify_ashby(tv):
                    verified.append({"name": name, "ats": "ashby", "token": tv, "careers_url": ""})
                    existing_tokens.add(tv)
                    found = True
                    break

        logger.info(f"Verified {len(verified)} new companies with working APIs.")
        return verified

    except Exception as e:
        logger.error(f"Company discovery failed: {str(e)}", exc_info=True)
        return []


def _verify_greenhouse(token: str) -> bool:
    try:
        r = requests.get(
            f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs",
            timeout=8,
        )
        if r.status_code == 200:
            jobs = r.json().get("jobs", [])
            return len(jobs) > 0
    except:
        pass
    return False


def _verify_ashby(token: str) -> bool:
    try:
        r = requests.get(
            f"https://api.ashbyhq.com/posting-api/job-board/{token}",
            timeout=8,
        )
        if r.status_code == 200:
            jobs = r.json().get("jobs", [])
            return len(jobs) > 0
    except:
        pass
    return False


def update_companies_file(new_companies: List[Dict]) -> int:
    if not new_companies:
        return 0

    with open(COMPANIES_PATH, "r") as f:
        existing = json.load(f)

    existing_tokens = {c["token"] for c in existing}
    added = 0

    for comp in new_companies:
        if comp["token"] not in existing_tokens:
            existing.append(comp)
            existing_tokens.add(comp["token"])
            added += 1

    if added > 0:
        with open(COMPANIES_PATH, "w") as f:
            json.dump(existing, f, indent=2)
        logger.info(f"Added {added} new companies to database. Total: {len(existing)}")

    return added
