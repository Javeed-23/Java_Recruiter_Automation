# Code guide (what each function does)

**config.py** `db_path()` database location · `get()` read an environment variable · `is_demo_mode()` true unless DEMO_MODE=false.

**database.py** `connection()` open/commit/close · `init_db()` create tables · `query()` SELECT → list of dicts · `job_hash()` identity of a job (title+company+location) · `insert_job()` / `insert_recruiter()` / `create_email()` insert and skip duplicates (UNIQUE) · `get_email()`, `list_emails()` · `mark_sent()`, `mark_failed()`, `reset_to_pending()`, `mark_replied()` · `stats()` dashboard numbers.

**job_search.py** `load_demo_jobs()` fictional jobs with real timestamps · `fetch_live_jobs()` authorised API call · `normalize_live_job()` map API fields · `search_jobs()` live or demo fallback.

**job_filter.py** `is_usa()` · `is_recent()` last 24h · `is_java_role()` · `match_keywords()` · `check_job()` first failing rule or pass · `filter_jobs()` applies all rules and removes duplicates.

**recruiter_data.py** `is_valid_email()` · `dedupe_key()` · `extract_recruiter()` uses only real data · `build_recruiter_records()` removes duplicate recruiters.

**resume_tailor.py** `tailor_resume()` match/gap skills, reorder, new summary · `render_resume_text()` · `save_tailored_resume()`.

**email_automation.py** `load_template()` · `render_email()` fill template · `queue_initial_email()` create Pending · `resolve_recipient()` demo redirect · `build_message()` headers + attachment · `preview()` · `send_email()` needs `approved=True`, saves Failed on error · `queue_followups()` · `check_replies()` IMAP · `simulate_reply()` demo only.

**main.py** `run_pipeline()` the whole flow. **dashboard.py** the Streamlit screens.
