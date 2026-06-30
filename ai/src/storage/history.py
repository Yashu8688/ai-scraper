import re
import logging
import datetime
from pathlib import Path
from typing import Set, Tuple
import pandas as pd
from config import settings

logger = logging.getLogger(__name__)

def parse_date_from_filename(filename: str) -> datetime.date:
    """
    Parses date from filename pattern CyberJobs_DDMMYYYY.xlsx or CyberJobs_DDMMYYYY_v2.xlsx.
    Returns None if pattern doesn't match or date is invalid.
    """
    # Match base name with optional _v2, _v3 suffixes
    match = re.search(r"CyberJobs_(\d{2})(\d{2})(\d{4})", filename)
    if match:
        day, month, year = match.groups()
        try:
            return datetime.date(int(year), int(month), int(day))
        except ValueError:
            pass
    return None

def load_history_signatures() -> Tuple[Set[str], Set[str]]:
    """
    Scans the history directory for Excel sheets generated in the last 90 days.
    Loads job listings and extracts signatures to prevent duplicates.
    
    Returns:
        Tuple[Set[str], Set[str]]: (set of lowercase_title_company, set of apply_links)
    """
    seen_titles_companies = set()
    seen_links = set()
    
    history_dir = settings.HISTORY_DIR
    if not history_dir.exists():
        logger.info(f"History directory {history_dir} does not exist yet. Creating it.")
        history_dir.mkdir(parents=True, exist_ok=True)
        return seen_titles_companies, seen_links
        
    cutoff_date = datetime.date.today() - datetime.timedelta(days=7)
    excel_files = list(history_dir.glob("CyberJobs_*.xlsx"))
    
    logger.info(f"Scanning {len(excel_files)} Excel history files in {history_dir}")
    
    for file_path in excel_files:
        filename = file_path.name
        file_date = parse_date_from_filename(filename)
        
        # Fallback to file modification time if filename parsing fails
        if not file_date:
            mtime = file_path.stat().st_mtime
            file_date = datetime.date.fromtimestamp(mtime)
            
        # Only process files within the last 90 days
        if file_date >= cutoff_date:
            try:
                # Read with header=3 because Excel has a 3-row title block
                # before the actual column headers (row 4 = index 3)
                df = pd.read_excel(file_path, engine="openpyxl", header=3)
                
                # Normalize column names to lowercase to prevent minor spelling discrepancies
                df.columns = [col.strip().lower() for col in df.columns]
                
                # Check for needed columns
                has_company = "company" in df.columns
                has_title = "job title" in df.columns or "title" in df.columns
                has_link = "apply link" in df.columns or "link" in df.columns
                
                # Resolve specific column mappings
                company_col = "company" if has_company else None
                title_col = "job title" if "job title" in df.columns else ("title" if "title" in df.columns else None)
                link_col = "apply link" if "apply link" in df.columns else ("link" if "link" in df.columns else None)
                
                for _, row in df.iterrows():
                    # 1. Deduplicate by Apply Link
                    if link_col:
                        link_val = str(row[link_col]).strip()
                        if link_val and link_val != "nan":
                            seen_links.add(link_val.lower())
                            
                    # 2. Deduplicate by Title + Company
                    if company_col and title_col:
                        comp_val = str(row[company_col]).strip().lower()
                        title_val = str(row[title_col]).strip().lower()
                        if comp_val and title_val and comp_val != "nan" and title_val != "nan":
                            signature = f"{comp_val}::{title_val}"
                            seen_titles_companies.add(signature)
                            
                logger.info(f"Successfully loaded history from {filename}")
            except Exception as e:
                logger.error(f"Failed to read history from {filename}: {str(e)}")
                
    logger.info(f"Loaded {len(seen_links)} links and {len(seen_titles_companies)} title-company pairs from last 90 days.")
    return seen_titles_companies, seen_links

def is_duplicate_job(job: dict, seen_titles_companies: Set[str], seen_links: Set[str]) -> bool:
    """
    Checks if a job already exists in the 90-day history.
    """
    title = job.get("title", "").strip().lower()
    company = job.get("company", "").strip().lower()
    apply_link = job.get("apply_link", "").strip().lower()
    
    # 1. Check exact link match
    if apply_link in seen_links:
        return True
        
    # 2. Check title + company match
    signature = f"{company}::{title}"
    if signature in seen_titles_companies:
        return True
        
    return False
