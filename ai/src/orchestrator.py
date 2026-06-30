import json
import logging
from typing import List, Dict, Any
from config import settings
from src.scrapers import GreenhouseScraper, LeverScraper, AshbyScraper, PlaywrightScraper
from src.filters import filter_job, verify_job_with_ai
from src.storage import load_history_signatures, is_duplicate_job
from src.reporting import generate_styled_excel, send_email_with_report

logger = logging.getLogger(__name__)

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

    # 1. Load Company Database
    if not settings.COMPANIES_JSON_PATH.exists():
        logger.error(f"Companies JSON file not found at {settings.COMPANIES_JSON_PATH}")
        return False

    with open(settings.COMPANIES_JSON_PATH, "r") as f:
        all_companies = json.load(f)

    companies = all_companies
    logger.info(f"Scraping all {len(companies)} companies.")
    
    # 2. Load Excel History for Deduplication (Last 90 Days)
    seen_titles_companies, seen_links = load_history_signatures()
    
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
    
    # 4. Regex Filter: Deduplicate + USA + CyberSec + Experience
    regex_passed: List[Dict[str, Any]] = []

    for job in raw_jobs:
        # Check 1: Duplicate check (history)
        if is_duplicate_job(job, seen_titles_companies, seen_links):
            continue

        # Check 2: Core Criteria Filter (USA + Cyber Security + 1-6 Years Exp)
        is_match, reason, enriched_job = filter_job(job)
        if not is_match:
            continue

        regex_passed.append(enriched_job)

    logger.info(f"Regex filter passed: {len(regex_passed)} jobs from all scrapers.")

    # 5. Company Diversity Filter BEFORE Claude (pick best 1 job per company)
    # This prevents Claude from analyzing 10 Datadog jobs when only 1 will be used.
    jobs_by_company: Dict[str, List[Dict[str, Any]]] = {}
    for job in regex_passed:
        comp_name = job["company"]
        if comp_name not in jobs_by_company:
            jobs_by_company[comp_name] = []
        jobs_by_company[comp_name].append(job)

    # How many jobs to forward per company to Claude for validation
    # Setting to 2 gives Claude more candidates per company, helping reach 30-35 final jobs
    JOBS_PER_COMPANY_FOR_CLAUDE = 2

    pre_diversity_jobs: List[Dict[str, Any]] = []
    for comp_name, comp_jobs in jobs_by_company.items():
        sorted_comp_jobs = sorted(comp_jobs, key=rate_job_relevance, reverse=True)
        # Take top N jobs from this company to send to Claude
        top_jobs = sorted_comp_jobs[:JOBS_PER_COMPANY_FOR_CLAUDE]
        pre_diversity_jobs.extend(top_jobs)
        if len(comp_jobs) > 1:
            logger.info(
                f"Pre-Claude: Picked top {len(top_jobs)} job(s) for {comp_name} "
                f"from {len(comp_jobs)} candidates."
            )

    logger.info(f"Sending {len(pre_diversity_jobs)} jobs to Claude for validation (top {JOBS_PER_COMPANY_FOR_CLAUDE} per company).")

    # 6. Claude AI Filter (1 job per company — efficient & accurate)
    valid_jobs: List[Dict[str, Any]] = []

    for enriched_job in pre_diversity_jobs:
        if settings.USE_AI_FILTER and settings.CLAUDE_API_KEY:
            ai_match, ai_reason = verify_job_with_ai(enriched_job)
            if not ai_match:
                logger.info(f"Claude rejected: '{enriched_job['title']}' at {enriched_job['company']}")
                continue
            enriched_job["experience_metadata"] = f"{enriched_job['experience_metadata']} | {ai_reason}"

        valid_jobs.append(enriched_job)

    logger.info(f"After Claude AI filter: {len(valid_jobs)} jobs approved.")

    # 7. Final Company Diversity Enforcement (1 best Claude-approved job per company)
    final_by_company: Dict[str, Dict[str, Any]] = {}
    for job in valid_jobs:
        comp = job["company"]
        if comp not in final_by_company:
            final_by_company[comp] = job
        else:
            if rate_job_relevance(job) > rate_job_relevance(final_by_company[comp]):
                final_by_company[comp] = job

    diverse_final = list(final_by_company.values())
    logger.info(f"After final diversity enforcement: {len(diverse_final)} unique companies with approved jobs.")

    # 8. Sort by newest first and select top 30-40 jobs
    def get_sort_key(j: Dict[str, Any]) -> str:
        return j.get("date_posted", "") or "0000-00-00"

    sorted_jobs = sorted(diverse_final, key=get_sort_key, reverse=True)

    # Select top 40 jobs for the report
    final_selection = sorted_jobs[:40]
    logger.info(f"Selected top {len(final_selection)} jobs for report generation.")
    
    if not final_selection:
        logger.warning("No new matching jobs were found today. Excel file creation skipped.")
        return True
        
    # 9. Generate Excel Report
    try:
        excel_path = generate_styled_excel(final_selection)
    except Exception as e:
        logger.error(f"Error creating Excel report: {str(e)}", exc_info=True)
        return False
        
    # 10. Send Email Alert
    try:
        send_email_with_report(excel_path, final_selection)
    except Exception as e:
        logger.error(f"Error during email dispatch: {str(e)}", exc_info=True)
        # Even if email fails, Excel is saved in history so pipeline succeeded
        
    logger.info("Pipeline executed successfully.")
    return True
