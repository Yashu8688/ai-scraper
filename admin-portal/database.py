import sqlite3
import re
import difflib
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = Path(__file__).parent / "companies.db"

SUFFIXES = [
    "inc", "incorporated", "llc", "l.l.c", "corp", "corporation",
    "co", "company", "ltd", "limited", "group", "staffing",
    "consulting", "solutions", "technologies", "technology", "tech",
]


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_conn()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS companies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            normalized_name TEXT NOT NULL,
            website TEXT,
            careers_url TEXT,
            platform TEXT DEFAULT 'custom',       -- greenhouse | lever | custom
            board_identifier TEXT,                 -- greenhouse board token / lever company slug
            state TEXT,
            company_size TEXT DEFAULT 'small_mid', -- small_mid | staffing_agency | top_tier
            recruiter_name TEXT,
            recruiter_contact TEXT,
            added_by TEXT NOT NULL,
            date_added TEXT NOT NULL,
            last_shown_date TEXT,
            times_shown INTEGER DEFAULT 0,
            active INTEGER DEFAULT 1
        );

        CREATE INDEX IF NOT EXISTS idx_normalized_name ON companies(normalized_name);

        CREATE TABLE IF NOT EXISTS sessions (
            token TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            expires_at TEXT NOT NULL,
            staff_name TEXT
        );
        """
    )
    conn.commit()
    conn.close()


def normalize_name(name: str) -> str:
    """Lowercase, strip punctuation and common legal suffixes for dedup matching."""
    n = name.lower().strip()
    n = re.sub(r"[.,&/\\\-]", " ", n)
    n = re.sub(r"[^a-z0-9\s]", "", n)
    words = [w for w in n.split() if w not in SUFFIXES]
    return " ".join(words).strip()


def find_duplicate(conn, name: str, website: str | None, threshold: float = 0.88):
    """Returns the matching row (sqlite3.Row) if a likely duplicate exists, else None."""
    norm = normalize_name(name)

    # exact normalized-name match
    row = conn.execute(
        "SELECT * FROM companies WHERE normalized_name = ? AND active = 1", (norm,)
    ).fetchone()
    if row:
        return row

    # website/domain match
    if website:
        domain = extract_domain(website)
        if domain:
            row = conn.execute(
                "SELECT * FROM companies WHERE active = 1 AND website LIKE ?",
                (f"%{domain}%",),
            ).fetchone()
            if row:
                return row

    # fuzzy name match against all active companies
    rows = conn.execute(
        "SELECT * FROM companies WHERE active = 1"
    ).fetchall()
    for r in rows:
        ratio = difflib.SequenceMatcher(None, norm, r["normalized_name"]).ratio()
        if ratio >= threshold:
            return r

    return None


def extract_domain(url: str) -> str | None:
    m = re.search(r"(?:https?://)?(?:www\.)?([a-z0-9\-]+\.[a-z0-9\-.]+)", url.lower())
    return m.group(1) if m else None


def companies_due_for_export(conn, rotation_days: int = 14, limit: int | None = None):
    cutoff = (datetime.utcnow() - timedelta(days=rotation_days)).isoformat()
    query = """
        SELECT * FROM companies
        WHERE active = 1
          AND (last_shown_date IS NULL OR last_shown_date < ?)
        ORDER BY last_shown_date IS NOT NULL, last_shown_date ASC
    """
    if limit:
        query += f" LIMIT {int(limit)}"
    return conn.execute(query, (cutoff,)).fetchall()


def mark_shown(conn, ids: list[int]):
    now = datetime.utcnow().isoformat()
    conn.executemany(
        "UPDATE companies SET last_shown_date = ?, times_shown = times_shown + 1 WHERE id = ?",
        [(now, i) for i in ids],
    )
    conn.commit()
