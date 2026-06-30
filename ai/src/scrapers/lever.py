import logging
import requests
from typing import List, Dict, Any
from src.scrapers.base import BaseScraper

logger = logging.getLogger(__name__)

class LeverScraper(BaseScraper):
    def scrape(self) -> List[Dict[str, Any]]:
        jobs_list = []
        # Lever API URL
        # E.g. https://api.lever.co/v0/postings/{company_id}
        url = f"https://api.lever.co/v0/postings/{self.token}"
        
        try:
            logger.info(f"Fetching Lever jobs for {self.company_name} using company ID: {self.token}")
            response = requests.get(url, timeout=15)
            
            if response.status_code != 200:
                logger.warning(f"Failed to fetch Lever postings for {self.company_name}. Status code: {response.status_code}")
                return []
                
            postings = response.json()
            
            for post in postings:
                title = post.get("text", "").strip()
                
                # Lever locations can be inside categories or fields
                categories = post.get("categories", {})
                location = categories.get("location", "").strip()
                
                apply_link = post.get("hostedUrl", "").strip()
                
                # Combine description and lists into a single string for parsing
                description_parts = []
                description_parts.append(post.get("descriptionHtml", ""))
                
                # Lever puts responsibilities/requirements in lists lists
                lists = post.get("lists", [])
                for lst in lists:
                    list_text = lst.get("text", "")
                    list_content = lst.get("content", "")
                    description_parts.append(f"<h3>{list_text}</h3>{list_content}")
                    
                description = "\n".join(description_parts).strip()
                
                # Lever dates are timestamps (milliseconds)
                # E.g. 1622548800000 -> "2021-06-01"
                created_at = post.get("createdAt", None)
                date_posted = ""
                if created_at:
                    try:
                        import datetime
                        # convert milliseconds timestamp to datetime object
                        dt = datetime.datetime.fromtimestamp(created_at / 1000.0, tz=datetime.timezone.utc)
                        date_posted = dt.strftime("%Y-%m-%d")
                    except Exception:
                        pass
                
                jobs_list.append({
                    "company": self.company_name,
                    "title": title,
                    "location": location,
                    "apply_link": apply_link,
                    "description": description,
                    "date_posted": date_posted
                })
                
            logger.info(f"Successfully scraped {len(jobs_list)} jobs for {self.company_name} from Lever.")
        except Exception as e:
            logger.error(f"Error scraping Lever for {self.company_name}: {str(e)}", exc_info=True)
            
        return jobs_list
