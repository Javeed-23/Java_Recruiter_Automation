"""recruiter_data.py - Module 3: recruiter details from the job data.

Only information that is really present in the data is used. A missing email stays missing: we never guess one.
"""
import re

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}$")


def is_valid_email(email) -> bool:
    """Format check only (does not prove the mailbox exists)."""
    if not isinstance(email, str):
        return False
    email = email.strip()
    return bool(EMAIL_RE.match(email)) and ".." not in email


def dedupe_key(name, company, email) -> str:
    """Email (lower-case) when we have one, otherwise name|company."""
    if email and email.strip():
        return "e:" + email.strip().lower()
    return "n:" + f"{(name or '').strip().lower()}|{(company or '').strip().lower()}"


def extract_recruiter(job: dict):
    """Build one recruiter record from a job. Returns None if the job has no recruiter data at all."""
    r = job.get("recruiter") or {}
    name = (r.get("name") or "").strip()
    email = (r.get("email") or "").strip() or None
    linkedin = (r.get("linkedin_url") or "").strip() or None
    if not (name or email or linkedin):
        return None
    return {
        "name": name or None, "company": job.get("company"), "email": email,
        "email_valid": is_valid_email(email), "linkedin_url": linkedin, "job_title": job.get("title"),
        "dedupe_key": dedupe_key(name, job.get("company"), email),
    }


def build_recruiter_records(jobs: list) -> list:
    """Return [(job, recruiter_record)] with duplicate recruiters removed."""
    seen, out = set(), []
    for job in jobs:
        rec = extract_recruiter(job)
        if rec and rec["dedupe_key"] not in seen:
            seen.add(rec["dedupe_key"])
            out.append((job, rec))
    return out


def fetch_live_recruiter_info(job: dict):
    """Placeholder: call an authorized contact-data API here and return a dict
    {"name","email","linkedin_url"} using ONLY what the provider returns."""
    raise NotImplementedError("Connect an authorized recruiter-data API here (see README).")


if __name__ == "__main__":
    for e in ["a@b.com", "bad@@x.com", "", None, "no-at-sign.com"]:
        print(repr(e), "->", is_valid_email(e))
