# Testing results

Command: `python -m unittest discover -s tests -v` (Python 3, run on 2026-11-24). Fake SMTP/IMAP servers, temporary database.

## Scenario table
| # | Scenario | Expected | Result |
|---|---|---|---|
| 1 | Java Developer, USA, 2 h ago | Matches | PASS |
| 2 | Java Developer, USA, 30 h ago | Rejected: older than 24 h | PASS |
| 3 | Python Developer, USA | Rejected: not a Java role | PASS |
| 4 | Java Developer, India | Rejected: not USA | PASS |
| 5 | Missing recruiter email | Job matches, recruiter stored, no email created | PASS |
| 6 | Duplicate job post | Second copy rejected, one row stored | PASS |
| 7 | Invalid email (`x@@y.com`) | Flagged invalid, no email created | PASS |
| 8 | Email sending failure | Status `Failed` with reason saved, can retry | PASS |
| 9 | Sending without approval | Blocked (`ApprovalRequired`) | PASS |
| 10 | Demo-mode recipient | Goes to TEST_RECIPIENT only | PASS |
| 11 | Re-run pipeline | 0 new recruiters, 0 new emails | PASS |
| 12 | Follow-up | Threaded (`In-Reply-To`), only one per recruiter | PASS |
| 13 | Reply detection | Reply marked, own sent mail ignored | PASS |
| 14 | Resume tailoring | Skills missing from the resume are never added | PASS |

## Pipeline on demo data
12 posts fetched, 11 unique stored, **5 matching**, 5 recruiters, **3 valid emails**, 3 emails queued as Pending.
Rejected: older than 24 h 1, not Java 1, not USA 1, duplicate 1, bench marketer 1, spam 1, no keyword 1.

## Raw test output
```
test_12_pipeline_creates_pending_only ... ok
test_13_rerun_creates_no_duplicates ... ok
test_14_approval_required ... ok
test_15_send_success_goes_to_test_recipient_only ... ok
test_16_send_failure_marked_failed ... ok
test_17_cannot_send_twice ... ok
test_18_followup_is_threaded_and_not_duplicated ... ok
test_19_reply_detection ... ok
test_20_own_sent_mail_not_counted_as_reply ... ok
test_1_java_usa_2h_matches ... ok
test_2_java_usa_30h_rejected ... ok
test_3_python_rejected ... ok
test_4_india_rejected ... ok
test_5_duplicate_removed ... ok
test_6_bench_marketer_and_spam_rejected ... ok
test_7_matching_count ... ok
test_10_no_invented_emails ... ok
test_11_email_validator ... ok
test_8_missing_email_stays_missing_and_no_email_queued ... ok
test_9_invalid_email_flagged_and_not_queued ... ok
test_21_never_adds_skills_not_in_resume ... ok
Ran 21 tests in 0.488s
OK
```

Dashboard smoke test (Streamlit AppTest): loads and runs the pipeline with no errors.

## Bug found by testing
A duplicate repost was saved before the original, so the original was stored as "not matching". Fixed by saving matching jobs first (`main.py`); covered by test 1.
