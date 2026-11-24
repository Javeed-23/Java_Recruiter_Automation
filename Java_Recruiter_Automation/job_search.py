"""job_search.py - Module 1: get job posts.

DEMO source : data/sample_jobs.json (fictional data, labelled "DEMO sample data").
LIVE source : an authorized job API you configure in .env (JOB_API_URL / JOB_API_KEY).
This module never logs into LinkedIn and never scrapes it.
"""
import json
from datetime import datetime, timedelta, timezone

import requests

import config


class LiveApiNotConfigured(Exception):
    """Raised when live mode is requested but no API credentials are set."""


def build_queries() -> list:
    """One search phrase per keyword, e.g. 'Java Developer C2C'."""
    return [f"{config.ROLE} {kw}" for kw in config.KEYWORDS]


def load_demo_jobs(path=None) -> list:
    """Load fictional sample jobs. 'hours_ago' is turned into a real timestamp so the 24h filter can be tested."""
    path = path or config.DATA_DIR / "sample_jobs.json"
    with open(path, encoding="utf-8") as f:
        raw = json.load(f)
    now = datetime.now(timezone.utc)
    jobs = []
    for item in raw:
        job = dict(item)
        hours = job.pop("hours_ago", 0)
        job["posted_at"] = (now - timedelta(hours=hours)).isoformat(timespec="seconds")
        job["source"] = "DEMO sample data"
        job["is_demo"] = True
        jobs.append(job)
    return jobs


def normalize_live_job(item: dict) -> dict:
    """Map ONE record from your API to our standard fields.
    TODO: change the keys on the right to match your provider's documentation."""
    return {
        "title": item.get("title", ""),
        "description": item.get("description", ""),
        "location": item.get("location", ""),
        "company": item.get("company", ""),
        "posted_at": item.get("posted_at", ""),   # must be an ISO date-time string
        "url": item.get("url", ""),
        "recruiter": item.get("recruiter") or {},  # {"name","email","linkedin_url"} only if the API provides it
        "source": "LIVE API",
        "is_demo": False,
    }


def fetch_live_jobs() -> list:
    """Call an authorized API. Stops with a clear message if credentials are missing."""
    url, key = config.get("JOB_API_URL"), config.get("JOB_API_KEY")
    if not url or not key:
        raise LiveApiNotConfigured("JOB_API_URL / JOB_API_KEY are not set in .env, so live mode is unavailable.")
    jobs = []
    for q in build_queries():
        try:
            resp = requests.get(url, headers={"Authorization": f"Bearer {key}"}, params={"query": q}, timeout=20)
            resp.raise_for_status()
            jobs += [normalize_live_job(x) for x in resp.json().get("results", [])]
        except (requests.RequestException, ValueError) as exc:
            print(f"[job_search] query '{q}' failed: {exc}")  # keep going with the other queries
    return jobs


def search_jobs(use_live: bool = False):
    """Return (jobs, source_label). Falls back to demo data when live mode is not configured."""
    if use_live:
        try:
            return fetch_live_jobs(), "LIVE API"
        except LiveApiNotConfigured as exc:
            print(f"[job_search] {exc} Using DEMO data instead.")
    return load_demo_jobs(), "DEMO sample data"


if __name__ == "__main__":
    for j in load_demo_jobs():
        print(j["posted_at"], "|", j["title"], "|", j["location"], "|", j["company"])
