"""config.py - central settings. Secrets are read from environment variables (.env), never hard-coded."""
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent / ".env")
except ImportError:  # python-dotenv is optional; plain environment variables still work
    pass

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

# The keywords required by the internship brief.
KEYWORDS = ["C2C", "Bench", "Sales", "W2", "Full-Time", "Hotlist"]
ROLE = "Java Developer"
MAX_AGE_HOURS = 24
FOLLOWUP_DAYS = 7


def db_path() -> Path:
    """Read at call time so tests can point to a temporary database."""
    return Path(os.getenv("DB_PATH", str(DATA_DIR / "recruiter_automation.db")))


def get(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def is_demo_mode() -> bool:
    """DEMO_MODE=true (default): every email goes to TEST_RECIPIENT, never to a recruiter."""
    return get("DEMO_MODE", "true").lower() not in ("false", "0", "no")
