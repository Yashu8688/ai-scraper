import re
import logging
import datetime
import requests
from typing import List, Dict, Any
from src.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

# Workday's list endpoint gives a relative string instead of a real date
# (e.g. "Posted Today", "Posted 3 Days Ago", "Posted 30+ Days Ago").
_RELATIVE_DATE_RE = re.compile(r"posted\s+(today|yesterday|(\d+)\+?\s+days?\s+ago)", re.IGNORECASE)


def _parse_relative_posted(text: str) -> str:
    """Converts Workday's relative "Posted X Days Ago" text to a YYYY-MM-DD estimate.
    Needed so these jobs sort correctly against dated jobs from other ATS APIs instead of
    always ranking last (and getting cut from the report) with an empty date."""
    if not text:
        return ""
    match = _RELATIVE_DATE_RE.search(text)
    if not match:
        return ""
    today = datetime.date.today()
    word = match.group(1).lower()
    if word == "today":
        days_ago = 0
    elif word == "yesterday":
        days_ago = 1
    else:
        days_ago = int(match.group(2))
    return (today - datetime.timedelta(days=days_ago)).strftime("%Y-%m-%d")


class WorkdayScraper(BaseScraper):
    """
    Scrapes a company's Workday-hosted job board via its public CXS search API.

    Token format is "{tenant}.{data_center}.{site}" (e.g. "amgen.wd1.Careers") -- all three
    pieces come directly from the company's real careers URL, which Workday-hosted employers
    redirect to a URL shaped like https://{tenant}.{data_center}.myworkdayjobs.com/{site}.
    """
    def scrape(self) -> List[Dict[str, Any]]:
        jobs_list: List[Dict[str, Any]] = []

        parts = (self.token or "").split(".")
        if len(parts) != 3:
            logger.warning(
                f"Workday token for {self.company_name} is malformed (expected "
                f"'tenant.data_center.site'): {self.token!r}"
            )
            return jobs_list
        tenant, data_center, site = parts

        base_url = f"https://{tenant}.{data_center}.myworkdayjobs.com"
        api_url = f"{base_url}/wday/cxs/{tenant}/{site}/jobs"

        limit = 20  # Workday's API rejects anything above 20 with a 400
        offset = 0
        total = None
        # Generous but bounded, so one huge board (some have 1000+ postings) can't blow up
        # the daily run the way the old browser fallback did.
        max_jobs = 500

        try:
            while total is None or (offset < total and offset < max_jobs):
                payload = {"appliedFacets": {}, "limit": limit, "offset": offset, "searchText": ""}
                response = requests.post(api_url, json=payload, timeout=15)

                if response.status_code != 200:
                    logger.warning(
                        f"Failed to fetch Workday board for {self.company_name}. "
                        f"Status code: {response.status_code}"
                    )
                    break

                data = response.json()
                # Workday only reports the real total on the first page -- every later page
                # reports total=0 even though jobPostings still has real results, so only
                # trust it once (offset == 0) or it would silently truncate pagination.
                if offset == 0:
                    total = data.get("total", 0)
                postings = data.get("jobPostings", [])
                if not postings:
                    break

                for job in postings:
                    title = (job.get("title") or "").strip()
                    location = (job.get("locationsText") or "").strip()
                    external_path = job.get("externalPath") or ""
                    apply_link = f"{base_url}/{site}{external_path}" if external_path else ""
                    date_posted = _parse_relative_posted(job.get("postedOn") or "")

                    jobs_list.append({
                        "company": self.company_name,
                        "title": title,
                        "location": location,
                        "apply_link": apply_link,
                        # Workday's list endpoint doesn't include the full description, only
                        # a title/location/posted summary -- fetching it per-job would mean
                        # one extra request per posting, too expensive for boards with
                        # hundreds of roles. Domain/experience filtering falls back to
                        # title-only matching for these, same as before description fallback
                        # existed for other sources.
                        "description": "",
                        "date_posted": date_posted,
                    })

                offset += limit

            logger.info(f"Successfully scraped {len(jobs_list)} jobs for {self.company_name} from Workday.")
        except Exception as e:
            logger.error(f"Error scraping Workday for {self.company_name}: {str(e)}", exc_info=True)

        return jobs_list
