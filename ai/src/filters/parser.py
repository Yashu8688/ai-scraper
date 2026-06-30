import re
import logging
from typing import Dict, Any, Tuple

logger = logging.getLogger(__name__)

# Keywords that indicate a Cyber Security role
SECURITY_KEYWORDS = [
    r"\bsecurity\b", r"\bcyber\b", r"\bcybersecurity\b", r"\binfosec\b", 
    r"\bsecops\b", r"\bsoc\b", r"\bpentest\b", r"\bpenetration\b", 
    r"\bvulnerability\b", r"\biam\b", r"\bgrc\b", r"\bcompliance\b", 
    r"\bthreat\b", r"\bincident\b", r"\bsiem\b", r"\bcryptography\b"
]

# Title patterns to exclude (false positives and non-cyber roles)
EXCLUDE_TITLE_PATTERNS = [
    r"\bsecurities\b",
    r"\bphysical security\b",
    r"\bguard\b",
    r"\bofficer\b",
    r"\bloss prevention\b",
    r"\bfood security\b",
    r"\bhome security\b",
    r"\bsales\b",
    r"\baccount\s+executive\b",
    r"\bchannel\b",
    r"\bbrand\b",
    r"\bmarketing\b",
    r"\bcounsel\b",
    r"\battorney\b",
    r"\blegal\b",
    r"\brecruiter\b",
    r"\badministrative\b",
    r"\bfellowship\b",
    r"\bskillbridge\b",
    r"\bvice\s+president\b",
    r"\barea\s+vice\b",
    r"\bstaff\b",
    r"\bprincipal\b",
    r"\bdirector\b",
    r"\bhead\s+of\b",
    r"\bchief\b",
    r"\bgroup\s+product\b",
]

# Experience regexes
# Matches: "3-5 years", "3+ years", "minimum of 2 years", "1 to 6 years", "4 yrs", etc.
EXPERIENCE_PATTERNS = [
    re.compile(r"(\d+)\s*(?:-|to)\s*(\d+)\s*(?:years?|yrs?)\b", re.IGNORECASE),
    re.compile(r"(\d+)\s*\+\s*(?:years?|yrs?)\b", re.IGNORECASE),
    re.compile(r"(?:minimum|at least|requried|require)\s*(?:of)?\s*(\d+)\s*(?:years?|yrs?)\b", re.IGNORECASE),
    re.compile(r"(\d+)\s*(?:years?|yrs?)\s*(?:of)?\s*(?:experience|relevant)\b", re.IGNORECASE)
]

# Exclusions for senior roles that exceed 6 years
SENIORITY_EXCLUSIONS = [
    r"\bsenior\b", r"\bsr\.\b", r"\bprincipal\b", r"\blead\b", 
    r"\bdirector\b", r"\bmanager\b", r"\bvp\b", r"\bhead\b", r"\bchief\b"
]

def clean_html(html_text: str) -> str:
    """Removes HTML tags from a text block."""
    if not html_text:
        return ""
    clean = re.compile("<.*?>")
    return re.sub(clean, " ", html_text)

def is_usa_location(location: str, description: str = "") -> bool:
    """Checks if the job location is in the United States."""
    if not location:
        # Check description for explicit US mentions if location is missing
        desc_lower = description.lower()
        return "united states" in desc_lower or "remote (us)" in desc_lower or "us-based" in desc_lower

    loc_lower = location.lower()
    
    # Common US location indicators
    us_indicators = [
        "us", "usa", "united states", "america", "remote, us", "remote (us)", "remote - us",
        "al", "ak", "az", "ar", "ca", "co", "ct", "de", "fl", "ga", "hi", "id", "il", "in", "ia",
        "ks", "ky", "la", "me", "md", "ma", "mi", "mn", "ms", "mo", "mt", "ne", "nv", "nh", "nj",
        "nm", "ny", "nc", "nd", "oh", "ok", "or", "pa", "ri", "sc", "sd", "tn", "tx", "ut", "vt",
        "va", "wa", "wv", "wi", "wy"
    ]
    
    # Check if location matches standard indicators
    # Break into words or parts to avoid matching substrings like "india" matching "in"
    parts = [p.strip(",. ") for p in re.split(r"[\s/]+", loc_lower)]
    
    # Explicit check for international locations that might conflict
    international_exclusions = ["uk", "united kingdom", "canada", "ca (canada)", "india", "in (india)", "germany", "de (germany)", "london", "munich", "berlin", "bangalore"]
    
    if any(ex in loc_lower for ex in international_exclusions):
        # Double check if it's dual-listed or truly international
        if "us" not in parts and "usa" not in parts and "united states" not in loc_lower:
            return False
            
    # Check if parts contain US state codes or country name
    for part in parts:
        if part in ["us", "usa", "united states"]:
            return True
        # For state codes, match exactly as separate token
        if len(part) == 2 and part in us_indicators:
            return True
            
    # Standard string search check
    if any(ind in loc_lower for ind in ["united states", "remote - us", "remote (us)", "remote, us", "united states of america"]):
        return True
        
    return False

def is_cyber_security_role(title: str) -> bool:
    """Checks if the job title matches cyber security roles and avoids exclusions."""
    title_lower = title.lower()
    
    # Check for title exclusion patterns first
    for pattern in EXCLUDE_TITLE_PATTERNS:
        if re.search(pattern, title_lower):
            return False
            
    # Check for security keywords in title
    for keyword in SECURITY_KEYWORDS:
        if re.search(keyword, title_lower):
            return True
            
    return False

def parse_experience(description: str, title: str = "") -> Tuple[bool, str]:
    """
    Parses experience required from the job description.
    Returns:
        Tuple[bool, str]: (is_within_range, extracted_experience_string)
        
    Range: 1 to 6 years.
    """
    title_lower = title.lower()
    desc_clean = clean_html(description)
    desc_lower = desc_clean.lower()
    
    # First heuristic: Check title for seniority level. 
    # If the title is "Senior ...", "Principal ...", "Lead ...", "Director ...", 
    # it is highly likely to require more than 6 years of experience.
    # However, some companies call 5-6 years "Senior". So we still parse the description,
    # but we flag it if there's no experience text found.
    is_senior_title = any(re.search(pat, title_lower) for pat in SENIORITY_EXCLUSIONS)
    
    # Find all mentions of years of experience in the description
    found_years = []
    experience_mentions = []
    
    for pattern in EXPERIENCE_PATTERNS:
        matches = pattern.findall(desc_clean)
        for match in matches:
            if isinstance(match, tuple):
                # E.g. ("3", "5") or ("3", "")
                val1, val2 = match
                if val1:
                    found_years.append(int(val1))
                    if val2:
                        found_years.append(int(val2))
                        experience_mentions.append(f"{val1}-{val2} years")
                    else:
                        experience_mentions.append(f"{val1}+ years")
            else:
                # E.g. "3"
                if match:
                    found_years.append(int(match))
                    experience_mentions.append(f"{match} years")
                    
    # If we extracted years, let's analyze if they fit within 1-6 years
    if found_years:
        max_exp = max(found_years)
        min_exp = min(found_years)
        
        # If the minimum experience required is greater than 6, reject
        if min_exp > 6:
            return False, f"Requires {min_exp}+ yrs (exceeds 6 yrs)"

        # If the maximum experience requested is greater than 8 and title is senior, reject
        if max_exp > 8 and is_senior_title:
            return False, f"Requires {max_exp} yrs (Senior/Principal)"
            
        return True, ", ".join(experience_mentions[:2])
        
    # Heuristic fallback: If no years of experience mentioned in description
    if is_senior_title:
        # Senior / Principal titles with no exp details might be 8+ years, reject to be safe for 1-6 MVP
        # But "Lead" / "Manager" are definitely out of range
        if any(w in title_lower for w in ["principal", "director", "manager", "chief", "head", "vp"]):
            return False, "Senior leadership role (assumed > 6 yrs)"
        return True, "Assumed mid-level senior"
        
    return True, "Not specified (Assumed 1-6 yrs)"

def filter_job(job: Dict[str, Any]) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Applies the full verification pipeline to a single job.
    Returns:
        Tuple[bool, str, Dict[str, Any]]: (is_match, reason, job_with_metadata)
    """
    title = job.get("title", "")
    location = job.get("location", "")
    description = job.get("description", "")
    
    # 1. Location check
    if not is_usa_location(location, description):
        return False, "Not in USA", job
        
    # 2. Security role check
    if not is_cyber_security_role(title):
        return False, "Not a Cyber Security role", job
        
    # 3. Experience check
    is_exp_match, exp_reason = parse_experience(description, title)
    if not is_exp_match:
        return False, f"Experience out of range: {exp_reason}", job
        
    # Enrich job dictionary with parsed metadata
    enriched_job = job.copy()
    enriched_job["experience_metadata"] = exp_reason
    
    return True, "Matches criteria", enriched_job
