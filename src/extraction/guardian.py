"""The Guardian Open Platform extraction.

Queries the Guardian Content API for recent articles and writes raw
records as JSON Lines. Articles missing a thumbnail are filtered out to
preserve the text + image multimodal constraint.

The Guardian provides editorial-quality journalism: collected articles
are treated as a high-credibility "real" baseline, to be combined with
fact-checker sources (Snopes, FakeNewsNet) for the negative class.

Reference: https://open-platform.theguardian.com/documentation/
"""

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

import requests

from src.utils.config import GUARDIAN_API_KEY, RAW_DIR
from src.utils.logger import get_logger

logger = get_logger(__name__)

BASE_URL = "https://content.guardianapis.com/search"
DEFAULT_QUERY = "misinformation OR disinformation OR fact-check OR fake news"
DEFAULT_FIELDS = "headline,trailText,body,thumbnail,byline,publication,lastModified"
PAGE_SIZE = 50
REQUEST_TIMEOUT = 30
RATE_LIMIT_SLEEP = 1.0


def _fetch_page(query: str, page: int, from_date: str | None) -> dict:
    if not GUARDIAN_API_KEY:
        raise RuntimeError(
            "GUARDIAN_API_KEY is not set. Register a free key at "
            "https://open-platform.theguardian.com/access/."
        )

    params = {
        "q": query,
        "api-key": GUARDIAN_API_KEY,
        "page": page,
        "page-size": PAGE_SIZE,
        "show-fields": DEFAULT_FIELDS,
        "order-by": "newest",
    }
    if from_date:
        params["from-date"] = from_date

    response = requests.get(BASE_URL, params=params, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    return response.json()["response"]


def _iter_articles(
    query: str,
    from_date: str | None,
    max_pages: int,
) -> Iterator[dict]:
    for page in range(1, max_pages + 1):
        body = _fetch_page(query, page, from_date)
        results = body.get("results", [])
        if not results:
            return

        logger.info("Page %d/%d: %d results (total=%d)", page, body["pages"], len(results), body["total"])
        for article in results:
            yield article

        if page >= body["pages"]:
            return
        time.sleep(RATE_LIMIT_SLEEP)


def fetch(
    query: str = DEFAULT_QUERY,
    from_date: str | None = None,
    max_pages: int = 1,
    require_image: bool = True,
) -> Path:
    out_dir = RAW_DIR / "guardian"
    out_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_path = out_dir / f"guardian_{timestamp}.jsonl"

    written = 0
    skipped = 0
    with out_path.open("w", encoding="utf-8") as f:
        for article in _iter_articles(query, from_date, max_pages):
            if require_image and not article.get("fields", {}).get("thumbnail"):
                skipped += 1
                continue
            f.write(json.dumps(article, ensure_ascii=False) + "\n")
            written += 1

    logger.info("Done: %d records to %s (skipped %d without thumbnail)", written, out_path, skipped)
    return out_path


if __name__ == "__main__":
    fetch(max_pages=1)
