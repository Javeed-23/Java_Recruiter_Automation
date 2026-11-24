# Demo video script (about 4 to 5 minutes)

Tip: record your phone screen (built-in screen recorder) while the deployed dashboard is open, and speak over it.

**0:00 Intro (20 s)**
"Hi, I'm <name>. This is my Java Developer Job Search and Recruiter Email Automation System. It finds Java C2C and W2 posts, filters them, collects recruiter details, and sends personalised emails after my approval."

**0:20 Important note (20 s)**
"The data shown is clearly marked demo data. I did not log into LinkedIn or scrape it, because that breaks its terms. A real authorised API can be connected through the .env file. In demo mode every email goes only to my own test address."

**0:40 Architecture (40 s)**
Show the README diagram. "Search, filter, recruiters, resume tailoring, email with approval, then follow-up and reply tracking. Everything is stored in SQLite and shown in Streamlit."

**1:20 Run the pipeline (40 s)**
Tap **Run search + filter pipeline**. "It fetched 12 posts. 5 match: Java, USA, last 24 hours, with the keywords."

**2:00 Metrics and tables (50 s)**
Point at the metrics. Open **Jobs**: show Matching, then Rejected, with reasons (too old, Python, India, duplicate, bench marketer, spam, no keyword). Use the keyword filter. Open **Recruiters**: "One has a missing email and one has an invalid email. Those are never emailed and I never invent an address."

**2:50 Email approval (60 s)**
Open **Email approval**. Show the preview: recipient, subject, tailored text, attachment. "I must tick the box and press Approve & send." Send one. Show Sent in the metrics. "If sending fails, it is saved as Failed with the reason and I can retry."

**3:50 Follow-up and analytics (40 s)**
Tick "pretend 7 days passed", queue the follow-up, mention it is a threaded reply and also needs approval. Press Simulate reply. Open **Analytics**: sent, replied, reply rate.

**4:30 Tests and close (30 s)**
"21 automated tests cover every required scenario and all pass. Thank you."
