"""Environment-based settings for the API."""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load backend/.env first, then root .env (root overrides or supplies RUN_LOCAL)
ROOT_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"
BACKEND_ENV_FILE = Path(__file__).resolve().parents[1] / ".env"

if BACKEND_ENV_FILE.exists():
    load_dotenv(BACKEND_ENV_FILE)

if ROOT_ENV_FILE.exists():
    load_dotenv(ROOT_ENV_FILE, override=True)


def is_local_mode() -> bool:
    """Return whether CodeMap is configured to run in offline local mode."""
    val = os.getenv("RUN_LOCAL", "").strip().lower()

    print(val)
    if val in ("true", "1", "yes", "on"):
        return True
    mode = os.getenv("CODEMAP_MODE", "").strip().lower()
    return mode == "local"


def required_setting(name: str) -> str:
    """Return a required environment setting or fail with a clear message."""
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def allowed_origins() -> list[str]:
    """Return the frontend origins allowed to call the API."""
    raw_origins = os.getenv("CORS_ORIGINS", "http://localhost:5173")
    return [origin.strip() for origin in raw_origins.split(",") if origin.strip()]
