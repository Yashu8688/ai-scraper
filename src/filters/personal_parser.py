import re
import logging
from typing import Dict, Any, Tuple

logger = logging.getLogger(__name__)

ROLE_KEYWORDS = [
    r"\bfull\s*stack\b", r"\bfullstack\b", r"\bfrontend\b", r"\bfront\s*end\b",
    r"\bbackend\b", r"\bback\s*end\b", r"\bsoftware\s+engineer\b", r"\bsoftware\s+developer\b",
    r"\bweb\s+developer\b", r"\bapplication\s+developer\b", r"\bpython\s+developer\b",
    r"\bjavascript\s+developer\b", r"\breact\b", r"\bnode\.?js\b", r"\bnext\.?js\b",
    r"\bflutter\b", r"\bdjango\b", r"\bflask\b",
    r"\bai\b", r"\bmachine\s+learning\b", r"\bml\s+engineer\b", r"\bdata\s+scientist\b",
    r"\bdata\s+engineer\b", r"\bllm\b", r"\bnlp\b", r"\bdeep\s+learning\b",
    r"\bdevops\b", r"\bsre\b", r"\bcloud\s+engineer\b",
    r"\bsde\b", r"\bmember\s+of\s+technical\s+staff\b", r"\bmts\b",
    r"\bsoftware\s+architect\b", r"\bplatform\s+engineer\b", r"\bsite\s+reliability\b",
    r"\binfrastructure\s+engineer\b", r"\bdata\s+analyst\b", r"\banalytics\s+engineer\b",
    r"\bsolutions\s+architect\b", r"\bgolang\b", r"\bjava\b", r"\bc\+\+\b",
    r"\bengineering\b",
]

EXCLUDE_TITLE_PATTERNS = [
    r"\bsales\b", r"\bmarketing\b", r"\brecruiter\b", r"\bhr\b",
    r"\baccount\s+manager\b", r"\bcontent\s+writer\b",
    r"\bvideo\s+editor\b", r"\bgrowth\b", r"\bintern\b",
    r"\bmanager\b", r"\bdirector\b", r"\bprincipal\b", r"\bstaff\b",
    r"\bvp\b", r"\bchief\b", r"\bhead\b", r"\bdistinguished\b",
    r"\bsenior\b", r"\bsr\.\b", r"\blead\b",
    r"\bpartner\b", r"\bpremier\b",
]

SENIORITY_EXCLUSIONS = [
    r"\bprincipal\b", r"\bstaff\b", r"\bdirector\b", r"\bvp\b",
    r"\bchief\b", r"\bhead\b", r"\bdistinguished\b",
]

EXPERIENCE_PATTERNS = [
    re.compile(r"(\d+)\s*(?:-|to)\s*(\d+)\s*(?:years?|yrs?)\b", re.IGNORECASE),
    re.compile(r"(\d+)\s*\+\s*(?:years?|yrs?)\b", re.IGNORECASE),
    re.compile(r"(?:minimum|at least|require)\s*(?:of)?\s*(\d+)\s*(?:years?|yrs?)\b", re.IGNORECASE),
    re.compile(r"(\d+)\s*(?:years?|yrs?)\s*(?:of)?\s*(?:experience|relevant)\b", re.IGNORECASE),
]


def clean_html(html_text: str) -> str:
    if not html_text:
        return ""
    return re.sub(r"<[^>]+>", " ", html_text)


def is_hyderabad_location(location: str, description: str = "") -> bool:
    loc_lower = location.lower() if location else ""
    desc_lower = description.lower() if description else ""

    hyderabad_indicators = [
        "hyderabad", "hyd", "secunderabad", "hitech city", "hitec city",
        "gachibowli", "madhapur", "kondapur", "kukatpally", "begumpet",
        "banjara hills", "jubilee hills", "ameerpet", "telangana",
    ]

    india_remote = ["india", "remote - india", "remote (india)", "remote, india", "bangalore or hyderabad"]

    for ind in hyderabad_indicators:
        if ind in loc_lower or ind in desc_lower:
            return True

    for ind in india_remote:
        if ind in loc_lower:
            return True

    return False


def is_matching_role(title: str) -> bool:
    title_lower = title.lower()

    for pattern in EXCLUDE_TITLE_PATTERNS:
        if re.search(pattern, title_lower):
            return False

    for pattern in SENIORITY_EXCLUSIONS:
        if re.search(pattern, title_lower):
            return False

    for keyword in ROLE_KEYWORDS:
        if re.search(keyword, title_lower):
            return True

    return False


def parse_experience_personal(description: str, title: str = "") -> Tuple[bool, str]:
    title_lower = title.lower()
    desc_clean = clean_html(description)

    if any(re.search(pat, title_lower) for pat in SENIORITY_EXCLUSIONS):
        return False, "Senior leadership role"

    found_years = []
    experience_mentions = []

    for pattern in EXPERIENCE_PATTERNS:
        matches = pattern.findall(desc_clean)
        for match in matches:
            if isinstance(match, tuple):
                val1, val2 = match
                if val1:
                    found_years.append(int(val1))
                    if val2:
                        found_years.append(int(val2))
                        experience_mentions.append(f"{val1}-{val2} years")
                    else:
                        experience_mentions.append(f"{val1}+ years")
            else:
                if match:
                    found_years.append(int(match))
                    experience_mentions.append(f"{match} years")

    if found_years:
        min_exp = min(found_years)
        if min_exp > 4:
            return False, f"Requires {min_exp}+ yrs (too senior)"
        return True, ", ".join(experience_mentions[:2])

    if "senior" in title_lower or "sr." in title_lower or "lead" in title_lower:
        return False, "Senior title (assumed > 3 yrs)"

    return True, "Not specified (fresher-friendly)"


def filter_personal_job(job: Dict[str, Any]) -> Tuple[bool, str, Dict[str, Any]]:
    title = job.get("title", "")
    location = job.get("location", "")
    description = job.get("description", "")

    if not is_hyderabad_location(location, description):
        return False, "Not in Hyderabad/India", job

    if not is_matching_role(title):
        return False, "Not a matching role", job

    is_exp_match, exp_reason = parse_experience_personal(description, title)
    if not is_exp_match:
        return False, f"Experience out of range: {exp_reason}", job

    enriched_job = job.copy()
    enriched_job["experience_metadata"] = exp_reason

    return True, "Matches criteria", enriched_job
