"""database.py - SQLite storage: jobs, recruiters, emails. Unique constraints prevent duplicates."""
import hashlib
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_hash TEXT NOT NULL UNIQUE,
    title TEXT, company TEXT, location TEXT, description TEXT,
    posted_at TEXT, url TEXT, source TEXT,
    is_demo INTEGER DEFAULT 1,
    matched INTEGER DEFAULT 0,
    matched_keywords TEXT,
    reject_reason TEXT,
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS recruiters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dedupe_key TEXT NOT NULL UNIQUE,
    name TEXT, company TEXT, email TEXT,
    email_valid INTEGER DEFAULT 0,
    linkedin_url TEXT, job_title TEXT,
    job_id INTEGER REFERENCES jobs(id),
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS emails (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recruiter_id INTEGER NOT NULL REFERENCES recruiters(id),
    job_id INTEGER REFERENCES jobs(id),
    kind TEXT NOT NULL DEFAULT 'initial' CHECK (kind IN ('initial','followup')),
    status TEXT NOT NULL DEFAULT 'Pending' CHECK (status IN ('Pending','Sent','Failed')),
    subject TEXT, body TEXT, attachment_path TEXT,
    message_id TEXT, in_reply_to TEXT, error TEXT,
    replied INTEGER DEFAULT 0,
    created_at TEXT, sent_at TEXT,
    UNIQUE (recruiter_id, kind)
);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def connection():
    """Open the database, commit on success, roll back on error, always close."""
    path = config.db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """Create the tables if they do not exist yet."""
    with connection() as c:
        c.executescript(SCHEMA)


def query(sql: str, params: tuple = ()) -> list:
    """Run a SELECT and return a list of dicts (easy to turn into a pandas DataFrame)."""
    with connection() as c:
        return [dict(r) for r in c.execute(sql, params).fetchall()]


def job_hash(title: str, company: str, location: str) -> str:
    """Same title + company + location = same job, however many times it is posted."""
    norm = lambda s: re.sub(r"\s+", " ", (s or "").strip().lower())
    return hashlib.sha1(f"{norm(title)}|{norm(company)}|{norm(location)}".encode()).hexdigest()


def insert_job(job: dict, matched: bool, matched_keywords: str = "", reject_reason: str = None):
    """Insert a job. Returns (job_id, created). created=False means it already existed."""
    h = job_hash(job.get("title"), job.get("company"), job.get("location"))
    with connection() as c:
        cur = c.execute(
            """INSERT OR IGNORE INTO jobs (job_hash,title,company,location,description,posted_at,url,
               source,is_demo,matched,matched_keywords,reject_reason,created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (h, job.get("title"), job.get("company"), job.get("location"), job.get("description"),
             job.get("posted_at"), job.get("url"), job.get("source"), int(bool(job.get("is_demo", True))),
             int(matched), matched_keywords, reject_reason, now_iso()))
        if cur.rowcount:
            return cur.lastrowid, True
        return c.execute("SELECT id FROM jobs WHERE job_hash=?", (h,)).fetchone()["id"], False


def insert_recruiter(rec: dict, job_id: int):
    """Insert a recruiter. Returns (recruiter_id, created). Duplicates (same dedupe_key) are skipped."""
    with connection() as c:
        cur = c.execute(
            """INSERT OR IGNORE INTO recruiters (dedupe_key,name,company,email,email_valid,linkedin_url,
               job_title,job_id,created_at) VALUES (?,?,?,?,?,?,?,?,?)""",
            (rec["dedupe_key"], rec.get("name"), rec.get("company"), rec.get("email"),
             int(rec.get("email_valid", 0)), rec.get("linkedin_url"), rec.get("job_title"), job_id, now_iso()))
        if cur.rowcount:
            return cur.lastrowid, True
        return c.execute("SELECT id FROM recruiters WHERE dedupe_key=?", (rec["dedupe_key"],)).fetchone()["id"], False


def create_email(recruiter_id, job_id, kind, subject, body, attachment_path=None, in_reply_to=None):
    """Queue an email as Pending. One email per recruiter per kind, so no duplicate outreach."""
    with connection() as c:
        cur = c.execute(
            """INSERT OR IGNORE INTO emails (recruiter_id,job_id,kind,status,subject,body,attachment_path,
               in_reply_to,created_at) VALUES (?,?,?,'Pending',?,?,?,?,?)""",
            (recruiter_id, job_id, kind, subject, body, attachment_path, in_reply_to, now_iso()))
        if cur.rowcount:
            return cur.lastrowid, True
        return c.execute("SELECT id FROM emails WHERE recruiter_id=? AND kind=?",
                         (recruiter_id, kind)).fetchone()["id"], False


EMAIL_SELECT = """SELECT e.*, r.name AS recruiter_name, r.email AS recruiter_email, r.company AS company,
                  j.title AS job_title, j.url AS job_url, j.location AS location
                  FROM emails e JOIN recruiters r ON r.id=e.recruiter_id LEFT JOIN jobs j ON j.id=e.job_id"""


def get_email(email_id: int):
    rows = query(EMAIL_SELECT + " WHERE e.id=?", (email_id,))
    return rows[0] if rows else None


def list_emails(status: str = None) -> list:
    if status:
        return query(EMAIL_SELECT + " WHERE e.status=? ORDER BY e.id", (status,))
    return query(EMAIL_SELECT + " ORDER BY e.id")


def mark_sent(email_id: int, message_id: str) -> None:
    with connection() as c:
        c.execute("UPDATE emails SET status='Sent', message_id=?, sent_at=?, error=NULL WHERE id=?",
                  (message_id, now_iso(), email_id))


def mark_failed(email_id: int, error: str) -> None:
    with connection() as c:
        c.execute("UPDATE emails SET status='Failed', error=? WHERE id=?", (str(error)[:500], email_id))


def reset_to_pending(email_id: int) -> None:
    with connection() as c:
        c.execute("UPDATE emails SET status='Pending', error=NULL WHERE id=? AND status='Failed'", (email_id,))


def mark_replied(email_id: int) -> None:
    with connection() as c:
        c.execute("UPDATE emails SET replied=1 WHERE id=?", (email_id,))


def stats() -> dict:
    """Numbers shown on the dashboard."""
    one = lambda sql: query(sql)[0]["n"]
    return {
        "total_jobs": one("SELECT COUNT(*) n FROM jobs"),
        "matching_jobs": one("SELECT COUNT(*) n FROM jobs WHERE matched=1"),
        "recruiters": one("SELECT COUNT(*) n FROM recruiters"),
        "valid_emails": one("SELECT COUNT(*) n FROM recruiters WHERE email_valid=1"),
        "pending": one("SELECT COUNT(*) n FROM emails WHERE status='Pending'"),
        "sent": one("SELECT COUNT(*) n FROM emails WHERE status='Sent'"),
        "failed": one("SELECT COUNT(*) n FROM emails WHERE status='Failed'"),
        "replied": one("SELECT COUNT(*) n FROM emails WHERE replied=1"),
        "followups_sent": one("SELECT COUNT(*) n FROM emails WHERE kind='followup' AND status='Sent'"),
    }
