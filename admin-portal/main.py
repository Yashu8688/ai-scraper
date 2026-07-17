import os
import json
import secrets
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

import database as db

APP_DIR = Path(__file__).parent
STATIC_DIR = APP_DIR / "static"

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "changeme123")
SESSION_HOURS = 12
ROTATION_DAYS = int(os.environ.get("ROTATION_DAYS", "14"))

app = FastAPI(title="Company Admin Portal")


@app.on_event("startup")
def startup():
    db.init_db()


# ---------- auth ----------

class LoginRequest(BaseModel):
    password: str
    staff_name: str


def require_auth(authorization: str | None = Header(default=None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not logged in.")
    token = authorization.removeprefix("Bearer ").strip()
    conn = db.get_conn()
    row = conn.execute("SELECT * FROM sessions WHERE token = ?", (token,)).fetchone()
    if not row or row["expires_at"] < datetime.utcnow().isoformat():
        conn.close()
        raise HTTPException(status_code=401, detail="Session expired. Please log in again.")
    staff_name = row["staff_name"]
    conn.close()
    return staff_name


@app.post("/api/login")
def login(payload: LoginRequest):
    if not payload.staff_name.strip():
        raise HTTPException(status_code=400, detail="Enter your name so entries can be tracked.")
    if payload.password != ADMIN_PASSWORD:
        raise HTTPException(status_code=401, detail="Incorrect password.")
    token = secrets.token_urlsafe(32)
    now = datetime.utcnow()
    conn = db.get_conn()
    conn.execute(
        "INSERT INTO sessions (token, created_at, expires_at, staff_name) VALUES (?, ?, ?, ?)",
        (token, now.isoformat(), (now + timedelta(hours=SESSION_HOURS)).isoformat(), payload.staff_name.strip()),
    )
    conn.commit()
    conn.close()
    return {"token": token, "staff_name": payload.staff_name.strip()}


# ---------- companies ----------

class CompanyIn(BaseModel):
    name: str
    website: str | None = None
    careers_url: str | None = None
    platform: str = "custom"          # greenhouse | lever | custom
    board_identifier: str | None = None
    state: str | None = None
    company_size: str = "small_mid"   # small_mid | staffing_agency | top_tier
    recruiter_name: str | None = None
    recruiter_contact: str | None = None


@app.get("/api/companies")
def list_companies(staff_name: str = Depends(require_auth), q: str | None = None):
    conn = db.get_conn()
    if q:
        rows = conn.execute(
            "SELECT * FROM companies WHERE active = 1 AND name LIKE ? ORDER BY date_added DESC",
            (f"%{q}%",),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM companies WHERE active = 1 ORDER BY date_added DESC"
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.get("/api/stats")
def stats(staff_name: str = Depends(require_auth)):
    conn = db.get_conn()
    total = conn.execute("SELECT COUNT(*) c FROM companies WHERE active = 1").fetchone()["c"]
    today = datetime.utcnow().date().isoformat()
    added_today = conn.execute(
        "SELECT COUNT(*) c FROM companies WHERE active = 1 AND date_added LIKE ?",
        (f"{today}%",),
    ).fetchone()["c"]
    by_staff = conn.execute(
        """SELECT added_by, COUNT(*) c FROM companies
           WHERE active = 1 AND date_added LIKE ?
           GROUP BY added_by ORDER BY c DESC""",
        (f"{today}%",),
    ).fetchall()
    due = len(db.companies_due_for_export(conn, ROTATION_DAYS))
    conn.close()
    return {
        "total_companies": total,
        "added_today": added_today,
        "by_staff_today": [dict(r) for r in by_staff],
        "due_for_next_export": due,
    }


@app.post("/api/companies")
def add_company(payload: CompanyIn, staff_name: str = Depends(require_auth)):
    if not payload.name.strip():
        raise HTTPException(status_code=400, detail="Company name is required.")
    if payload.company_size == "top_tier":
        raise HTTPException(
            status_code=400,
            detail="Top-tier companies are excluded from this database. Add a mid/small staffing agency or company instead.",
        )

    conn = db.get_conn()
    dup = db.find_duplicate(conn, payload.name, payload.website)
    if dup:
        conn.close()
        raise HTTPException(
            status_code=409,
            detail=f"Duplicate: '{dup['name']}' was already added by {dup['added_by']} on "
                   f"{dup['date_added'][:10]}.",
        )

    now = datetime.utcnow().isoformat()
    cur = conn.execute(
        """INSERT INTO companies
           (name, normalized_name, website, careers_url, platform, board_identifier,
            state, company_size, recruiter_name, recruiter_contact, added_by, date_added)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            payload.name.strip(),
            db.normalize_name(payload.name),
            payload.website,
            payload.careers_url,
            payload.platform,
            payload.board_identifier,
            payload.state,
            payload.company_size,
            payload.recruiter_name,
            payload.recruiter_contact,
            staff_name,
            now,
        ),
    )
    conn.commit()
    new_id = cur.lastrowid
    row = conn.execute("SELECT * FROM companies WHERE id = ?", (new_id,)).fetchone()
    conn.close()
    return dict(row)


@app.post("/api/companies/check-duplicate")
def check_duplicate(payload: CompanyIn, staff_name: str = Depends(require_auth)):
    """Live-check as the user types, without inserting."""
    conn = db.get_conn()
    dup = db.find_duplicate(conn, payload.name, payload.website)
    conn.close()
    if dup:
        return {
            "duplicate": True,
            "match": dup["name"],
            "added_by": dup["added_by"],
            "date_added": dup["date_added"][:10],
        }
    return {"duplicate": False}


@app.delete("/api/companies/{company_id}")
def deactivate_company(company_id: int, staff_name: str = Depends(require_auth)):
    conn = db.get_conn()
    conn.execute("UPDATE companies SET active = 0 WHERE id = ?", (company_id,))
    conn.commit()
    conn.close()
    return {"ok": True}


# ---------- export for the scraper ----------

@app.post("/api/export")
def export_companies(staff_name: str = Depends(require_auth), limit: int | None = None):
    """
    Selects companies due for rotation (not shown in the last ROTATION_DAYS),
    marks them as shown, and returns a config/companies.json-compatible payload
    for the ai-scraper repo.
    """
    conn = db.get_conn()
    rows = db.companies_due_for_export(conn, ROTATION_DAYS, limit)
    if not rows:
        conn.close()
        return {"companies": [], "count": 0}

    payload = []
    for r in rows:
        payload.append({
            "name": r["name"],
            "platform": r["platform"],
            "board_identifier": r["board_identifier"],
            "careers_url": r["careers_url"],
            "website": r["website"],
            "state": r["state"],
        })

    db.mark_shown(conn, [r["id"] for r in rows])
    conn.close()
    return {"companies": payload, "count": len(payload)}


# ---------- static frontend ----------

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/")
def index():
    return FileResponse(STATIC_DIR / "index.html")
