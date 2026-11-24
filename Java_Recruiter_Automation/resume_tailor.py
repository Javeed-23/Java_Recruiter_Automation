"""resume_tailor.py - rewrite the resume summary / skill order to match a job description.

HONESTY RULE: it only re-orders and re-words what is already in your resume. A skill the job asks for but your
resume does not contain is reported as a "gap" and is NEVER added.
"""
import json
import re
from pathlib import Path

import config

SKILL_VOCAB = ["Java", "Spring Boot", "Spring", "Hibernate", "Microservices", "REST APIs", "Kafka", "AWS", "Azure",
               "Docker", "Kubernetes", "SQL", "MySQL", "Oracle", "MongoDB", "Jenkins", "CI/CD", "Angular", "React",
               "JUnit", "Maven", "Git"]


def load_resume(path=None) -> dict:
    with open(path or config.DATA_DIR / "sample_resume.json", encoding="utf-8") as f:
        return json.load(f)


def _found(term: str, text: str) -> bool:
    return bool(re.search(r"(?<![A-Za-z0-9])" + re.escape(term) + r"(?![A-Za-z0-9])", text, re.I))


def tailor_resume(resume: dict, job_description: str) -> dict:
    """Return {"matched","gaps","skills","projects","summary"} for one job."""
    wanted = [t for t in SKILL_VOCAB if _found(t, job_description)]
    wanted = [t for t in wanted if not any(t != o and t.lower() in o.lower() for o in wanted)]  # 'Spring' inside 'Spring Boot'
    have = {s.lower(): s for s in resume["skills"]}
    matched = [have[t.lower()] for t in wanted if t.lower() in have]
    gaps = [t for t in wanted if t.lower() not in have]
    skills = matched + [s for s in resume["skills"] if s not in matched]
    projects = sorted(resume.get("projects", []),
                      key=lambda p: -len({t.lower() for t in p["tech"]} & {m.lower() for m in matched}))
    top = ", ".join(matched[:5]) if matched else ", ".join(resume["skills"][:5])
    summary = (f"{resume['title']} with {resume['years_experience']}+ years of experience, "
               f"hands-on with {top}. Looking for a role where I can apply these skills.")
    return {"matched": matched, "gaps": gaps, "skills": skills, "projects": projects, "summary": summary}


def render_resume_text(resume: dict, tailored: dict) -> str:
    lines = [resume["name"], f"{resume['email']} | {resume['phone']} | {resume['linkedin']}", "",
             "SUMMARY", tailored["summary"], "", "SKILLS", ", ".join(tailored["skills"]), "", "PROJECTS"]
    for p in tailored["projects"]:
        lines.append(f"- {p['name']}: {p['description']} ({', '.join(p['tech'])})")
    return "\n".join(lines) + "\n"


def save_tailored_resume(resume: dict, tailored: dict, job: dict) -> str:
    """Save a text resume for this job and return its path."""
    out = config.DATA_DIR / "tailored_resumes"
    out.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "_", f"{job.get('company','job')}_{job.get('title','')}".lower()).strip("_")
    path = out / f"resume_{slug}.txt"
    path.write_text(render_resume_text(resume, tailored), encoding="utf-8")
    return str(path)


if __name__ == "__main__":
    r = load_resume()
    t = tailor_resume(r, "Java, Spring Boot, Microservices, Kafka, AWS, Docker and SQL")
    print("Matched:", t["matched"], "\nGaps (NOT added):", t["gaps"], "\n", t["summary"])
