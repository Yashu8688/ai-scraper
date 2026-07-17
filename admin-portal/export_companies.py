"""
Run this daily (e.g. right before your GitHub Action / cron scrape job) to pull
the companies due for rotation out of the admin portal and write them into the
ai-scraper repo's config/companies.json.

Usage:
    ADMIN_PORTAL_URL=http://localhost:8000 \
    ADMIN_TOKEN=<a valid session token, or set STAFF_NAME + ADMIN_PASSWORD below> \
    python export_companies.py /path/to/ai-scraper/config/companies.json

If you don't want to manage a token, this script will log in itself using
ADMIN_PASSWORD + STAFF_NAME.
"""
import os
import sys
import json
import requests

PORTAL_URL = os.environ.get("ADMIN_PORTAL_URL", "http://localhost:8000")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "changeme123")
STAFF_NAME = os.environ.get("STAFF_NAME", "automation-bot")


def get_token():
    r = requests.post(f"{PORTAL_URL}/api/login", json={
        "staff_name": STAFF_NAME,
        "password": ADMIN_PASSWORD,
    })
    r.raise_for_status()
    return r.json()["token"]


def main():
    out_path = sys.argv[1] if len(sys.argv) > 1 else "config/companies.json"

    token = get_token()
    headers = {"Authorization": f"Bearer {token}"}

    r = requests.post(f"{PORTAL_URL}/api/export", headers=headers)
    r.raise_for_status()
    data = r.json()

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(data["companies"], f, indent=2)

    print(f"Wrote {data['count']} companies to {out_path}")


if __name__ == "__main__":
    main()
