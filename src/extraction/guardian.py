"""The Guardian Open Platform extraction.

What this module does:
    Pulls recent Guardian articles from a set of fact-based sections
    and writes raw responses as JSON Lines to ``data/raw/guardian/``.
    Non-article content (liveblogs, crosswords, galleries) and records
    missing a thumbnail are filtered out.

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
    credibility "real"* baseline; The Guardian fills that role and is
    labelled ``real`` by the normalizer.

Why no search query (and why this matters):
    An earlier version searched for ``"misinformation OR fact-check
    OR fake news"``. That introduced a label-leakage trap: it returned
    articles *about* misinformation, saturated with words like
    "hoax" / "false claim", yet labelled ``real``. A classifier would
    learn the topic vocabulary instead of veracity. We therefore drop
    the query entirely and sample neutral general news across
    fact-based sections, so the ``real`` label reflects credible
    reporting rather than a misinformation theme.

Key design choices:
    * **Section filter, no ``q``** — ``SECTIONS`` selects text-rich,
      fact-based desks (world, science, technology, business,
      environment) without thematic bias.
    * **``type == "article"`` only** — liveblogs and crosswords carry
      noisy or non-prose bodies; we keep only editorial articles.
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
from collections.abc import Iterator
from pathlib import Path

import requests

from src.utils.config import GUARDIAN_API_KEY
from src.utils.io import write_jsonl
from src.utils.logger import get_logger

logger = get_logger(__name__)

BASE_URL = "https://content.guardianapis.com/search"
SECTIONS = "world|science|technology|business|environment"
DEFAULT_FIELDS = "headline,trailText,body,thumbnail,byline,publication,lastModified"
ALLOWED_TYPES = {"article"}
PAGE_SIZE = 50
REQUEST_TIMEOUT = 30
RATE_LIMIT_SLEEP = 1.0


def _fetch_page(page: int, from_date: str | None) -> dict:
    if not GUARDIAN_API_KEY:
        raise RuntimeError(
            "GUARDIAN_API_KEY is not set. Register a free key at "
            "https://open-platform.theguardian.com/access/."
        )

    params = {
        "section": SECTIONS,
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


def _iter_articles(from_date: str | None, max_pages: int) -> Iterator[dict]:
    for page in range(1, max_pages + 1):
        body = _fetch_page(page, from_date)
        results = body.get("results", [])
        if not results:
            return

        logger.info(
            "Page %d/%d: %d results (total=%d)", page, body["pages"], len(results), body["total"]
        )
        yield from results

        if page >= body["pages"]:
            return
        time.sleep(RATE_LIMIT_SLEEP)


def _is_wanted(article: dict, require_image: bool) -> bool:
    """Keep only editorial articles that satisfy the multimodal contract."""
    if article.get("type") not in ALLOWED_TYPES:
        return False
    return not require_image or bool(article.get("fields", {}).get("thumbnail"))


def fetch(
    from_date: str | None = None,
    max_pages: int = 1,
    require_image: bool = True,
) -> Path:
    """Pull Guardian articles into a timestamped JSONL under ``data/raw/guardian/``.

    Args:
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
        for article in _iter_articles(from_date, max_pages):
            if not _is_wanted(article, require_image):
                skipped += 1
                continue
            yield article

    out_path, _ = write_jsonl(_iter_with_filter(), "guardian")
    if skipped:
        logger.info("Skipped %d non-article or imageless results", skipped)
    return out_path


if __name__ == "__main__":
    fetch(max_pages=1)
