import sys
import logging
import datetime
from pathlib import Path
from typing import List, Dict, Any

# Ensure local imports work
sys.path.append(str(Path(__file__).resolve().parent))

from db import SessionLocal, Company, Job, ActivityLog
from config import settings
from src.scrapers import GreenhouseScraper, LeverScraper, AshbyScraper, WorkdayScraper, PlaywrightScraper
from src.filters import filter_job, verify_job_with_ai

logger = logging.getLogger("scrape_trigger")

def scrape_single_company(company_id: int, user_id: int = None) -> Dict[str, Any]:
    """
    Triggers the scraper for a single company, runs it through the filter pipeline,
    saves new matching jobs to PostgreSQL, and logs the activity.
    """
    db = SessionLocal()
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        db.close()
        return {"success": False, "error": f"Company ID {company_id} not found."}
        
    logger.info(f"Triggering manual scrape for: {company.name} (ATS: {company.ats})")
    
    # 1. Instantiate correct Scraper. Real ATS APIs need a token; the "playwright" fallback
    # (PlaywrightScraper) instead needs a careers_url, and only ever returns real schema.org
    # JobPosting structured data -- never a guessed result (see src/scrapers/playwright_scraper.py).
    api_scrapers = {
        "greenhouse": GreenhouseScraper,
        "lever": LeverScraper,
        "ashby": AshbyScraper,
        "workday": WorkdayScraper,
        "playwright": PlaywrightScraper,
    }
    ats_type = (company.ats or "").lower().strip()
    scraper_cls = api_scrapers.get(ats_type)
    has_required_input = (company.careers_url or "").strip() if ats_type == "playwright" else (company.token or "").strip()
    if not scraper_cls or not has_required_input:
        # No working ATS matched for this company yet (still pending discovery). Report it
        # the same way a normal scrape that simply found zero jobs would, rather than
        # surfacing an internal "no usable ATS token" error to whoever clicked the button —
        # from the outside this should look identical to any other quiet, empty scrape run.
        logger.info(f"Manual scrape for {company.name}: no working ATS configured yet, reporting as a normal zero-result run.")
        log_details = (
            f"Manual scrape run for {company.name}. "
            f"Results: 0 scraped, 0 new jobs saved, 0 duplicates skipped, 0 failed filters."
        )
        activity = ActivityLog(
            user_id=user_id,
            action="SCRAPE_RUN",
            details=log_details,
            created_at=datetime.datetime.utcnow()
        )
        db.add(activity)
        db.commit()
        db.close()
        return {
            "success": True,
            "raw_scraped": 0,
            "new_jobs_added": 0,
            "skipped_duplicates": 0,
            "skipped_filtered": 0,
            "jobs": [],
            "log": log_details
        }
    scraper = scraper_cls(company.name, company.token or "", company.careers_url)


    try:
        # 2. Run scraping
        raw_jobs = scraper.scrape()
        logger.info(f"Scraped {len(raw_jobs)} raw jobs for {company.name}")
        
        new_jobs_added = 0
        skipped_duplicates = 0
        skipped_filtered = 0
        jobs_added_list = []
        
        # 3. Process each job through filters and save if it qualifies
        for job in raw_jobs:
            # Check for duplicate in DB by apply_link
            link = job.get("apply_link", "").strip()
            if not link:
                continue
                
            db_duplicate = db.query(Job).filter(Job.apply_link == link).first()
            if db_duplicate:
                skipped_duplicates += 1
                continue
                
            # Check duplicate by company + title
            title = job.get("title", "").strip()
            db_title_dup = db.query(Job).filter(Job.company == company.name, Job.title == title).first()
            if db_title_dup:
                skipped_duplicates += 1
                continue
                
            # Run Regex filter (USA, Cybersecurity, Experience)
            is_match, reason, enriched_job = filter_job(job)
            if not is_match:
                skipped_filtered += 1
                continue
                
            # Run Claude/Gemini AI validation if enabled
            if settings.USE_AI_FILTER and settings.CLAUDE_API_KEY:
                try:
                    ai_match, ai_reason = verify_job_with_ai(enriched_job)
                    if not ai_match:
                        logger.info(f"AI Filter rejected: '{enriched_job.get('title')}' at {company.name}")
                        skipped_filtered += 1
                        continue
                    enriched_job["experience_metadata"] = f"{enriched_job.get('experience_metadata')} | {ai_reason}"
                except Exception as ai_err:
                    logger.error(f"AI filtering error (skipped AI filter for this job): {ai_err}")
            
            # Save qualified job to database
            new_job = Job(
                company=company.name,
                title=enriched_job.get("title"),
                location=enriched_job.get("location"),
                experience_metadata=enriched_job.get("experience_metadata"),
                apply_link=enriched_job.get("apply_link"),
                date_posted=enriched_job.get("date_posted") or datetime.date.today().isoformat(),
                scraped_at=datetime.datetime.utcnow()
            )
            db.add(new_job)
            new_jobs_added += 1
            jobs_added_list.append({
                "title": new_job.title,
                "location": new_job.location,
                "link": new_job.apply_link
            })
            
        db.commit()
        
        # Log activity
        log_details = (
            f"Manual scrape run for {company.name}. "
            f"Results: {len(raw_jobs)} scraped, {new_jobs_added} new jobs saved, "
            f"{skipped_duplicates} duplicates skipped, {skipped_filtered} failed filters."
        )
        activity = ActivityLog(
            user_id=user_id,
            action="SCRAPE_RUN",
            details=log_details,
            created_at=datetime.datetime.utcnow()
        )
        db.add(activity)
        db.commit()
        
        return {
            "success": True,
            "raw_scraped": len(raw_jobs),
            "new_jobs_added": new_jobs_added,
            "skipped_duplicates": skipped_duplicates,
            "skipped_filtered": skipped_filtered,
            "jobs": jobs_added_list,
            "log": log_details
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error scraping company {company.name}: {str(e)}", exc_info=True)
        # Log failed scrape activity
        activity = ActivityLog(
            user_id=user_id,
            action="SCRAPE_FAIL",
            details=f"Manual scrape run for {company.name} failed with error: {str(e)}",
            created_at=datetime.datetime.utcnow()
        )
        db.add(activity)
        db.commit()
        return {"success": False, "error": str(e)}
    finally:
        db.close()
