import logging
import requests
from typing import List, Dict, Any
from src.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

class GreenhouseScraper(BaseScraper):
    def scrape(self) -> List[Dict[str, Any]]:
        jobs_list = []
        
        # Greenhouse board API url
        # Passing content=true fetches the job description text under "content"
        url = f"https://boards-api.greenhouse.io/v1/boards/{self.token}/jobs?content=true"
        
        try:
            logger.info(f"Fetching Greenhouse jobs for {self.company_name} using token: {self.token}")
            response = requests.get(url, timeout=15)
            
            if response.status_code != 200:
                logger.warning(f"Failed to fetch Greenhouse board for {self.company_name}. Status code: {response.status_code}")
                return []
                
            data = response.json()
            jobs = data.get("jobs", [])
            
            for job in jobs:
                title = job.get("title", "").strip()
                location = (job.get("location") or {}).get("name") or ""
                location = location.strip()
                apply_link = job.get("absolute_url", "").strip()
                description = job.get("content", "").strip()
                updated_at = job.get("updated_at", "")
                
                # Format date if available
                # E.g. "2026-06-19T10:00:00Z" -> "2026-06-19"
                date_posted = updated_at[:10] if updated_at else ""
                
                jobs_list.append({
                    "company": self.company_name,
                    "title": title,
                    "location": location,
                    "apply_link": apply_link,
                    "description": description,
                    "date_posted": date_posted
                })
                
            logger.info(f"Successfully scraped {len(jobs_list)} jobs for {self.company_name} from Greenhouse.")
        except Exception as e:
            logger.error(f"Error scraping Greenhouse for {self.company_name}: {str(e)}", exc_info=True)
            
        return jobs_list
