import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Base directories
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
HISTORY_DIR = DATA_DIR / "history"

# Ensure directories exist
DATA_DIR.mkdir(exist_ok=True)
HISTORY_DIR.mkdir(exist_ok=True)

# Configuration Files
COMPANIES_JSON_PATH = BASE_DIR / "config" / "companies.json"

# Email / SMTP Settings
SMTP_HOST = os.getenv("SMTP_HOST") or "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
EMAIL_TO = os.getenv("EMAIL_TO", "")
EMAIL_FROM = os.getenv("EMAIL_FROM", SMTP_USER)

# Filtering Constants
EXPERIENCE_MIN_YEARS = 1
EXPERIENCE_MAX_YEARS = 6

# Claude AI Settings (Primary AI filter)
CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY", "")
USE_AI_FILTER = os.getenv("USE_AI_FILTER", "false").lower() == "true"

# Gemini (Optional / secondary fallback — not used by default)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
