from abc import ABC, abstractmethod
from typing import List, Dict, Any

class BaseScraper(ABC):
    def __init__(self, company_name: str, token: str, careers_url: str):
        self.company_name = company_name
        self.token = token
        self.careers_url = careers_url

    @abstractmethod
    def scrape(self) -> List[Dict[str, Any]]:
        """
        Scrapes job listings for the target company.
        
        Returns:
            List[Dict[str, Any]]: A list of dictionaries representing jobs, e.g.:
            [
                {
                    "company": "Company Name",
                    "title": "Cyber Security Engineer",
                    "location": "Remote, US",
                    "apply_link": "https://...",
                    "description": "...",
                    "date_posted": "2026-06-20"
                }
            ]
        """
        pass
