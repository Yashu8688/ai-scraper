import re
import logging
import datetime
from pathlib import Path
from typing import Dict, Set, Tuple
import pandas as pd
from config import settings

logger = logging.getLogger(__name__)

# Filename prefix -> domain, used for history scanning and per-domain dedup/cooldown.
HISTORY_FILE_PREFIX_TO_DOMAIN = {
    "CyberJobs": "cyber",
    "DataJobs": "data",
    "JavaJobs": "java",
    "DotNetJobs": "dotnet",
}

def parse_date_from_filename(filename: str) -> datetime.date:
    """
    Parses date from filename pattern <Prefix>_DDMMYYYY.xlsx or <Prefix>_DDMMYYYY_v2.xlsx,
    where <Prefix> is one of HISTORY_FILE_PREFIX_TO_DOMAIN keys.
    Returns None if pattern doesn't match or date is invalid.
    """
    # Match base name with optional _v2, _v3 suffixes
    prefix_group = "|".join(HISTORY_FILE_PREFIX_TO_DOMAIN.keys())
    match = re.search(rf"(?:{prefix_group})_(\d{{2}})(\d{{2}})(\d{{4}})", filename)
    if match:
        day, month, year = match.groups()
        try:
            return datetime.date(int(year), int(month), int(day))
        except ValueError:
            pass
    return None

def purge_expired_history(retention_days: int) -> int:
    """
    Deletes history Excel files older than `retention_days`.

    This is what makes a company/link eligible again: once its report file is deleted,
    its links and company name are no longer loaded as history, so the same company can
    be featured again. Runs before history is loaded so the purge takes effect the same day.

    Returns:
        int: number of files deleted.
    """
    history_dir = settings.HISTORY_DIR
    if not history_dir.exists():
        return 0

    cutoff = datetime.date.today() - datetime.timedelta(days=retention_days)
    deleted = 0

    for prefix in HISTORY_FILE_PREFIX_TO_DOMAIN:
        for file_path in history_dir.glob(f"{prefix}_*.xlsx"):
            file_date = parse_date_from_filename(file_path.name)
            if not file_date:
                file_date = datetime.date.fromtimestamp(file_path.stat().st_mtime)

            if file_date < cutoff:
                try:
                    file_path.unlink()
                    deleted += 1
                    logger.info(f"Purged expired history file: {file_path.name} (dated {file_date})")
                except OSError as e:
                    logger.error(f"Could not delete expired history file {file_path.name}: {e}")

    if deleted:
        logger.info(f"History retention: deleted {deleted} file(s) older than {retention_days} days.")
    else:
        logger.info(f"History retention: no files older than {retention_days} days to purge.")
    return deleted

def load_history_signatures(company_cooldown_days: int = 14, retention_days: int = None) -> Tuple[Dict[str, Set[str]], Dict[str, Set[str]], Dict[str, Set[str]]]:
    """
    Scans the history directory for Excel sheets inside the retention window, per domain.
    Loads job listings and extracts signatures to prevent duplicates.
    Also tracks companies featured in the last `company_cooldown_days` (default 14 days for alternate weeks).
    All tracking is scoped per domain, so a company appearing in one domain's report
    (e.g. a Java role) does not suppress it from another domain's report (e.g. a Data role).

    Returns:
        Tuple[Dict[str, Set[str]], Dict[str, Set[str]], Dict[str, Set[str]]]:
            (domain -> set of lowercase_title_company, domain -> set of apply_links, domain -> set of recent_company_names)
    """
    seen_titles_companies: Dict[str, Set[str]] = {d: set() for d in HISTORY_FILE_PREFIX_TO_DOMAIN.values()}
    seen_links: Dict[str, Set[str]] = {d: set() for d in HISTORY_FILE_PREFIX_TO_DOMAIN.values()}
    recent_companies: Dict[str, Set[str]] = {d: set() for d in HISTORY_FILE_PREFIX_TO_DOMAIN.values()}

    history_dir = settings.HISTORY_DIR
    if not history_dir.exists():
        logger.info(f"History directory {history_dir} does not exist yet. Creating it.")
        history_dir.mkdir(parents=True, exist_ok=True)
        return seen_titles_companies, seen_links, recent_companies

    # Dedup window == retention window. Files older than this are purged by
    # purge_expired_history(), so scanning a longer window here would have no effect.
    if retention_days is None:
        retention_days = settings.HISTORY_RETENTION_DAYS
    cutoff_date = datetime.date.today() - datetime.timedelta(days=retention_days)
    cooldown_cutoff_date = datetime.date.today() - datetime.timedelta(days=company_cooldown_days)

    files_with_domain = []
    for prefix, domain in HISTORY_FILE_PREFIX_TO_DOMAIN.items():
        for file_path in history_dir.glob(f"{prefix}_*.xlsx"):
            files_with_domain.append((file_path, domain))

    logger.info(f"Scanning {len(files_with_domain)} Excel history files in {history_dir}")

    for file_path, domain in files_with_domain:
        filename = file_path.name
        file_date = parse_date_from_filename(filename)

        # Fallback to file modification time if filename parsing fails
        if not file_date:
            mtime = file_path.stat().st_mtime
            file_date = datetime.date.fromtimestamp(mtime)

        # Only process files within the retention window
        if file_date >= cutoff_date:
            try:
                # Read with header=3 because Excel has a 3-row title block
                # before the actual column headers (row 4 = index 3)
                df = pd.read_excel(file_path, engine="openpyxl", header=3)

                # Normalize column names to lowercase to prevent minor spelling discrepancies
                df.columns = [col.strip().lower() for col in df.columns]

                # Check for needed columns
                has_company = "company" in df.columns

                # Resolve specific column mappings
                company_col = "company" if has_company else None
                title_col = "job title" if "job title" in df.columns else ("title" if "title" in df.columns else None)
                link_col = "apply link" if "apply link" in df.columns else ("link" if "link" in df.columns else None)

                is_within_cooldown = file_date >= cooldown_cutoff_date

                for _, row in df.iterrows():
                    # 1. Deduplicate by Apply Link
                    if link_col:
                        link_val = str(row[link_col]).strip()
                        if link_val and link_val != "nan":
                            seen_links[domain].add(link_val.lower())

                    # 2. Deduplicate by Title + Company & Track Recent Companies
                    if company_col:
                        comp_val = str(row[company_col]).strip().lower()
                        if comp_val and comp_val != "nan":
                            if is_within_cooldown:
                                recent_companies[domain].add(comp_val)

                            if title_col:
                                title_val = str(row[title_col]).strip().lower()
                                if title_val and title_val != "nan":
                                    signature = f"{comp_val}::{title_val}"
                                    seen_titles_companies[domain].add(signature)

                logger.info(f"Successfully loaded history from {filename} (domain={domain})")
            except Exception as e:
                logger.error(f"Failed to read history from {filename}: {str(e)}")

    total_links = sum(len(v) for v in seen_links.values())
    total_titles = sum(len(v) for v in seen_titles_companies.values())
    total_recent = sum(len(v) for v in recent_companies.values())
    logger.info(f"Loaded {total_links} links, {total_titles} title-company pairs (last {retention_days}d), and {total_recent} companies featured in the last {company_cooldown_days} days (across all domains).")
    return seen_titles_companies, seen_links, recent_companies

def is_duplicate_job(job: dict, seen_titles_companies: Set[str], seen_links: Set[str]) -> bool:
    """
    Checks if a job already exists in the 90-day history for its domain.
    Callers must pass the per-domain sets (e.g. seen_titles_companies[domain]).
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
