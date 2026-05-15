"""The Guardian Open Platform extraction.

What this module does:
    Queries the Guardian Content API for recent articles matching a
    misinformation-related search query and writes raw responses as
    JSON Lines to ``data/raw/guardian/``. Records missing a thumbnail
    are filtered out to preserve the text + image multimodal
    constraint.

Why The Guardian (and not NewsData.io as in the original spec):
    NewsData.io's free tier is 200 requests/day and the broader
    product is paid. For a portfolio project we needed a source that
    is fully free, has a public free-tier API, and offers
    editorial-grade journalism. The Guardian Open Platform fits all
    three: a developer key delivered in seconds, 5 000 calls/day, JSON
    responses, and articles with named bylines and editorial review.

Why this source matters for CheckIt.AI:
    Fakeddit and Snopes are skewed toward fake / dubious content (by
    construction: they are fact-checkers or labelled fake-news
    datasets). To train a balanced classifier we need a *high
    credibility "real"* baseline; The Guardian fills that role.

Key design choices:
    * **Pagination loop with explicit ``max_pages``** — the Guardian
      reports a global ``pages`` field that can reach thousands; we
      cap the loop to avoid runaway runs and stay friendly with the
      daily quota.
    * **``RATE_LIMIT_SLEEP = 1.0 s``** between pages even though the
      published limit is much higher (12 calls/s). Courtesy delays
      cost us nothing here and demonstrate good API citizenship.
    * **``require_image=True`` by default** — articles without a
      thumbnail break the multimodal contract. We log them as
      ``skipped`` so the metric remains observable.
    * **Distinct output file per run** (timestamped) — Airflow can
      schedule overlapping retries without overwriting prior batches.
      Idempotency on the ``(source, url)`` key is enforced by the
      normalizer, not here.

Reference: https://open-platform.theguardian.com/documentation/
"""

import time
from pathlib import Path
from typing import Iterator

import requests

from src.utils.config import GUARDIAN_API_KEY
from src.utils.io import write_jsonl
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
    """Pull Guardian articles into a timestamped JSONL under ``data/raw/guardian/``.

    Args:
        query: Guardian-flavoured search expression (boolean ``OR`` /
            ``AND`` supported). Defaults to a misinformation-themed query.
        from_date: ``YYYY-MM-DD`` lower bound. ``None`` lets the API
            decide (newest first regardless of date).
        max_pages: how many pages of ``PAGE_SIZE`` items to fetch.
            Caps API spend per run.
        require_image: skip articles without a ``thumbnail`` field to
            preserve the multimodal contract.

    Returns:
        The path of the JSONL file written.
    """
    skipped = 0

    def _iter_with_filter() -> Iterator[dict]:
        nonlocal skipped
        for article in _iter_articles(query, from_date, max_pages):
            if require_image and not article.get("fields", {}).get("thumbnail"):
                skipped += 1
                continue
            yield article

    out_path, _ = write_jsonl(_iter_with_filter(), "guardian")
    if skipped:
        logger.info("Skipped %d articles without thumbnail", skipped)
    return out_path


if __name__ == "__main__":
    fetch(max_pages=1)
