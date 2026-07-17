# Company Admin Portal

Internal tool for the team to add US-based companies to a shared database,
with duplicate rejection, so the daily scraper stops hitting the same
companies over and over.

## What it does

- **Shared-password login** — everyone uses one password, but each person
  types their name at login so entries are still attributed (needed for the
  "3 companies per person per day" tracking).
- **Add company form** with live duplicate checking as you type (name +
  website fuzzy-matched against everything already in the database).
- **Hard rejection of duplicates** on submit, with a message showing who
  already added it and when.
- **Rejects "top-tier" company size** at the API level, per the team's
  targeting rules.
- **Dashboard stats**: total companies, added today, breakdown by teammate
  today, and how many are due to appear in the next export.
- **Rotation-aware export** (`/api/export`): pulls only companies not shown
  in the last `ROTATION_DAYS` (default 14, i.e. "every alternate week"),
  marks them as shown, and leaves full history in the database (nothing is
  ever deleted, satisfying the 3–4 week retention requirement).

## Run it locally

```bash
cd admin-portal
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# edit .env — set ADMIN_PASSWORD to your team's shared password

export $(cat .env | xargs)      # or use python-dotenv / your OS's env setup
uvicorn main:app --reload --port 8000
```

Open http://localhost:8000 — log in with your name and the shared password.

The database is a single SQLite file (`companies.db`) created automatically
on first run. For the weekend demo this is enough; for production, point
`DB_PATH` in `database.py` at a real Postgres instance if you outgrow it
(schema is plain SQL, easy to port).

## Wiring it into the existing scraper

The scraper repo expects `config/companies.json`. Once this portal is
deployed somewhere reachable (even just an internal server or a free Render/
Railway instance), add a step to your existing `.github/workflows/scrape.yml`
**before** the scrape step:

```yaml
- name: Pull today's companies from admin portal
  run: python admin-portal/export_companies.py config/companies.json
  env:
    ADMIN_PORTAL_URL: ${{ secrets.ADMIN_PORTAL_URL }}
    ADMIN_PASSWORD: ${{ secrets.ADMIN_PASSWORD }}
```

That overwrites `config/companies.json` with exactly the companies due for
rotation that day, and the rest of your existing pipeline (Greenhouse/Lever
scrapers, filters, Excel export, email) runs unchanged.

## Deploying so the whole team can reach it

For the Sunday demo, running it on one laptop and sharing your local network
IP is fine. For real daily use, deploy `admin-portal/` to something like
Render, Railway, or a small VM — it's a single FastAPI app with no external
services besides the SQLite file (mount a persistent disk so the DB survives
restarts).

## Notes / things to adjust before Monday

- `board_identifier` field maps to Greenhouse's board token or Lever's
  company slug — confirm the exact field names your `src/scrapers/` classes
  expect and adjust `export_companies.py`'s payload shape if they differ.
- Dedup fuzzy-match threshold is `0.88` in `database.py::find_duplicate` —
  tune it if you see false positives/negatives once real data is in.
- Session tokens last 12 hours (`SESSION_HOURS` in `main.py`) — bump if staff
  get logged out mid-shift.
