import logging
import requests
from typing import List, Dict, Any
from src.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)


class AshbyScraper(BaseScraper):
    def scrape(self) -> List[Dict[str, Any]]:
        jobs_list = []
        url = f"https://api.ashbyhq.com/posting-api/job-board/{self.token}"

        try:
            logger.info(f"Fetching Ashby jobs for {self.company_name} using token: {self.token}")
            response = requests.get(url, timeout=15)

            if response.status_code != 200:
                logger.warning(f"Failed to fetch Ashby board for {self.company_name}. Status code: {response.status_code}")
                return []

            data = response.json()
            jobs = data.get("jobs", [])

            for job in jobs:
                title = job.get("title", "").strip()
                location = job.get("location", "").strip()
                apply_link = job.get("jobUrl", "").strip()
                description = job.get("descriptionPlain", "").strip()
                published_at = job.get("publishedAt", "")

                date_posted = published_at[:10] if published_at else ""

                jobs_list.append({
                    "company": self.company_name,
                    "title": title,
                    "location": location,
                    "apply_link": apply_link,
                    "description": description,
                    "date_posted": date_posted,
                })

            logger.info(f"Successfully scraped {len(jobs_list)} jobs for {self.company_name} from Ashby.")
        except Exception as e:
            logger.error(f"Error scraping Ashby for {self.company_name}: {str(e)}", exc_info=True)

        return jobs_list
