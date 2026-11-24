"""main.py - runs the whole pipeline: search -> filter -> store -> recruiters -> tailor resume -> queue emails.

Usage:   python main.py            (demo data)
         python main.py --live     (authorized API from .env, falls back to demo if not configured)
Then:    streamlit run dashboard.py
Emails are only QUEUED here as Pending. Sending happens in the dashboard after you approve.
"""
import sys

import database
import email_automation
import job_filter
import job_search
import recruiter_data
import resume_tailor


def run_pipeline(use_live: bool = False) -> dict:
    database.init_db()
    jobs, source = job_search.search_jobs(use_live)
    result = job_filter.filter_jobs(jobs)
    resume = resume_tailor.load_resume()
    summary = {"source": source, "fetched": len(jobs), "matching": len(result["kept"]),
               "rejected": result["reasons"], "recruiters": 0, "valid_emails": 0, "emails_queued": 0}

    # Save matching jobs FIRST so a duplicate repost can never take the original's place in the database.
    job_ids = {}
    for job in result["kept"]:
        job_ids[id(job)], _ = database.insert_job(job, matched=True, matched_keywords=job["matched_keywords"])
    for job, reason in result["rejected"]:
        database.insert_job(job, matched=False, reject_reason=reason)

    for job, rec in recruiter_data.build_recruiter_records(result["kept"]):
        rec_id, created = database.insert_recruiter(rec, job_ids[id(job)])
        summary["recruiters"] += int(created)
        summary["valid_emails"] += int(created and rec["email_valid"])
        if rec["email_valid"]:  # never email a missing or invalid address
            tailored = resume_tailor.tailor_resume(resume, job["description"])
            path = resume_tailor.save_tailored_resume(resume, tailored, job)
            _, new = email_automation.queue_initial_email(rec_id, job_ids[id(job)], job, rec, resume, tailored, path)
            summary["emails_queued"] += int(new)
    return summary


if __name__ == "__main__":
    s = run_pipeline(use_live="--live" in sys.argv)
    print(f"Data source: {s['source']}")
    print(f"Fetched {s['fetched']} posts -> {s['matching']} matching opportunities")
    print("Rejected:", s["rejected"])
    print(f"Recruiters: {s['recruiters']} | valid emails: {s['valid_emails']} | emails queued (Pending): {s['emails_queued']}")
    print("Next: streamlit run dashboard.py")
