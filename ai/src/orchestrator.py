import json
import logging
from typing import List, Dict, Any
from config import settings
from src.scrapers import GreenhouseScraper, LeverScraper, AshbyScraper, PlaywrightScraper
from src.filters import filter_job, verify_job_with_ai
from src.storage import load_history_signatures, is_duplicate_job
from src.reporting import generate_styled_excel, send_email_with_report

logger = logging.getLogger(__name__)

# All domains the pipeline tracks and reports on separately.
DOMAINS = ["cyber", "data", "java", "dotnet"]

def rate_job_relevance(job: Dict[str, Any]) -> int:
    """
    Heuristic to score job relevance. Helps in selecting the best job
    per company for the diversity filter.
    """
    title_lower = job.get("title", "").lower()
    score = 0
    
    # Prefer engineers and analysts
    if "engineer" in title_lower:
        score += 15
    if "analyst" in title_lower:
        score += 12
    if "specialist" in title_lower:
        score += 10
    if "consultant" in title_lower:
        score += 8
    if "architect" in title_lower:
        score += 5
        
    # Demote internships/co-ops if full-time positions are available
    if "intern" in title_lower or "co-op" in title_lower or "student" in title_lower:
        score -= 20
        
    # Minor boost for specific cyber fields
    if "application" in title_lower or "appsec" in title_lower:
        score += 2
    if "cloud" in title_lower:
        score += 2
    if "penetration" in title_lower or "pentest" in title_lower:
        score += 3
    if "soc" in title_lower or "operations" in title_lower:
        score += 2
        
    return score

def run_pipeline() -> bool:
    logger.info("Initializing Cyber Security Job Aggregator Pipeline...")

    # 0. Auto-discover new companies using Claude AI
    try:
        from src.company_discovery import discover_new_companies, update_companies_file
        new_companies = discover_new_companies(target_count=30)
        if new_companies:
            added = update_companies_file(new_companies)
            logger.info(f"Auto-discovery: added {added} new companies to database.")
        else:
            logger.info("Auto-discovery: no new companies found this run.")
    except Exception as e:
        logger.warning(f"Company auto-discovery failed (non-fatal): {str(e)}")

    # 1. Load Company Database from Database (PostgreSQL)
    try:
        import sys
        from pathlib import Path
        ai_dir = str(Path(__file__).resolve().parent.parent)
        if ai_dir not in sys.path:
            sys.path.append(ai_dir)
        from db import SessionLocal, Company
        db = SessionLocal()
        db_companies = db.query(Company).all()
        all_companies = [
            {
                "name": c.name,
                "ats": c.ats,
                "token": c.token,
                "careers_url": c.careers_url
            }
            for c in db_companies
        ]
        db.close()
        logger.info(f"Loaded {len(all_companies)} companies from PostgreSQL database.")
    except Exception as db_err:
        logger.warning(f"Failed to load companies from database: {str(db_err)}. Falling back to companies.json.")
        if not settings.COMPANIES_JSON_PATH.exists():
            logger.error(f"Companies JSON file not found at {settings.COMPANIES_JSON_PATH}")
            return False
        with open(settings.COMPANIES_JSON_PATH, "r") as f:
            all_companies = json.load(f)

    companies = all_companies
    logger.info(f"Scraping all {len(companies)} companies.")
    
    # 2. Load Excel History for Deduplication (Last 90 Days) & Company Cooldown (Last 14 Days = Alternate Weeks)
    # All three are dicts keyed by domain (cyber/data/java/dotnet) — see src/storage/history.py
    seen_titles_companies, seen_links, recent_companies = load_history_signatures(settings.COMPANY_COOLDOWN_DAYS)
    for domain in DOMAINS:
        logger.info(f"[{domain}] Alternate Week Filter: {len(recent_companies[domain])} companies featured within the last {settings.COMPANY_COOLDOWN_DAYS} days will be skipped.")

    # 3. Scrape Jobs from all configured companies
    raw_jobs: List[Dict[str, Any]] = []

    for comp in companies:
        name = comp.get("name")
        ats_type = comp.get("ats", "").lower()
        token = comp.get("token")
        careers_url = comp.get("careers_url", "")

        scraper = None
        if ats_type == "greenhouse":
            scraper = GreenhouseScraper(name, token, careers_url)
        elif ats_type == "lever":
            scraper = LeverScraper(name, token, careers_url)
        elif ats_type == "ashby":
            scraper = AshbyScraper(name, token, careers_url)
        else:
            scraper = PlaywrightScraper(name, token, careers_url)

        try:
            company_jobs = scraper.scrape()
            raw_jobs.extend(company_jobs)
        except Exception as e:
            logger.error(f"Failed to run scraper for {name}: {str(e)}", exc_info=True)

    logger.info(f"Collected a total of {len(raw_jobs)} raw jobs from all scrapers.")

    # 4. Regex Filter: classifies each job into a domain (cyber/data/java/dotnet), applies
    # per-domain company cooldown + dedup + USA + experience checks.
    regex_passed_by_domain: Dict[str, List[Dict[str, Any]]] = {d: [] for d in DOMAINS}

    for job in raw_jobs:
        comp_name_lower = job.get("company", "").strip().lower()

        # Core Criteria Filter (USA + Domain classification + 1-6 Years Exp)
        is_match, reason, enriched_job = filter_job(job)
        if not is_match:
            continue

        domain = enriched_job["domain"]

        # Check: Company Cooldown (Alternate Weeks / 14 Days), scoped to this domain
        if comp_name_lower in recent_companies[domain]:
            logger.debug(f"[{domain}] Skipping {job.get('company')}: featured in email digest within last {settings.COMPANY_COOLDOWN_DAYS} days.")
            continue

        # Check: Duplicate check (history), scoped to this domain
        if is_duplicate_job(enriched_job, seen_titles_companies[domain], seen_links[domain]):
            continue

        regex_passed_by_domain[domain].append(enriched_job)

    for domain in DOMAINS:
        logger.info(f"[{domain}] Regex filter passed: {len(regex_passed_by_domain[domain])} jobs.")

    # How many jobs to forward per company to Claude for validation
    # Setting to 2 gives Claude more candidates per company, helping reach 30-35 final jobs
    JOBS_PER_COMPANY_FOR_CLAUDE = 2

    final_selection_by_domain: Dict[str, List[Dict[str, Any]]] = {}

    for domain in DOMAINS:
        regex_passed = regex_passed_by_domain[domain]

        # 5. Company Diversity Filter BEFORE Claude (pick best N jobs per company)
        # This prevents Claude from analyzing 10 Datadog jobs when only 1 will be used.
        jobs_by_company: Dict[str, List[Dict[str, Any]]] = {}
        for job in regex_passed:
            comp_name = job["company"]
            jobs_by_company.setdefault(comp_name, []).append(job)

        pre_diversity_jobs: List[Dict[str, Any]] = []
        for comp_name, comp_jobs in jobs_by_company.items():
            sorted_comp_jobs = sorted(comp_jobs, key=rate_job_relevance, reverse=True)
            top_jobs = sorted_comp_jobs[:JOBS_PER_COMPANY_FOR_CLAUDE]
            pre_diversity_jobs.extend(top_jobs)
            if len(comp_jobs) > 1:
                logger.info(
                    f"[{domain}] Pre-Claude: Picked top {len(top_jobs)} job(s) for {comp_name} "
                    f"from {len(comp_jobs)} candidates."
                )

        logger.info(f"[{domain}] Sending {len(pre_diversity_jobs)} jobs to Claude for validation (top {JOBS_PER_COMPANY_FOR_CLAUDE} per company).")

        # 6. Claude AI Filter (domain-aware prompt — see src/filters/ai_filter.py)
        valid_jobs: List[Dict[str, Any]] = []
        for enriched_job in pre_diversity_jobs:
            if settings.USE_AI_FILTER and settings.CLAUDE_API_KEY:
                ai_match, ai_reason = verify_job_with_ai(enriched_job)
                if not ai_match:
                    logger.info(f"[{domain}] Claude rejected: '{enriched_job['title']}' at {enriched_job['company']}")
                    continue
                enriched_job["experience_metadata"] = f"{enriched_job['experience_metadata']} | {ai_reason}"

            valid_jobs.append(enriched_job)

        logger.info(f"[{domain}] After Claude AI filter: {len(valid_jobs)} jobs approved.")

        # 7. Final Company Diversity Enforcement (1 best Claude-approved job per company)
        final_by_company: Dict[str, Dict[str, Any]] = {}
        for job in valid_jobs:
            comp = job["company"]
            if comp not in final_by_company or rate_job_relevance(job) > rate_job_relevance(final_by_company[comp]):
                final_by_company[comp] = job

        diverse_final = list(final_by_company.values())
        logger.info(f"[{domain}] After final diversity enforcement: {len(diverse_final)} unique companies with approved jobs.")

        # 8. Sort by newest first and select top 40 jobs
        def get_sort_key(j: Dict[str, Any]) -> str:
            return j.get("date_posted", "") or "0000-00-00"

        sorted_jobs = sorted(diverse_final, key=get_sort_key, reverse=True)
        final_selection_by_domain[domain] = sorted_jobs[:40]
        logger.info(f"[{domain}] Selected {len(final_selection_by_domain[domain])} jobs for report generation.")

    if not any(final_selection_by_domain.values()):
        logger.warning("No new matching jobs were found today in any domain. Excel file creation skipped.")
        return True

    # 9. Generate an Excel Report per domain (domains with no jobs are skipped)
    excel_paths_by_domain: Dict[str, str] = {}
    for domain in DOMAINS:
        jobs = final_selection_by_domain[domain]
        if not jobs:
            logger.info(f"[{domain}] No matching jobs today — skipping Excel generation for this domain.")
            continue
        try:
            excel_paths_by_domain[domain] = generate_styled_excel(jobs, domain=domain)
        except Exception as e:
            logger.error(f"[{domain}] Error creating Excel report: {str(e)}", exc_info=True)

    if not excel_paths_by_domain:
        logger.warning("No Excel reports were generated today.")
        return True

    # 10. Send one Email Alert with all domain reports attached
    try:
        send_email_with_report(excel_paths_by_domain, final_selection_by_domain)
    except Exception as e:
        logger.error(f"Error during email dispatch: {str(e)}", exc_info=True)
        # Even if email fails, Excel files are saved in history so pipeline succeeded

    logger.info("Pipeline executed successfully.")
    return True

def scrape_try_all(company_name: str, token: str, careers_url: str) -> tuple:
    """
    Tries each available scraper (Greenhouse, Lever, Ashby) in sequence using the provided token,
    and returns the first one that successfully returns valid jobs. Falls back to Playwright if all fail.
    Returns:
        (successful_ats_type, jobs_list)
    """
    # 1. Greenhouse
    if token:
        try:
            logger.info(f"Orchestration try-all: attempting Greenhouse for {company_name} using token {token}")
            scraper = GreenhouseScraper(company_name, token, careers_url)
            jobs = scraper.scrape()
            if jobs:
                return "greenhouse", jobs
        except Exception as e:
            logger.warning(f"Orchestration try-all: Greenhouse failed for {company_name}: {e}")

    # 2. Lever
    if token:
        try:
            logger.info(f"Orchestration try-all: attempting Lever for {company_name} using token {token}")
            scraper = LeverScraper(company_name, token, careers_url)
            jobs = scraper.scrape()
            if jobs:
                return "lever", jobs
        except Exception as e:
            logger.warning(f"Orchestration try-all: Lever failed for {company_name}: {e}")

    # 3. Ashby
    if token:
        try:
            logger.info(f"Orchestration try-all: attempting Ashby for {company_name} using token {token}")
            scraper = AshbyScraper(company_name, token, careers_url)
            jobs = scraper.scrape()
            if jobs:
                return "ashby", jobs
        except Exception as e:
            logger.warning(f"Orchestration try-all: Ashby failed for {company_name}: {e}")

    # 4. Playwright fallback
    if careers_url:
        try:
            logger.info(f"Orchestration try-all: attempting Playwright fallback for {company_name} using URL {careers_url}")
            scraper = PlaywrightScraper(company_name, token, careers_url)
            jobs = scraper.scrape()
            if jobs:
                return "playwright", jobs
            
            # If Playwright runs but returns no cyber jobs, check if URL is reachable (HTTP 200)
            # as general reachability counts as a successful setup for custom sites.
            import requests
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            resp = requests.get(careers_url, headers=headers, timeout=10, allow_redirects=True)
            if resp.status_code == 200:
                logger.info(f"Orchestration try-all: Playwright URL is reachable, but no cyber jobs found today. Saving as playwright.")
                return "playwright", []
        except Exception as e:
            logger.warning(f"Orchestration try-all: Playwright failed for {company_name}: {e}")

    return None, []
