import datetime
import json
import logging
from pathlib import Path
from typing import List, Dict, Any
from config import settings
from db import save_domain_report
from src.scrapers import GreenhouseScraper, LeverScraper, AshbyScraper, WorkdayScraper, PlaywrightScraper
from src.filters import filter_job, verify_job_with_ai
from src.storage import load_history_signatures, is_duplicate_job, purge_expired_history
from src.reporting import generate_styled_excel, send_email_with_report

logger = logging.getLogger(__name__)

# All domains the pipeline tracks and reports on separately.
DOMAINS = ["cyber", "data", "java", "dotnet"]

# Target size of every domain's Excel sheet. Each row is a distinct company, so these are
# also the minimum/maximum number of unique companies per sheet. When the 14-day company
# cooldown leaves a sheet short of the minimum, cooled-down companies are pulled back in
# (see the top-up step in run_pipeline) rather than shipping a thin report.
MIN_JOBS_PER_SHEET = 30
MAX_JOBS_PER_SHEET = 40

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
    
    # 2a. Purge expired history first, so a company whose report just aged out is eligible today.
    # Retention must cover the cooldown window, otherwise the cooldown data would be deleted
    # before it could ever apply.
    cooldown_days = settings.COMPANY_COOLDOWN_DAYS
    retention_days = max(settings.HISTORY_RETENTION_DAYS, cooldown_days)
    if retention_days != settings.HISTORY_RETENTION_DAYS:
        logger.warning(
            f"HISTORY_RETENTION_DAYS ({settings.HISTORY_RETENTION_DAYS}) is shorter than "
            f"COMPANY_COOLDOWN_DAYS ({cooldown_days}); using {retention_days} days for both."
        )
    purge_expired_history(retention_days)

    # 2b. Load Excel History for Deduplication & Company Cooldown.
    # All three are dicts keyed by domain (cyber/data/java/dotnet) — see src/storage/history.py
    seen_titles_companies, seen_links, recent_companies = load_history_signatures(cooldown_days, retention_days)
    # NOTE: Company cooldown is disabled below (see the "Soft filter" comment in the loop
    # further down) — recent_companies is still computed here so re-enabling it later is just
    # uncommenting, but it is not used to skip anything right now.
    for domain in DOMAINS:
        logger.info(f"[{domain}] Alternate Week Filter: {len(recent_companies[domain])} companies featured within the last {settings.COMPANY_COOLDOWN_DAYS} days (cooldown enforcement currently disabled).")

    # 3. Scrape Jobs from all configured companies.
    #
    # Companies on a real ATS API (Greenhouse/Lever/Ashby/Workday) are scraped sequentially —
    # each is a single fast HTTP call. Companies without one of those ("playwright") fall back
    # to PlaywrightScraper, which — unlike the old removed version that treated any <a> tag as
    # a job (see git history) — only extracts real schema.org JobPosting structured data and
    # returns nothing rather than guessing when a site has none. Since that involves a real
    # headless-browser page load per company, those run as a separate, concurrent batch so a
    # few hundred of them don't turn into hours of sequential wall-clock time.
    raw_jobs: List[Dict[str, Any]] = []
    API_SCRAPERS = {
        "greenhouse": GreenhouseScraper,
        "lever": LeverScraper,
        "ashby": AshbyScraper,
        "workday": WorkdayScraper,
    }
    PLAYWRIGHT_CONCURRENCY = 6

    skipped_companies: List[str] = []
    scraped_count = 0
    playwright_companies = []

    for comp in companies:
        name = comp.get("name")
        ats_type = (comp.get("ats") or "").lower().strip()
        token = (comp.get("token") or "").strip()
        careers_url = comp.get("careers_url", "")

        if ats_type == "playwright":
            if careers_url:
                playwright_companies.append(comp)
            else:
                skipped_companies.append(f"{name} (ats=playwright, careers_url=missing)")
            continue

        scraper_cls = API_SCRAPERS.get(ats_type)
        if not scraper_cls or not token:
            skipped_companies.append(f"{name} (ats={ats_type or 'none'}, token={'yes' if token else 'missing'})")
            continue

        try:
            company_jobs = scraper_cls(name, token, careers_url).scrape()
            raw_jobs.extend(company_jobs)
            scraped_count += 1
        except Exception as e:
            logger.error(f"Failed to run scraper for {name}: {str(e)}", exc_info=True)

    if playwright_companies:
        import concurrent.futures

        def _scrape_playwright(comp):
            try:
                return comp.get("name"), PlaywrightScraper(comp.get("name"), "", comp.get("careers_url", "")).scrape()
            except Exception as e:
                logger.error(f"Failed to run Playwright scraper for {comp.get('name')}: {str(e)}", exc_info=True)
                return comp.get("name"), []

        with concurrent.futures.ThreadPoolExecutor(max_workers=PLAYWRIGHT_CONCURRENCY) as executor:
            for name, company_jobs in executor.map(_scrape_playwright, playwright_companies):
                if company_jobs:
                    raw_jobs.extend(company_jobs)
                    scraped_count += 1
        logger.info(f"Playwright tier: attempted {len(playwright_companies)} companies with no supported ATS API.")

    logger.info(f"Collected a total of {len(raw_jobs)} raw jobs from {scraped_count} ATS-backed companies.")
    if skipped_companies:
        logger.warning(
            f"Skipped {len(skipped_companies)} companies with no usable ATS API token. "
            f"Add a greenhouse/lever/ashby token via the dashboard to include them. "
            f"First 10: {skipped_companies[:10]}"
        )

    # 4. Regex Filter: classifies each job into a domain (cyber/data/java/dotnet), applies
    # per-domain dedup + USA + experience checks.
    #
    # Jobs are split into two tiers. The company cooldown (14 days) is a *preference*, not a
    # hard filter: if enforcing it would push a sheet below MIN_JOBS_PER_SHEET, cooled-down
    # companies are added back to top the sheet up. The duplicate check stays a hard filter —
    # a link that already went out must never be repeated.
    regex_passed_by_domain: Dict[str, List[Dict[str, Any]]] = {d: [] for d in DOMAINS}
    cooldown_reserve_by_domain: Dict[str, List[Dict[str, Any]]] = {d: [] for d in DOMAINS}

    for job in raw_jobs:
        # --- Company cooldown disabled per request: a company can now show up again the very
        # next day if it has a new/different role — only the exact same link (or the same
        # title+company pair) is still permanently blocked, via is_duplicate_job below, which
        # is untouched. comp_name_lower was only used by the cooldown check, so it's commented
        # out with it. To restore cooldown, uncomment this line and the "Soft filter" block.
        # comp_name_lower = job.get("company", "").strip().lower()

        # Core Criteria Filter (USA + Domain classification + 1-6 Years Exp)
        is_match, reason, enriched_job = filter_job(job)
        if not is_match:
            continue

        domain = enriched_job["domain"]

        # Hard filter: never repeat a link/title+company still inside the retention window.
        if is_duplicate_job(enriched_job, seen_titles_companies[domain], seen_links[domain]):
            continue

        # Soft filter: company featured within the cooldown window goes to the reserve pool.
        # --- Disabled (see comment above). Restore by uncommenting this block.
        # if comp_name_lower in recent_companies[domain]:
        #     cooldown_reserve_by_domain[domain].append(enriched_job)
        #     continue

        regex_passed_by_domain[domain].append(enriched_job)

    for domain in DOMAINS:
        logger.info(
            f"[{domain}] Regex filter passed: {len(regex_passed_by_domain[domain])} jobs "
            f"({len(cooldown_reserve_by_domain[domain])} more held in cooldown reserve)."
        )

    # How many jobs to forward per company to Claude for validation
    # Setting to 2 gives Claude more candidates per company, helping reach the sheet minimum
    JOBS_PER_COMPANY_FOR_CLAUDE = 2

    def select_one_per_company(jobs: List[Dict[str, Any]], exclude: set) -> List[Dict[str, Any]]:
        """Keeps only the single highest-rated job per company, skipping excluded companies."""
        best_by_company: Dict[str, Dict[str, Any]] = {}
        for job in jobs:
            comp = job["company"]
            if comp in exclude:
                continue
            if comp not in best_by_company or rate_job_relevance(job) > rate_job_relevance(best_by_company[comp]):
                best_by_company[comp] = job
        return list(best_by_company.values())

    def run_claude_filter(domain: str, jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Validates candidates with the domain-aware Claude prompt (no-op if AI filter is off)."""
        if not (settings.USE_AI_FILTER and settings.CLAUDE_API_KEY):
            return list(jobs)

        approved: List[Dict[str, Any]] = []
        for job in jobs:
            ai_match, ai_reason = verify_job_with_ai(job)
            if not ai_match:
                logger.info(f"[{domain}] Claude rejected: '{job['title']}' at {job['company']}")
                continue
            job["experience_metadata"] = f"{job['experience_metadata']} | {ai_reason}"
            approved.append(job)
        return approved

    def cap_per_company(jobs: List[Dict[str, Any]], limit: int) -> List[Dict[str, Any]]:
        """Forwards at most `limit` best-rated jobs per company to Claude."""
        by_company: Dict[str, List[Dict[str, Any]]] = {}
        for job in jobs:
            by_company.setdefault(job["company"], []).append(job)

        capped: List[Dict[str, Any]] = []
        for comp_jobs in by_company.values():
            capped.extend(sorted(comp_jobs, key=rate_job_relevance, reverse=True)[:limit])
        return capped

    def sort_newest_first(jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return sorted(jobs, key=lambda j: j.get("date_posted", "") or "0000-00-00", reverse=True)

    final_selection_by_domain: Dict[str, List[Dict[str, Any]]] = {}

    for domain in DOMAINS:
        # 5-7. Cap per company -> Claude validation -> one job per company.
        primary = cap_per_company(regex_passed_by_domain[domain], JOBS_PER_COMPANY_FOR_CLAUDE)
        logger.info(f"[{domain}] Sending {len(primary)} jobs to Claude (top {JOBS_PER_COMPANY_FOR_CLAUDE} per company).")

        approved = run_claude_filter(domain, primary)
        logger.info(f"[{domain}] After Claude AI filter: {len(approved)} jobs approved.")

        selected = select_one_per_company(approved, exclude=set())
        logger.info(f"[{domain}] {len(selected)} unique companies after diversity enforcement.")

        # 8. Top-up: if the cooldown left this sheet short of the minimum, pull the best
        # cooled-down companies back in (newest first) until the sheet reaches MIN_JOBS_PER_SHEET.
        # NOTE: cooldown_reserve_by_domain is always empty now that the cooldown soft-filter
        # above is disabled, so this block is currently inert. Restore the cooldown filter to
        # bring it back.
        if len(selected) < MIN_JOBS_PER_SHEET and cooldown_reserve_by_domain[domain]:
            shortfall = MIN_JOBS_PER_SHEET - len(selected)
            used_companies = {j["company"] for j in selected}
            logger.info(
                f"[{domain}] Only {len(selected)} companies available (minimum is {MIN_JOBS_PER_SHEET}). "
                f"Topping up from {len(cooldown_reserve_by_domain[domain])} cooled-down candidates."
            )

            reserve = cap_per_company(cooldown_reserve_by_domain[domain], JOBS_PER_COMPANY_FOR_CLAUDE)
            # Only validate as many reserve companies as we plausibly need, newest first.
            reserve = sort_newest_first(reserve)[: max(shortfall * 3, shortfall)]

            reserve_approved = run_claude_filter(domain, reserve)
            topped_up = select_one_per_company(reserve_approved, exclude=used_companies)
            topped_up = sort_newest_first(topped_up)[:shortfall]

            selected.extend(topped_up)
            logger.info(f"[{domain}] Added {len(topped_up)} cooled-down companies to reach {len(selected)}.")

        final_selection_by_domain[domain] = sort_newest_first(selected)[:MAX_JOBS_PER_SHEET]

        count = len(final_selection_by_domain[domain])
        if count < MIN_JOBS_PER_SHEET:
            logger.warning(
                f"[{domain}] Only {count} jobs available — below the {MIN_JOBS_PER_SHEET} minimum. "
                f"Add more {domain} companies with ATS tokens via the dashboard to raise this."
            )
        logger.info(f"[{domain}] Selected {count} jobs for report generation.")

    if not any(final_selection_by_domain.values()):
        logger.warning("No new matching jobs were found today in any domain. Excel file creation skipped.")
        return True

    # 9. Generate an Excel Report per domain (domains with no jobs are skipped), and persist
    # each one to the database so the dashboard can resend the latest report for a domain
    # on demand (see api_server.py's /domain-reports endpoints).
    excel_paths_by_domain: Dict[str, str] = {}
    for domain in DOMAINS:
        jobs = final_selection_by_domain[domain]
        if not jobs:
            logger.info(f"[{domain}] No matching jobs today — skipping Excel generation for this domain.")
            continue
        try:
            excel_path = generate_styled_excel(jobs, domain=domain)
            excel_paths_by_domain[domain] = excel_path
        except Exception as e:
            logger.error(f"[{domain}] Error creating Excel report: {str(e)}", exc_info=True)
            continue

        try:
            file_bytes = Path(excel_path).read_bytes()
            save_domain_report(
                domain=domain,
                report_date=datetime.date.today(),
                filename=Path(excel_path).name,
                file_bytes=file_bytes,
                job_count=len(jobs),
            )
            logger.info(f"[{domain}] Persisted today's report to the database ({len(file_bytes)} bytes).")
        except Exception as e:
            logger.error(f"[{domain}] Failed to persist report to database: {str(e)}", exc_info=True)

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
    Tries each ATS API scraper (Greenhouse, Lever, Ashby) in sequence using the provided token
    and returns the first one that returns valid jobs.

    There is deliberately no browser fallback: scraping a raw careers page yielded nav links
    rather than real listings (see the note in run_pipeline). A company that matches no ATS
    here returns (None, []) so the caller can report that a valid token is required.

    Returns:
        (successful_ats_type, jobs_list) — (None, []) if no ATS API matched.
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

    logger.warning(
        f"Orchestration try-all: no ATS API matched for {company_name}. "
        f"A valid Greenhouse, Lever, or Ashby token is required for it to be scraped daily."
    )
    return None, []
