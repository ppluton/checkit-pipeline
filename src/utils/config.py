"""Project-wide configuration loaded from environment variables.

Why a dedicated module:
    All secrets and tunables enter the codebase here. Application code
    never calls ``os.getenv`` directly, which means:
      * Required configuration is discoverable in one file.
      * Tests can monkeypatch a single module instead of the environment.
      * Adding a new secret only requires one line here.

Why ``python-dotenv``:
    The spec requires ``.env`` based configuration. We load it once at
    import time so the rest of the codebase can rely on the values
    being populated.

Convention:
    Every API key / credential is uppercase and ends in ``_API_KEY`` or
    similar. Directory constants are ``Path`` objects rooted at
    ``PROJECT_ROOT`` so callers do not have to recompute relative paths.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

GUARDIAN_API_KEY = os.getenv("GUARDIAN_API_KEY")
FAKEDDIT_TSV_PATH = os.getenv("FAKEDDIT_TSV_PATH") or str(
    PROJECT_ROOT / "data" / "samples" / "fakeddit_multimodal_sample.tsv"
)

# Postgres load target (the ``L`` of the ETL). Defaults match the bundled
# docker-compose Postgres and its least-privilege ``checkit_app`` role; set
# ``CHECKIT_DB_URL`` directly to point at another instance (e.g. Neon).
POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5433")
CHECKIT_DB = os.getenv("CHECKIT_DB", "checkit")
CHECKIT_APP_USER = os.getenv("CHECKIT_APP_USER", "checkit_app")
CHECKIT_APP_PASSWORD = os.getenv("CHECKIT_APP_PASSWORD", "checkit_app")
CHECKIT_DB_URL = os.getenv("CHECKIT_DB_URL") or (
    f"postgresql+psycopg2://{CHECKIT_APP_USER}:{CHECKIT_APP_PASSWORD}"
    f"@{POSTGRES_HOST}:{POSTGRES_PORT}/{CHECKIT_DB}"
)

RAW_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
