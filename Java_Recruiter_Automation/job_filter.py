"""job_filter.py - Module 2: keep only relevant jobs.

Rules: Java role, USA, last 24h, keyword match, not spam, not a bench-marketer ad, no duplicates.
Edit the pattern lists below to tune the filter.
"""
import re
from datetime import datetime, timedelta, timezone

import config
from database import job_hash

US_STATES = ("AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY "
             "NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY DC").split()

KEYWORD_PATTERNS = {
    "C2C": r"\bc2c\b|corp[\s-]to[\s-]corp",
    "Bench": r"\bbench\b",
    "Sales": r"\bsales\b",
    "W2": r"\bw[\s-]?2\b",
    "Full-Time": r"\bfull[\s-]?time\b",
    "Hotlist": r"\bhot[\s-]?list\b",
}

# Posts where a bench marketer advertises THEIR consultants (not a real opening). Rejected.
BENCH_MARKETER_PATTERNS = [r"bench consultants?", r"consultants? available", r"available consultants?",
                           r"consultant hot[\s-]?list", r"candidates? available", r"our consultants?"]
SPAM_PATTERNS = [r"earn \$?\d+", r"work from home and earn", r"crypto", r"investment opportunity",
                 r"click here to (win|claim)", r"whatsapp me", r"\bmlm\b"]


def is_usa(location: str) -> bool:
    """True for 'Dallas, TX, USA', 'Austin, TX', 'Remote - US'. False for 'Hyderabad, India'."""
    loc = location or ""
    low = loc.lower()
    if "india" in low:
        return False
    if re.search(r"\b(usa|u\.s\.a?\.?|united states)\b", low) or re.search(r"\bus\b", low):
        return True
    return bool(re.search(r",\s*(%s)\b" % "|".join(US_STATES), loc))


def parse_time(value: str):
    dt = datetime.fromisoformat(value)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def is_recent(posted_at: str, hours: int = config.MAX_AGE_HOURS, now=None) -> bool:
    """True if posted within the last `hours` hours."""
    try:
        age = (now or datetime.now(timezone.utc)) - parse_time(posted_at)
    except (TypeError, ValueError):
        return False  # unreadable date -> do not guess
    return -timedelta(minutes=5) <= age <= timedelta(hours=hours)


def is_java_role(title: str) -> bool:
    """'Java Developer' yes; 'JavaScript Developer' and 'Python Developer' no."""
    return bool(re.search(r"\bjava\b", (title or "").lower()))


def match_keywords(text: str) -> list:
    return [k for k, p in KEYWORD_PATTERNS.items() if re.search(p, text or "", re.I)]


def _any(patterns, text):
    return any(re.search(p, text or "", re.I) for p in patterns)


def check_job(job: dict, now=None):
    """Return (keywords, reject_reason). reject_reason is None when the job passes."""
    text = f"{job.get('title','')} {job.get('description','')}"
    if not is_java_role(job.get("title")):
        return [], "Not a Java role"
    if not is_usa(job.get("location")):
        return [], "Not USA-based"
    if not is_recent(job.get("posted_at"), now=now):
        return [], "Older than 24 hours"
    if _any(SPAM_PATTERNS, text):
        return [], "Spam"
    if _any(BENCH_MARKETER_PATTERNS, text):
        return [], "Bench marketer post"
    kws = match_keywords(text)
    if not kws:
        return [], "No keyword match"
    return kws, None


def filter_jobs(jobs: list, now=None) -> dict:
    """Run every job through check_job and remove duplicates.
    Returns {"kept": [...], "rejected": [(job, reason)], "reasons": {reason: count}}."""
    kept, rejected, seen = [], [], set()
    for job in jobs:
        kws, reason = check_job(job, now)
        if not reason:
            key = job_hash(job.get("title"), job.get("company"), job.get("location"))
            url = (job.get("url") or "").strip()
            if key in seen or (url and url in seen):
                reason = "Duplicate"
            else:
                seen.add(key)
                if url:
                    seen.add(url)
        if reason:
            rejected.append((job, reason))
        else:
            kept.append({**job, "matched_keywords": ", ".join(kws)})
    reasons = {}
    for _, r in rejected:
        reasons[r] = reasons.get(r, 0) + 1
    return {"kept": kept, "rejected": rejected, "reasons": reasons}


if __name__ == "__main__":
    import job_search
    result = filter_jobs(job_search.load_demo_jobs())
    print("Matching opportunities:", len(result["kept"]))
    for j in result["kept"]:
        print(" +", j["title"], "|", j["company"], "|", j["matched_keywords"])
    for j, r in result["rejected"]:
        print(" -", j["title"], "|", j["location"], "->", r)
