import logging
from typing import Tuple, Dict, Any
from config import settings

logger = logging.getLogger(__name__)

# Domain-specific recruiter persona + role criteria, injected into the shared prompt template
DOMAIN_CRITERIA = {
    "cyber": {
        "persona": "expert cybersecurity recruiter",
        "role_label": "CYBER SECURITY ROLE",
        "role_rules": (
            "   - ACCEPT: AppSec, Cloud Security, SOC, Penetration Testing, IAM, GRC, Compliance, Incident Response, "
            "Threat Intelligence, SecOps, Security Engineering, SIEM, Vulnerability Management, Cryptography, DevSecOps.\n"
            "   - REJECT: Physical Security Guard, Food Safety, IT Helpdesk (non-security), Generic Software Engineer, Sales, Marketing, HR."
        ),
    },
    "data_analyst": {
        "persona": "expert data/BI analytics recruiter",
        "role_label": "DATA ANALYST ROLE",
        "role_rules": (
            "   - ACCEPT: Data Analyst, Business Intelligence Analyst/Developer, Reporting Analyst, "
            "roles centered on Tableau, Power BI, Looker, or SQL-based reporting/analysis.\n"
            "   - REJECT: Data Entry Clerk, generic Software Engineer with no data focus, Sales/Marketing Analyst without "
            "technical data work, and any role that's really Data Engineering (building pipelines/ETL/data platforms) rather than analysis/reporting."
        ),
    },
    "data_engineer": {
        "persona": "expert data engineering recruiter",
        "role_label": "DATA ENGINEER ROLE",
        "role_rules": (
            "   - ACCEPT: Data Engineer, Analytics Engineer, ETL/ELT Developer, Data Warehouse Engineer, Data Platform Engineer, "
            "roles centered on Databricks, Snowflake, dbt, Spark, Airflow, or building/maintaining data pipelines.\n"
            "   - REJECT: Data Entry Clerk, generic Software Engineer with no data focus, ML Research Scientist (unless clearly "
            "data engineering), and any role that's really a Data Analyst/BI reporting role rather than pipeline/platform engineering."
        ),
    },
    "java": {
        "persona": "expert Java recruiter",
        "role_label": "JAVA DEVELOPER ROLE",
        "role_rules": (
            "   - ACCEPT: Java Developer/Engineer, Backend Engineer using Java/Spring Boot/J2EE/Jakarta EE, Java Microservices Engineer.\n"
            "   - REJECT: Roles where Java is only listed as one of many unrelated skills, JavaScript/frontend-only roles, non-engineering roles."
        ),
    },
    "dotnet": {
        "persona": "expert .NET recruiter",
        "role_label": ".NET DEVELOPER ROLE",
        "role_rules": (
            "   - ACCEPT: .NET Developer/Engineer, C# Developer, ASP.NET / .NET Core Engineer, Blazor Developer.\n"
            "   - REJECT: Roles where .NET/C# is only a minor listed skill, non-engineering roles, unrelated software engineer roles without .NET focus."
        ),
    },
}

# Shared Claude prompt template for all job evaluations
CLAUDE_PROMPT_TEMPLATE = """You are an {persona} with 10+ years of hiring experience at US tech companies.

Evaluate the following job listing against ALL three criteria:

CRITERIA:
1. USA LOCATION: Is this job located in the United States? Remote-US is OK. International-only roles (UK, India, Europe, Canada, etc.) must be rejected.
2. {role_label}: Is this a legitimate role in this domain?
{role_rules}
3. EXPERIENCE LEVEL (1-6 YEARS): Does the role target 1–6 years of experience?
   - ACCEPT: Junior, Mid-level, or roles requiring 1-6 years.
   - REJECT: Internships (0 years), or roles clearly requiring 7+ years (VP, Distinguished Engineer, Staff Principal with 10+ years).

JOB DETAILS:
Company: {company}
Title: {title}
Location: {location}
Description (first 2000 chars):
{description}

RESPONSE FORMAT (strict — 2 lines only):
Line 1: MATCH or NO_MATCH
Line 2: One sentence reason."""


def verify_job_with_ai(job: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Validates a job using Claude claude-3-5-haiku-20241022 (fast + cheap) to verify:
    1. Is it a cyber security role?
    2. Is it in the USA?
    3. Is experience level 1-6 years?

    Falls back to True (accept) if API is unavailable or disabled.

    Returns:
        Tuple[bool, str]: (is_match, reason_string)
    """
    # Guard: Skip AI filter if not configured
    if not settings.USE_AI_FILTER:
        return True, "AI filter disabled"

    if not settings.CLAUDE_API_KEY:
        logger.warning("USE_AI_FILTER=true but CLAUDE_API_KEY is not set. Skipping AI check.")
        return True, "No API key — relying on rule-based filter"

    try:
        import anthropic

        client = anthropic.Anthropic(api_key=settings.CLAUDE_API_KEY)

        # Clean HTML from description before sending to Claude
        import re
        description_raw = job.get("description", "")
        description_clean = re.sub(r"<[^>]+>", " ", description_raw)
        description_clean = re.sub(r"\s+", " ", description_clean).strip()

        domain = job.get("domain", "cyber")
        criteria = DOMAIN_CRITERIA.get(domain, DOMAIN_CRITERIA["cyber"])

        prompt = CLAUDE_PROMPT_TEMPLATE.format(
            persona=criteria["persona"],
            role_label=criteria["role_label"],
            role_rules=criteria["role_rules"],
            company=job.get("company", "Unknown"),
            title=job.get("title", "Unknown"),
            location=job.get("location", "Unknown"),
            description=description_clean[:2000],
        )

        logger.info(
            f"[Claude] Analyzing: '{job.get('title')}' at {job.get('company')}"
        )

        # Model priority list — tries newest first, falls back to universally available
        CLAUDE_MODELS = [
            "claude-haiku-4-5",            # Latest Haiku (if available on plan)
            "claude-3-5-haiku-20241022",   # Previous Haiku
            "claude-3-haiku-20240307",     # Baseline — universally available
        ]

        response_text = None
        for model_name in CLAUDE_MODELS:
            try:
                message = client.messages.create(
                    model=model_name,
                    max_tokens=100,
                    messages=[{"role": "user", "content": prompt}],
                )
                response_text = message.content[0].text.strip()
                logger.debug(f"[Claude] Used model: {model_name}")
                break  # Success — stop trying
            except Exception as model_err:
                if "not_found_error" in str(model_err) or "404" in str(model_err):
                    logger.warning(f"[Claude] Model '{model_name}' not available, trying next...")
                    continue
                raise  # Re-raise non-model errors immediately
        if response_text is None:
            logger.warning("[Claude] All models failed or unavailable. Defaulting to MATCH.")
            return True, "Claude unavailable — fallback to rule-based"

        lines = [line.strip() for line in response_text.split("\n") if line.strip()]

        if not lines:
            logger.warning("[Claude] Empty response received. Defaulting to MATCH.")
            return True, "Empty Claude response — defaulting to accept"

        decision_line = lines[0].upper()
        reason = lines[1] if len(lines) > 1 else "No reason provided"

        if "NO_MATCH" in decision_line:
            logger.info(f"[Claude] REJECTED '{job.get('title')}': {reason}")
            return False, f"Claude: {reason}"

        logger.info(f"[Claude] ACCEPTED '{job.get('title')}': {reason}")
        return True, f"Claude: {reason}"

    except anthropic.AuthenticationError:
        logger.error("[Claude] Authentication failed — check your CLAUDE_API_KEY in .env")
        return True, "Claude auth error — fallback to rule-based"

    except anthropic.RateLimitError:
        logger.warning("[Claude] Rate limit hit. Falling back to rule-based filter.")
        return True, "Claude rate limit — fallback to rule-based"

    except Exception as e:
        logger.error(f"[Claude] Unexpected error: {str(e)}", exc_info=True)
        return True, f"Claude error fallback: {str(e)[:80]}"
