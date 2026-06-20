# 🇺🇸 Cyber Security Job Aggregator MVP

An automated daily job aggregator that scrapes careers boards of target companies, filters for US-based Cyber Security roles matching 1–6 years of experience, deduplicates against historical runs (last 90 days), applies a company diversity filter, formats a premium styled Excel sheet, and sends it via email.

## 🛠️ Features

1. **Dual Scrapers**:
   - Direct APIs for Greenhouse and Lever ATS boards (extremely fast, no browser load).
   - Playwright browser fallback for custom careers sites.
2. **Dynamic Filtering**:
   - Location checking (US/USA/Remote US).
   - Regex-based Cyber Security keyword checking.
   - Text parsing of experience requirements (limits to 1–6 years).
   - Optional validation using Google Gemini AI.
3. **Advanced Deduplication**:
   - Prevents duplicate job alerts by matching unique signatures (`company::title` & `apply_link`) from previous Excel runs stored in `data/history/` for the past 90 days.
4. **Company Diversity Filter**:
   - Ensures no company dominates the sheet by picking the **single best job** per company (ranking via scoring heuristics).
5. **Styled Excel Output**:
   - Table formats with Segoe UI, alternating rows, custom row heights, and active hyperlinks.
6. **Automation-ready**:
   - Fully automated daily triggers via GitHub Actions or local cron.

---

## 📂 Folder Structure

```
automate-scraper/
├── .github/workflows/
│   └── scrape.yml         # Daily automation trigger (5:00 PM UTC)
├── config/
│   ├── companies.json     # Curated company list (ATS platforms and details)
│   └── settings.py        # Pipeline configuration & variables
├── data/
│   └── history/           # History directory for generated daily Excel sheets
├── src/
│   ├── scrapers/          # Scraper classes (Base, Greenhouse, Lever, Playwright)
│   ├── filters/           # Filtering parsers (regex & optional AI validations)
│   ├── storage/           # History and duplication manager
│   ├── reporting/         # Excel designer and SMTP Email Client
│   └── orchestrator.py    # Pipeline controller
├── .env.example           # Environment template
├── main.py                # Main executable script
└── requirements.txt       # Dependencies
```

---

## 🚀 Setup & Execution

### 1. Prerequisite Installation
Ensure Python 3.10+ is installed, then install dependencies:
```bash
pip install -r requirements.txt
python -m playwright install chromium
```

### 2. Configure Environment variables
Create a `.env` file in the root directory:
```bash
copy .env.example .env
```
Fill in your SMTP and recipient details:
- **SMTP_HOST**: Server address (e.g., `smtp.gmail.com` for Gmail).
- **SMTP_PORT**: Standard TLS port `587`.
- **SMTP_USER**: Sender email address.
- **SMTP_PASSWORD**: App password (not your normal password; generate an App Password in Gmail Account Settings).
- **EMAIL_TO**: Recipient email address.
- **GEMINI_API_KEY**: (Optional) For AI filtering. Set `USE_AI_FILTER=true` to enable.

### 3. Run the Aggregator
Run the main script to fetch jobs, filter them, generate the Excel sheet under `data/history/`, and send the email:
```bash
python main.py
```

---

## 🦾 Automation with GitHub Actions

To automate this pipeline on GitHub:
1. Commit and push this codebase to a private repository.
2. In your GitHub repository: Go to **Settings > Secrets and variables > Actions**.
3. Create the following Repository Secrets matching your `.env` settings:
   - `SMTP_HOST`
   - `SMTP_PORT`
   - `SMTP_USER`
   - `SMTP_PASSWORD`
   - `EMAIL_TO`
   - `EMAIL_FROM` (Optional)
   - `GEMINI_API_KEY` (Optional)
   - `USE_AI_FILTER` (Set to `true` if utilizing Gemini)
4. Go to the **Actions** tab in GitHub to run manually or wait for the automatic daily trigger at 5:00 PM UTC (10:30 PM IST).
5. The runner will commit the generated Excel report back into the repository under `data/history/` to maintain the 90-day history.
