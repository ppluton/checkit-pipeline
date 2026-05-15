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
FAKEDDIT_TSV_PATH = os.getenv("FAKEDDIT_TSV_PATH")

RAW_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
