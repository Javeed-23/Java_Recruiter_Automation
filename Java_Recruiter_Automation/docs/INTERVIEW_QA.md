# Interview questions and answers

**1. What does your project do?** It finds Java C2C/W2 job posts, filters for USA and the last 24 hours, collects recruiter details, tailors a resume, and sends personalised emails after I approve them. A SQLite database stores everything and a Streamlit dashboard shows it.

**2. Why did you use demo data instead of logging into LinkedIn?** Automating LinkedIn login or scraping breaks its terms and can get accounts banned, and it handles other people's personal data. So I built the full pipeline on fictional data and isolated the data source, so an authorised API can replace it.

**3. How would you connect a real API?** Set JOB_API_URL and JOB_API_KEY in .env, then map the response fields in `normalize_live_job()`. Nothing else changes.

**4. How do you keep secrets safe?** Environment variables via `.env`, which is in `.gitignore`. Gmail uses an App Password. Hosted deployments use Streamlit Secrets.

**5. How does the filter work?** Rules in order: Java in the title, USA location, posted within 24 hours, not spam, not a bench-marketer ad, at least one keyword, not a duplicate. Each rejection stores its reason.

**6. How do you remove duplicates?** A hash of title, company and location for jobs, the email address for recruiters, and UNIQUE constraints in SQLite as a safety net.

**7. How do you validate emails?** A regular expression checks the format. It cannot prove the mailbox exists. Invalid or missing emails are stored but never emailed, and I never guess an address.

**8. How does approval work?** `send_email()` raises `ApprovalRequired` unless `approved=True`. Only the dashboard's Approve & send button, after a confirmation tick, passes it.

**9. How do you avoid unsolicited bulk email?** Demo mode sends only to my test address, one initial email and one follow-up per recruiter at most, and each needs manual approval. For real use I would add opt-out wording and follow CAN-SPAM.

**10. How does the follow-up stay in the same thread?** It sets the `In-Reply-To` and `References` headers to the original Message-ID.

**11. How do you detect replies?** Over IMAP I read recent headers and look for messages whose `In-Reply-To` matches a Message-ID I sent. My own sent mail is excluded.

**12. What does resume tailoring do, and what does it not do?** It reorders skills and projects and rewrites the summary using only what is in the resume. Skills the job wants but the resume lacks are listed as gaps, never added.

**13. What happens if sending fails?** The error is caught, the status becomes Failed with the reason, and the dashboard lets me move it back to Pending to retry.

**14. Why SQLite?** It is built in, needs no server, and is enough for this size. For multiple users I would move to PostgreSQL.

**15. What bug did testing find?** A duplicate repost was saved before the original, so the original showed as not matching. I changed the save order and a test now covers it.

**16. What would you improve?** PDF resumes, a real authorised data source, scheduled runs, better bench-marketer detection, and unsubscribe handling.
