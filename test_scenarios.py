"""Run all scenarios:  python -m unittest discover -s tests -v
Uses a temporary database and FAKE mail servers: nothing real is ever sent."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config, database, email_automation, job_filter, job_search, main, recruiter_data, resume_tailor  # noqa: E402


class FakeSMTP:
    sent = []
    fail_with = None

    def __init__(self, *a, **k):
        if FakeSMTP.fail_with:
            raise FakeSMTP.fail_with

    def __enter__(self): return self
    def __exit__(self, *a): return False
    def login(self, u, p): pass
    def send_message(self, msg): FakeSMTP.sent.append(msg)


class FakeIMAP:
    headers = []
    def __init__(self, *a, **k): pass
    def login(self, u, p): pass
    def select(self, *a, **k): return "OK", [b"1"]
    def search(self, *a): return "OK", [b" ".join(str(i + 1).encode() for i in range(len(self.headers)))]
    def fetch(self, num, spec): return "OK", [(b"1", self.headers[int(num) - 1])]
    def logout(self): pass


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ.update(DB_PATH=str(Path(self.tmp.name) / "t.db"), DEMO_MODE="true", TEST_RECIPIENT="me@example.com",
                          GMAIL_ADDRESS="sender@example.com", GMAIL_APP_PASSWORD="x")
        FakeSMTP.sent, FakeSMTP.fail_with = [], None
        email_automation.smtp_factory, email_automation.imap_factory = FakeSMTP, FakeIMAP
        self.summary = main.run_pipeline()

    def tearDown(self):
        self.tmp.cleanup()

    def job(self, company):
        return database.query("SELECT * FROM jobs WHERE company=?", (company,))[0]


class TestFilter(Base):
    def test_1_java_usa_2h_matches(self):
        self.assertEqual(self.job("Apex Demo Staffing")["matched"], 1)

    def test_2_java_usa_30h_rejected(self):
        self.assertEqual(self.job("Northwind Demo Staffing")["reject_reason"], "Older than 24 hours")

    def test_3_python_rejected(self):
        self.assertEqual(self.job("Initech Demo")["reject_reason"], "Not a Java role")

    def test_4_india_rejected(self):
        self.assertEqual(self.job("Hyderabad Demo Tech")["reject_reason"], "Not USA-based")

    def test_5_duplicate_removed(self):
        self.assertEqual(self.summary["rejected"].get("Duplicate"), 1)
        self.assertEqual(len(database.query("SELECT 1 FROM jobs WHERE company='Apex Demo Staffing'")), 1)

    def test_6_bench_marketer_and_spam_rejected(self):
        self.assertEqual(self.job("Bench Demo Marketing")["reject_reason"], "Bench marketer post")
        self.assertEqual(self.job("Quick Cash Demo")["reject_reason"], "Spam")

    def test_7_matching_count(self):
        self.assertEqual(self.summary["matching"], 5)


class TestRecruiters(Base):
    def test_8_missing_email_stays_missing_and_no_email_queued(self):
        r = database.query("SELECT * FROM recruiters WHERE company='Umbrella Demo Consulting'")[0]
        self.assertIsNone(r["email"])
        self.assertEqual(len(database.query("SELECT 1 FROM emails WHERE recruiter_id=?", (r["id"],))), 0)

    def test_9_invalid_email_flagged_and_not_queued(self):
        r = database.query("SELECT * FROM recruiters WHERE company='Globex Demo Solutions'")[0]
        self.assertEqual(r["email_valid"], 0)
        self.assertEqual(len(database.query("SELECT 1 FROM emails WHERE recruiter_id=?", (r["id"],))), 0)

    def test_10_no_invented_emails(self):
        source = {j["recruiter"]["email"] for j in job_search.load_demo_jobs()}
        for e in database.query("SELECT email FROM recruiters WHERE email IS NOT NULL"):
            self.assertIn(e["email"], source)

    def test_11_email_validator(self):
        self.assertTrue(recruiter_data.is_valid_email("a.b@firm.com"))
        for bad in ["x@@y.com", "", None, "nodomain", "a@b"]:
            self.assertFalse(recruiter_data.is_valid_email(bad))


class TestEmail(Base):
    def first_pending(self):
        return database.list_emails("Pending")[0]["id"]

    def test_12_pipeline_creates_pending_only(self):
        self.assertEqual(self.summary["emails_queued"], 3)
        self.assertEqual(database.stats()["sent"], 0)

    def test_13_rerun_creates_no_duplicates(self):
        again = main.run_pipeline()
        self.assertEqual((again["recruiters"], again["emails_queued"]), (0, 0))

    def test_14_approval_required(self):
        with self.assertRaises(email_automation.ApprovalRequired):
            email_automation.send_email(self.first_pending(), approved=False)
        self.assertEqual(FakeSMTP.sent, [])

    def test_15_send_success_goes_to_test_recipient_only(self):
        ok, _ = email_automation.send_email(self.first_pending(), approved=True)
        self.assertTrue(ok)
        self.assertEqual(FakeSMTP.sent[0]["To"], "me@example.com")
        self.assertEqual(database.stats()["sent"], 1)

    def test_16_send_failure_marked_failed(self):
        import smtplib
        FakeSMTP.fail_with = smtplib.SMTPAuthenticationError(535, b"bad credentials")
        ok, _ = email_automation.send_email(self.first_pending(), approved=True)
        self.assertFalse(ok)
        row = database.list_emails("Failed")[0]
        self.assertIn("SMTPAuthenticationError", row["error"])

    def test_17_cannot_send_twice(self):
        eid = self.first_pending()
        email_automation.send_email(eid, approved=True)
        ok, msg = email_automation.send_email(eid, approved=True)
        self.assertFalse(ok)
        self.assertEqual(len(FakeSMTP.sent), 1)

    def test_18_followup_is_threaded_and_not_duplicated(self):
        eid = self.first_pending()
        email_automation.send_email(eid, approved=True)
        self.assertEqual(email_automation.queue_followups(), 0)  # too early
        self.assertEqual(email_automation.queue_followups(simulate=True), 1)
        self.assertEqual(email_automation.queue_followups(simulate=True), 0)  # no second follow-up
        fid = [e for e in database.list_emails("Pending") if e["kind"] == "followup"][0]["id"]
        email_automation.send_email(fid, approved=True)
        self.assertEqual(FakeSMTP.sent[-1]["In-Reply-To"], FakeSMTP.sent[0]["Message-ID"])

    def test_19_reply_detection(self):
        eid = self.first_pending()
        email_automation.send_email(eid, approved=True)
        mid = database.get_email(eid)["message_id"]
        FakeIMAP.headers = [f"Message-ID: <reply1@x>\r\nIn-Reply-To: {mid}\r\n\r\n".encode()]
        self.assertEqual(email_automation.check_replies(), 1)
        self.assertEqual(database.stats()["replied"], 1)

    def test_20_own_sent_mail_not_counted_as_reply(self):
        eid = self.first_pending()
        email_automation.send_email(eid, approved=True)
        mid = database.get_email(eid)["message_id"]
        FakeIMAP.headers = [f"Message-ID: {mid}\r\nIn-Reply-To: {mid}\r\n\r\n".encode()]
        self.assertEqual(email_automation.check_replies(), 0)


class TestResume(unittest.TestCase):
    def test_21_never_adds_skills_not_in_resume(self):
        r = resume_tailor.load_resume()
        t = resume_tailor.tailor_resume(r, "Java Kafka AWS Kubernetes Spring Boot")
        self.assertEqual(set(t["skills"]), set(r["skills"]))
        self.assertIn("Kafka", t["gaps"])
        self.assertNotIn("Kafka", t["matched"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
