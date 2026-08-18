import re
import json
import time
import logging
from typing import List, Dict, Any, Optional
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from src.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

_LDJSON_PATTERN = re.compile(r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>', re.S | re.I)

# Conservative job-detail URL shapes only — never "any link with a keyword in it"
# (that heuristic is what made the old scraper produce nav-menu links as fake jobs).
_JOB_LINK_PATTERN = re.compile(r"/(?:job|jobs|position|positions|req|opening|openings)/[^\"'#?]*[A-Za-z0-9_-]", re.I)

PAGE_TIMEOUT_MS = 20000
COMPANY_BUDGET_SECONDS = 55
MAX_DETAIL_PAGES = 30


def _extract_job_postings(html: str) -> List[Dict[str, Any]]:
    """Parses every JSON-LD block on a page and returns any real schema.org JobPosting
    objects found (handles plain object, array, and @graph-wrapped forms). Never guesses —
    a page with no valid JobPosting markup contributes nothing."""
    postings = []
    for raw in _LDJSON_PATTERN.findall(html):
        try:
            data = json.loads(raw.strip())
        except (json.JSONDecodeError, ValueError):
            continue

        candidates = []
        if isinstance(data, dict) and "@graph" in data and isinstance(data["@graph"], list):
            candidates.extend(data["@graph"])
        elif isinstance(data, list):
            candidates.extend(data)
        else:
            candidates.append(data)

        for item in candidates:
            if isinstance(item, dict) and item.get("@type") in ("JobPosting", ["JobPosting"]):
                postings.append(item)
    return postings


def _location_from_posting(posting: Dict[str, Any]) -> str:
    loc = posting.get("jobLocation")
    if isinstance(loc, list):
        loc = loc[0] if loc else None
    if isinstance(loc, dict):
        address = loc.get("address")
        if isinstance(address, dict):
            parts = [address.get("addressLocality"), address.get("addressRegion"), address.get("addressCountry")]
            return ", ".join(p for p in parts if p)
    if posting.get("jobLocationType") == "TELECOMMUTE" or posting.get("applicantLocationRequirements"):
        return "Remote"
    return ""


def _posting_to_job(company_name: str, posting: Dict[str, Any], fallback_url: str) -> Optional[Dict[str, Any]]:
    title = (posting.get("title") or "").strip()
    if not title:
        return None
    apply_link = posting.get("url") or posting.get("mainEntityOfPage") or fallback_url
    if isinstance(apply_link, dict):
        apply_link = apply_link.get("@id") or fallback_url
    return {
        "company": company_name,
        "title": title,
        "location": _location_from_posting(posting),
        "apply_link": apply_link,
        "description": (posting.get("description") or "")[:5000],
        "date_posted": (posting.get("datePosted") or "")[:10],
    }


class PlaywrightScraper(BaseScraper):
    """
    Fallback scraper for companies not on Greenhouse/Lever/Ashby/Workday. Unlike the earlier
    removed version (which treated any <a> tag containing a keyword as a job — see the note in
    src/orchestrator.py), this only extracts real schema.org JobPosting structured data (the
    same markup Google Jobs relies on). A company with no such data anywhere returns an empty
    list rather than a guessed result.
    """

    def scrape(self) -> List[Dict[str, Any]]:
        jobs: List[Dict[str, Any]] = []
        if not self.careers_url:
            return jobs

        start = time.monotonic()

        def time_left() -> float:
            return COMPANY_BUDGET_SECONDS - (time.monotonic() - start)

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                try:
                    try:
                        page.goto(self.careers_url, timeout=PAGE_TIMEOUT_MS, wait_until="networkidle")
                    except PlaywrightTimeoutError:
                        page.goto(self.careers_url, timeout=PAGE_TIMEOUT_MS, wait_until="domcontentloaded")

                    listing_html = page.content()
                    listing_postings = _extract_job_postings(listing_html)
                    if listing_postings:
                        for posting in listing_postings:
                            job = _posting_to_job(self.company_name, posting, page.url)
                            if job:
                                jobs.append(job)
                        browser.close()
                        logger.info(f"PlaywrightScraper: {self.company_name} — {len(jobs)} jobs from listing-page structured data.")
                        return jobs

                    # No structured data on the listing page itself — look for candidate
                    # job-detail links and check each one for its own structured data.
                    hrefs = page.eval_on_selector_all("a[href]", "els => els.map(e => e.href)")
                    candidate_links = []
                    seen = set()
                    for href in hrefs:
                        if href in seen:
                            continue
                        seen.add(href)
                        if _JOB_LINK_PATTERN.search(href):
                            candidate_links.append(href)
                    candidate_links = candidate_links[:MAX_DETAIL_PAGES]

                    for link in candidate_links:
                        if time_left() <= 3:
                            logger.info(f"PlaywrightScraper: {self.company_name} — time budget exhausted, stopping early.")
                            break
                        detail_page = browser.new_page()
                        try:
                            detail_page.goto(link, timeout=min(PAGE_TIMEOUT_MS, max(int(time_left() * 1000), 3000)), wait_until="domcontentloaded")
                            detail_html = detail_page.content()
                            for posting in _extract_job_postings(detail_html):
                                job = _posting_to_job(self.company_name, posting, link)
                                if job:
                                    jobs.append(job)
                        except Exception:
                            pass
                        finally:
                            detail_page.close()
                finally:
                    browser.close()
        except Exception as e:
            logger.warning(f"PlaywrightScraper: {self.company_name} failed: {e}")

        logger.info(f"PlaywrightScraper: {self.company_name} — {len(jobs)} jobs from detail-page structured data.")
        return jobs
