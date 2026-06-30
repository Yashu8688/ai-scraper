import logging
from typing import List, Dict, Any
from src.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

class PlaywrightScraper(BaseScraper):
    def scrape(self) -> List[Dict[str, Any]]:
        jobs_list = []
        # Playwright scraper fallback for custom sites
        logger.info(f"Launching Playwright scraper fallback for {self.company_name} at URL: {self.careers_url}")
        
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            logger.error("playwright package is not installed. Skipping Playwright scraper.")
            return []
            
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                # Create a page with standard user agent to avoid bot blocks
                context = browser.new_context(
                    user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                )
                page = context.new_page()
                page.goto(self.careers_url, wait_until="networkidle", timeout=30000)
                
                # Let's search for all links on the page and filter them
                links = page.query_selector_all("a")
                
                for link in links:
                    try:
                        href = link.get_attribute("href")
                        text = link.inner_text().strip()
                        
                        if not href or not text:
                            continue
                            
                        # Resolve relative links
                        if href.startswith("/"):
                            # Simple concatenation with origin
                            from urllib.parse import urlparse
                            parsed_url = urlparse(self.careers_url)
                            href = f"{parsed_url.scheme}://{parsed_url.netloc}{href}"
                        elif not href.startswith("http"):
                            continue
                            
                        # Filter links to find potential job listings
                        # Look for security keywords in link text
                        text_lower = text.lower()
                        keywords = ["security", "cyber", "information security", "secops", "infosec", "penetration", "compliance"]
                        
                        if any(kw in text_lower for kw in keywords):
                            # It's a potential cyber security job link!
                            jobs_list.append({
                                "company": self.company_name,
                                "title": text,
                                "location": "USA (Verify)",  # Browser extraction fallback
                                "apply_link": href,
                                "description": f"Scraped link text: {text}. See career page for full details.",
                                "date_posted": ""
                            })
                    except Exception:
                        continue
                        
                browser.close()
                logger.info(f"Successfully scraped {len(jobs_list)} potential jobs for {self.company_name} using Playwright.")
        except Exception as e:
            logger.error(f"Error scraping with Playwright for {self.company_name}: {str(e)}", exc_info=True)
            
        return jobs_list
