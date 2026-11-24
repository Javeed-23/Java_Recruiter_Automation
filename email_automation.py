"""email_automation.py - Module 4: personalised emails with preview + approval.

Safety rules built in:
  * Nothing is sent unless send_email(..., approved=True) is called (the dashboard button does this).
  * DEMO_MODE=true (default): every email goes to TEST_RECIPIENT (your own address), never to a recruiter.
  * One initial email per recruiter, one follow-up per recruiter (database UNIQUE constraint).
  * Credentials come from environment variables only.
"""
import email
import imaplib
import re
import smtplib
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from email.utils import make_msgid
from pathlib import Path

import config
import database


class ApprovalRequired(Exception):
    """Raised when someone tries to send without approval."""


class EmailConfigError(Exception):
    """Raised when credentials / recipient settings are missing."""


# Replaceable in tests so no real mail is ever sent while testing.
smtp_factory = smtplib.SMTP_SSL
imap_factory = imaplib.IMAP4_SSL


class _SafeDict(dict):
    def __missing__(self, key):  # unknown {field} stays visible instead of crashing
        return "{" + key + "}"


def load_template(path) -> str:
    """Read a template file, dropping '# ' comment lines."""
    text = Path(path).read_text(encoding="utf-8")
    return "\n".join(l for l in text.splitlines() if not l.startswith("# ")).strip() + "\n"


def render_email(template_text: str, fields: dict):
    """Fill the template. Returns (subject, body). First line must be 'Subject: ...'."""
    filled = template_text.format_map(_SafeDict(fields))
    first, _, rest = filled.partition("\n")
    if not first.lower().startswith("subject:"):
        raise ValueError("Template must start with a 'Subject:' line.")
    return first.split(":", 1)[1].strip(), rest.strip() + "\n"


def build_fields(job: dict, recruiter: dict, resume: dict, tailored: dict) -> dict:
    return {
        "recruiter_name": (recruiter.get("name") or "Hiring Team").split()[0] if recruiter.get("name") else "Hiring Team",
        "company": job.get("company", ""), "job_title": job.get("title", ""),
        "location": job.get("location", ""), "job_url": job.get("url", ""),
        "candidate_name": resume["name"], "candidate_phone": resume["phone"],
        "candidate_email": resume["email"], "candidate_linkedin": resume.get("linkedin", ""),
        "matched_skills": ", ".join(tailored["matched"]) or "see attached resume",
        "fit_summary": tailored["summary"],
    }


def queue_initial_email(recruiter_id, job_id, job, recruiter, resume, tailored, attachment_path):
    """Create the Pending email (nothing is sent yet)."""
    subject, body = render_email(load_template(config.DATA_DIR / "email_template.txt"),
                                 build_fields(job, recruiter, resume, tailored))
    return database.create_email(recruiter_id, job_id, "initial", subject, body, attachment_path)


def resolve_recipient(recruiter_email: str) -> str:
    """Demo mode redirects to TEST_RECIPIENT. Live mode uses the recruiter address."""
    if config.is_demo_mode():
        to = config.get("TEST_RECIPIENT")
        if not to:
            raise EmailConfigError("DEMO_MODE is on but TEST_RECIPIENT is not set in .env.")
        return to
    if not recruiter_email:
        raise EmailConfigError("This recruiter has no email address.")
    return recruiter_email


def build_message(row: dict, to_addr: str, from_addr: str) -> EmailMessage:
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = from_addr, to_addr, row["subject"]
    msg["Message-ID"] = make_msgid(idstring="javarecruiter", domain=from_addr.split("@")[-1])
    if row.get("in_reply_to"):  # makes the follow-up appear in the same thread
        msg["In-Reply-To"] = msg["References"] = row["in_reply_to"]
    msg.set_content(row["body"])
    att = row.get("attachment_path")
    if att and Path(att).exists():
        msg.add_attachment(Path(att).read_bytes(), maintype="text", subtype="plain", filename=Path(att).name)
    return msg


def preview(email_id: int) -> dict:
    """What the dashboard shows before approval."""
    row = database.get_email(email_id)
    if not row:
        raise ValueError("Email not found")
    try:
        to = resolve_recipient(row["recruiter_email"])
    except EmailConfigError as exc:
        to = f"(cannot send: {exc})"
    return {"to": to, "recruiter_email": row["recruiter_email"], "subject": row["subject"], "body": row["body"],
            "attachment": Path(row["attachment_path"]).name if row["attachment_path"] else None,
            "status": row["status"], "demo_mode": config.is_demo_mode()}


def send_email(email_id: int, approved: bool = False):
    """Send one Pending email. Returns (ok, message). Failures are saved as 'Failed' with the reason."""
    if not approved:
        raise ApprovalRequired("User approval is required before sending any email.")
    row = database.get_email(email_id)
    if not row:
        return False, "Email not found."
    if row["status"] != "Pending":
        return False, f"Email is already {row['status']}."
    try:
        addr, pwd = config.get("GMAIL_ADDRESS"), config.get("GMAIL_APP_PASSWORD")
        if not addr or not pwd:
            raise EmailConfigError("GMAIL_ADDRESS / GMAIL_APP_PASSWORD are not set in .env.")
        msg = build_message(row, resolve_recipient(row["recruiter_email"]), addr)
        with smtp_factory(config.get("SMTP_HOST", "smtp.gmail.com"), int(config.get("SMTP_PORT", "465"))) as s:
            s.login(addr, pwd)
            s.send_message(msg)
        database.mark_sent(email_id, msg["Message-ID"])
        return True, f"Sent to {msg['To']}"
    except Exception as exc:  # network, login, config... all end as a Failed status
        database.mark_failed(email_id, f"{type(exc).__name__}: {exc}")
        return False, f"Failed: {exc}"


def retry_failed(email_id: int) -> None:
    database.reset_to_pending(email_id)


def queue_followups(days: int = config.FOLLOWUP_DAYS, simulate: bool = False) -> int:
    """Create Pending follow-ups for Sent, un-replied emails older than `days`.
    simulate=True ignores the waiting time (demo button 'pretend 7 days passed')."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    template = load_template(config.DATA_DIR / "followup_template.txt")
    created = 0
    for row in database.list_emails("Sent"):
        if row["kind"] != "initial" or row["replied"]:
            continue
        if not simulate and datetime.fromisoformat(row["sent_at"]) > cutoff:
            continue
        fields = {"recruiter_name": (row["recruiter_name"] or "Hiring Team").split()[0], "company": row["company"],
                  "job_title": row["job_title"], "candidate_name": "", "candidate_phone": "", "candidate_email": ""}
        import resume_tailor
        r = resume_tailor.load_resume()
        fields.update(candidate_name=r["name"], candidate_phone=r["phone"], candidate_email=r["email"])
        _, body = render_email("Subject: x\n" + template, fields)
        _, new = database.create_email(row["recruiter_id"], row["job_id"], "followup", "Re: " + row["subject"],
                                       body, None, in_reply_to=row["message_id"])
        created += int(new)
    return created


def check_replies() -> int:
    """Look in the inbox (IMAP) for messages that reply to our Sent emails. Returns how many were newly found."""
    sent = database.query("SELECT id, message_id FROM emails WHERE status='Sent' AND message_id IS NOT NULL")
    our_ids = {r["message_id"] for r in sent}
    addr, pwd = config.get("GMAIL_ADDRESS"), config.get("GMAIL_APP_PASSWORD")
    if not addr or not pwd:
        raise EmailConfigError("GMAIL_ADDRESS / GMAIL_APP_PASSWORD are not set in .env.")
    referenced = set()
    box = imap_factory(config.get("IMAP_HOST", "imap.gmail.com"))
    try:
        box.login(addr, pwd)
        box.select("INBOX", readonly=True)
        since = (datetime.now() - timedelta(days=30)).strftime("%d-%b-%Y")
        _, data = box.search(None, "SINCE", since)
        for num in data[0].split():
            _, parts = box.fetch(num, "(BODY.PEEK[HEADER.FIELDS (MESSAGE-ID IN-REPLY-TO REFERENCES)])")
            msg = email.message_from_bytes(parts[0][1])
            if msg.get("Message-ID", "").strip() in our_ids:
                continue  # that is our own sent mail, not a reply
            referenced.update((msg.get("In-Reply-To", "") + " " + msg.get("References", "")).split())
    finally:
        try:
            box.logout()
        except Exception:
            pass
    found = 0
    for r in sent:
        if r["message_id"] in referenced:
            database.mark_replied(r["id"])
            found += 1
    return found


def simulate_reply(email_id: int) -> None:
    """DEMO ONLY: mark an email as replied without checking the inbox."""
    database.mark_replied(email_id)
