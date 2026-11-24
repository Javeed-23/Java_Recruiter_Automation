"""dashboard.py - Module 6: Streamlit dashboard.   Run:  streamlit run dashboard.py"""
import pandas as pd
import streamlit as st

import config
import database
import email_automation
import main

st.set_page_config(page_title="Java Recruiter Automation", page_icon="📧", layout="wide")
database.init_db()

# ---------- sidebar ----------
st.sidebar.title("Controls")
if config.is_demo_mode():
    st.sidebar.warning("DEMO MODE: sample data only. Every email goes to TEST_RECIPIENT, never to a recruiter.")
use_live = st.sidebar.checkbox("Use live API (needs JOB_API_URL / JOB_API_KEY)", value=False)
if st.sidebar.button("Run search + filter pipeline", type="primary"):
    with st.spinner("Running pipeline..."):
        st.session_state["summary"] = main.run_pipeline(use_live)
    st.sidebar.success("Pipeline finished.")
with st.sidebar.expander("Reset demo database"):
    if st.checkbox("Yes, delete all stored data") and st.button("Reset"):
        config.db_path().unlink(missing_ok=True)
        database.init_db()
        st.rerun()

st.title("📧 Java Developer Job Search & Recruiter Email Automation")
summary = st.session_state.get("summary")
if summary:
    st.caption(f"Data source: **{summary['source']}** | fetched {summary['fetched']} posts | rejected: {summary['rejected']}")
else:
    st.caption("Click 'Run search + filter pipeline' in the sidebar. Demo data is fictional, not real LinkedIn data.")

# ---------- metrics ----------
s = database.stats()
cols = st.columns(4)
cols[0].metric("Total jobs found (unique)", s["total_jobs"])
cols[1].metric("Matching jobs", s["matching_jobs"])
cols[2].metric("Recruiters identified", s["recruiters"])
cols[3].metric("Valid email addresses", s["valid_emails"])
cols = st.columns(4)
cols[0].metric("Emails pending", s["pending"])
cols[1].metric("Emails sent", s["sent"])
cols[2].metric("Failed", s["failed"])
cols[3].metric("Replied", s["replied"])

tab_jobs, tab_rec, tab_mail, tab_follow, tab_stats = st.tabs(
    ["Jobs", "Recruiters", "Email approval", "Follow-ups & replies", "Analytics"])

# ---------- jobs ----------
with tab_jobs:
    jobs = pd.DataFrame(database.query(
        "SELECT title, company, location, posted_at, url, matched_keywords, matched, reject_reason, source FROM jobs"))
    if jobs.empty:
        st.info("No jobs yet. Run the pipeline from the sidebar.")
    else:
        c1, c2, c3 = st.columns(3)
        text = c1.text_input("Search title / company / location")
        view = c2.selectbox("Show", ["Matching only", "Rejected only", "All"])
        kw = c3.multiselect("Keyword", config.KEYWORDS)
        if view == "Matching only":
            jobs = jobs[jobs["matched"] == 1]
        elif view == "Rejected only":
            jobs = jobs[jobs["matched"] == 0]
        if text:
            blob = (jobs["title"] + " " + jobs["company"] + " " + jobs["location"]).str.lower()
            jobs = jobs[blob.str.contains(text.lower(), na=False)]
        for k in kw:
            jobs = jobs[jobs["matched_keywords"].fillna("").str.contains(k, case=False, regex=False)]
        st.write(f"{len(jobs)} result(s)")
        st.dataframe(jobs.drop(columns=["matched"]), width="stretch", hide_index=True)

# ---------- recruiters ----------
with tab_rec:
    rec = pd.DataFrame(database.query(
        "SELECT name, company, email, email_valid, linkedin_url, job_title FROM recruiters"))
    if rec.empty:
        st.info("No recruiters yet.")
    else:
        only_valid = st.checkbox("Only valid emails")
        if only_valid:
            rec = rec[rec["email_valid"] == 1]
        rec["email_status"] = rec["email_valid"].map({1: "valid", 0: "missing/invalid"})
        st.dataframe(rec.drop(columns=["email_valid"]), width="stretch", hide_index=True)

# ---------- email preview + approval ----------
with tab_mail:
    pending = database.list_emails("Pending")
    if not pending:
        st.info("No pending emails.")
    else:
        labels = {f"#{e['id']} {e['kind']} -> {e['recruiter_name']} ({e['company']})": e["id"] for e in pending}
        chosen = st.selectbox("Choose an email to review", list(labels))
        p = email_automation.preview(labels[chosen])
        st.write(f"**To (actual recipient):** {p['to']}")
        if p["demo_mode"]:
            st.caption(f"Demo mode: the recruiter address on file ({p['recruiter_email']}) is NOT used.")
        st.write(f"**Subject:** {p['subject']}")
        st.write(f"**Attachment:** {p['attachment'] or 'none'}")
        st.text_area("Body", p["body"], height=280, disabled=True)
        ok = st.checkbox("I have reviewed this email and approve sending it")
        if st.button("Approve & send", disabled=not ok):
            done, msg = email_automation.send_email(labels[chosen], approved=True)
            (st.success if done else st.error)(msg)
            st.rerun() if done else None
    failed = database.list_emails("Failed")
    if failed:
        st.subheader("Failed emails")
        for e in failed:
            st.write(f"#{e['id']} {e['recruiter_name']}: {e['error']}")
            if st.button("Move back to Pending", key=f"retry{e['id']}"):
                email_automation.retry_failed(e["id"])
                st.rerun()
    st.subheader("All emails")
    allm = pd.DataFrame(database.list_emails())
    if not allm.empty:
        st.dataframe(allm[["id", "kind", "status", "recruiter_name", "company", "subject", "sent_at", "replied", "error"]],
                     width="stretch", hide_index=True)

# ---------- follow-ups ----------
with tab_follow:
    st.write(f"Follow-ups are queued {config.FOLLOWUP_DAYS} days after an email was sent with no reply. They are sent in the same thread and still need your approval.")
    sim = st.checkbox("DEMO: pretend 7 days have passed")
    if st.button("Queue follow-ups"):
        st.success(f"{email_automation.queue_followups(simulate=sim)} follow-up(s) queued. Approve them in the 'Email approval' tab.")
    c1, c2 = st.columns(2)
    if c1.button("Check inbox for replies (IMAP)"):
        try:
            st.success(f"{email_automation.check_replies()} new repl(ies) found.")
        except Exception as exc:
            st.error(f"Could not check inbox: {exc}")
    sent = [e for e in database.list_emails("Sent") if e["kind"] == "initial" and not e["replied"]]
    if sent:
        pick = c2.selectbox("DEMO: simulate a reply from", {f"#{e['id']} {e['recruiter_name']}": e["id"] for e in sent})
        if c2.button("Simulate reply"):
            email_automation.simulate_reply({f"#{e['id']} {e['recruiter_name']}": e["id"] for e in sent}[pick])
            st.rerun()

# ---------- analytics ----------
with tab_stats:
    sent_n = s["sent"]
    rate = (s["replied"] / sent_n * 100) if sent_n else 0
    a, b, c = st.columns(3)
    a.metric("Sent", sent_n)
    b.metric("Replied", s["replied"])
    c.metric("Reply rate", f"{rate:.0f}%")
    st.bar_chart(pd.DataFrame({"count": [s["pending"], s["sent"], s["failed"], s["replied"]]},
                              index=["Pending", "Sent", "Failed", "Replied"]))
    rej = pd.DataFrame(database.query(
        "SELECT reject_reason AS reason, COUNT(*) AS jobs FROM jobs WHERE matched=0 GROUP BY reject_reason"))
    if not rej.empty:
        st.subheader("Why posts were rejected")
        st.bar_chart(rej.set_index("reason"))
