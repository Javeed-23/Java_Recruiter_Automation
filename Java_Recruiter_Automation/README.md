# Java Developer Job Search & Recruiter Email Automation System

A Python app that finds relevant **Java Developer C2C/W2 job posts**, filters them, collects recruiter contact details, tailors a resume to each job, and sends **personalised emails only after you approve them**. It includes a SQLite database and a Streamlit dashboard.

> ## ⚠️ Demo data, not live LinkedIn data
> This project **does not log into LinkedIn and does not scrape it**. That would break LinkedIn's terms and privacy rules.
> It ships with **fictional sample data** (`data/sample_jobs.json`), clearly labelled `DEMO sample data` in the app and database.
> Emails in demo mode go **only to your own test address** (`TEST_RECIPIENT`), never to a recruiter.
> A real, authorised job API can be plugged in later (see "Connecting a real API").

## Features
| Module | File | What it does |
|---|---|---|
| 1 Job search | `job_search.py` | Loads demo jobs, or calls an authorised API from `.env` |
| 2 Job filter | `job_filter.py` | Java role, USA, last 24h, keywords (C2C, Bench, Sales, W2, Full-Time, Hotlist), removes spam, bench-marketer ads and duplicates |
| 3 Recruiters | `recruiter_data.py` | Name, company, email, job title, profile URL; validates email format; removes duplicates; **never invents emails** |
| 4 Email | `email_automation.py` | Template, preview, approval, Gmail SMTP, 7-day threaded follow-up, IMAP reply check |
| 5 Database | `database.py` | SQLite: jobs, recruiters, emails (Pending/Sent/Failed), timestamps, unique constraints |
| 6 Dashboard | `dashboard.py` | Metrics, filters, tables, email preview + approve button, analytics |
| Extra | `resume_tailor.py` | Re-orders skills and rewrites the summary from your own resume; never adds skills you do not have |
| Runner | `main.py` | search → filter → store → recruiters → tailor → queue Pending emails |

## Architecture
```
sample_jobs.json / authorised API
        │  job_search.py
        ▼
  job_filter.py ──► rejected (reason saved)
        │ matching jobs
        ▼
 recruiter_data.py ──► valid email? ──no──► stored, no email
        │ yes
        ▼
 resume_tailor.py ──► email_automation.py (Pending) ──► YOU preview + approve ──► Gmail SMTP
                                                                   │
                         7 days, no reply ──► follow-up (Pending, needs approval) ◄── IMAP reply check
        ▼
   SQLite (database.py) ◄──► Streamlit dashboard
```

## Setup (computer)
```bash
git clone <your-repo-url> && cd Java_Recruiter_Automation
python -m venv venv && source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                  # then edit .env
python main.py                                        # runs the pipeline on demo data
streamlit run dashboard.py                            # opens the dashboard
```

## Setup (phone only: free hosting)
1. Upload this folder to a GitHub repository (GitHub mobile site → "Add file → Upload files").
2. Go to **share.streamlit.io**, sign in with GitHub, choose the repo, main file `dashboard.py`, deploy.
3. In the app's **Settings → Secrets**, paste your values as `KEY = "value"` lines (same names as `.env.example`). Never put them in the repo.
4. Open the link on your phone. The database resets when the app restarts. That is fine for a demo.

## Configure credentials securely
* Secrets live in `.env` (local) or Streamlit Secrets (hosted). `.env` is in `.gitignore`, so it is never uploaded.
* Use a **throw-away Gmail account**. Turn on 2-Step Verification, then create an **App Password** (Google Account → Security → App passwords). Put it in `GMAIL_APP_PASSWORD`.
* Keep `DEMO_MODE=true` and set `TEST_RECIPIENT` to your own address.

## Using the dashboard
1. Sidebar → **Run search + filter pipeline**.
2. Check the metrics, the **Jobs** table (filter by text, keyword, matching/rejected) and the **Recruiters** table.
3. **Email approval** tab → pick an email → read the preview → tick the confirmation box → **Approve & send**.
4. **Follow-ups & replies** → tick "pretend 7 days passed" → **Queue follow-ups** → approve them. Use **Simulate reply** or **Check inbox** to track replies.
5. **Analytics** shows sent, replied, reply rate and why posts were rejected.

## Email template
The placeholder template is `data/email_template.txt`. **Replace it with the template your internship team provided.** Keep the first line as `Subject: ...`. Fields such as `{recruiter_name}`, `{job_title}`, `{company}`, `{matched_skills}` are filled automatically.
Put your own details in `data/sample_resume.json`.

## Tests
```bash
python -m unittest discover -s tests -v
```
21 tests cover: Java USA 2h ago, Java USA 30h ago, Python job, Java India, missing email, duplicates, invalid email, bench-marketer/spam posts, approval required, send success, send failure, no double sending, follow-up threading, reply detection, resume honesty. They use fake mail servers, so nothing real is sent. Results are in `docs/TESTING_RESULTS.md`.

## Connecting a real API later
1. Choose a job-data provider you are authorised to use and read its terms.
2. Put `JOB_API_URL` and `JOB_API_KEY` in `.env`.
3. In `job_search.py`, edit `normalize_live_job()` so the field names match the provider's response.
4. If the provider returns recruiter contacts, they flow through `recruiter_data.py` automatically. Otherwise add an authorised contact-data API in `fetch_live_recruiter_info()`.
5. Switch off `DEMO_MODE` only for people who have agreed to receive your email, and respect anti-spam laws (CAN-SPAM: honest subject, opt-out).

## Limitations
* Demo data is fictional. Email format validation does not prove a mailbox exists.
* The tailored resume is a `.txt` file; a PDF/DOCX generator can be added.
* Reply detection uses `In-Reply-To` headers, so it needs Gmail IMAP enabled.
* The bench-marketer rule is keyword based and can be tuned in `job_filter.py`.

## Project structure
```
Java_Recruiter_Automation/
├── main.py  job_search.py  job_filter.py  recruiter_data.py
├── email_automation.py  database.py  dashboard.py  resume_tailor.py  config.py
├── requirements.txt  README.md  .env.example  .gitignore
├── data/  (sample_jobs.json, sample_resume.json, email_template.txt, followup_template.txt)
├── tests/test_scenarios.py
└── docs/  (VIDEO_SCRIPT.md, INTERVIEW_QA.md, TESTING_RESULTS.md, CODE_GUIDE.md)
```
