"""Snopes fact-check extraction.

What this module does:
    Reads the Snopes RSS feed, fetches each article page, and extracts
    the fact-check verdict (``True`` / ``False`` / ``Mixture`` /
    ``Unproven`` / ``Outdated`` / ...), the claim being reviewed, and
    the social image. Writes raw records as JSON Lines to
    ``data/raw/snopes/``.

Why this source matters for CheckIt.AI:
    Snopes is the gold-standard fact-checker for English-language
    content: verdicts are produced by human experts with a
    transparent methodology, and the rating vocabulary preserves
    nuances that a binary ``fake``/``real`` would destroy
    (``Mixture``, ``Mostly True``, ``Originated as Satire``,
    ``Correct Attribution``). These nuances feed our ``label_detail``
    field and let the model learn finer-grained distinctions.

Two extraction strategies are combined, in order:

1. **ClaimReview JSON-LD (preferred)** — schema.org structured data
   embedded by most fact-checkers for SEO. Stable across HTML
   redesigns; gives us the verdict and claim verbatim. About 65 % of
   Snopes URLs from the RSS feed expose it (the rest are narrative
   ``/news/`` articles that are not formal fact-checks).
2. **CSS selectors via BeautifulSoup (fallback)** — used when
   JSON-LD is missing. Imperfect by design: narrative articles do
   not encode a verdict, so we accept ``verdict = None`` in that case
   and let the normalizer drop them.

Why ``protego`` instead of ``urllib.robotparser``:
    Snopes' ``robots.txt`` starts with a ``Content-Signal:``
    directive (a non-standard extension). The standard-library
    parser fails on that line and, by safety, denies access to every
    user-agent — including ``Googlebot``. ``protego`` (the parser
    used by Scrapy) handles the directive correctly and gives a
    proper allow/deny decision per UA.

Why a 1.5 s rate limit:
    Snopes' ``robots.txt`` does not publish a ``Crawl-delay``. 1.5 s
    is well below the documented limits of comparable fact-checkers
    and keeps us in the "polite crawler" category without dragging
    the run beyond a minute for 20 articles.

References:
- RSS feed: https://www.snopes.com/feed/
- ClaimReview schema: https://schema.org/ClaimReview
- Protego: https://github.com/scrapy/protego
"""

import json
import time
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Iterator
from urllib.parse import urlparse

import feedparser
import requests
from bs4 import BeautifulSoup
from protego import Protego

from src.utils.config import RAW_DIR
from src.utils.logger import get_logger

logger = get_logger(__name__)

RSS_URL = "https://www.snopes.com/feed/"
USER_AGENT = "checkit-pipeline/0.1 (+https://github.com/ppluton/checkit-pipeline)"
REQUEST_TIMEOUT = 30
RATE_LIMIT_SLEEP = 1.5


@lru_cache(maxsize=8)
def _robots_for(netloc_root: str) -> Protego | None:
    try:
        response = requests.get(
            f"{netloc_root}/robots.txt",
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.warning("Could not fetch robots.txt at %s: %s. Assuming allowed.", netloc_root, exc)
        return None
    return Protego.parse(response.text)


def _robots_allowed(url: str) -> bool:
    parsed = urlparse(url)
    rp = _robots_for(f"{parsed.scheme}://{parsed.netloc}")
    if rp is None:
        return True
    return rp.can_fetch(url, USER_AGENT)


def _fetch_html(url: str) -> str:
    response = requests.get(
        url,
        headers={"User-Agent": USER_AGENT},
        timeout=REQUEST_TIMEOUT,
    )
    response.raise_for_status()
    return response.text


def _flatten_jsonld(node: object) -> Iterator[dict]:
    if isinstance(node, list):
        for item in node:
            yield from _flatten_jsonld(item)
    elif isinstance(node, dict):
        yield node
        if "@graph" in node:
            yield from _flatten_jsonld(node["@graph"])


def _extract_claim_review(soup: BeautifulSoup) -> dict | None:
    for script in soup.find_all("script", type="application/ld+json"):
        raw = script.string or ""
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        for item in _flatten_jsonld(data):
            if item.get("@type") == "ClaimReview":
                return item
    return None


def _meta_content(soup: BeautifulSoup, prop: str, attr: str = "property") -> str | None:
    tag = soup.find("meta", attrs={attr: prop})
    return tag.get("content") if tag else None


def _parse_article(html: str, url: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    claim_review = _extract_claim_review(soup)

    title = _meta_content(soup, "og:title") or (
        soup.h1.get_text(strip=True) if soup.h1 else ""
    )
    image_url = _meta_content(soup, "og:image")
    description = _meta_content(soup, "description", attr="name")

    if claim_review:
        rating = claim_review.get("reviewRating", {})
        verdict = rating.get("alternateName") or rating.get("ratingValue")
        claim = claim_review.get("claimReviewed")
        rating_value = rating.get("ratingValue")
    else:
        rating_tag = (
            soup.select_one(".rating-label-text")
            or soup.select_one(".rating-label")
            or soup.select_one("[class*=rating]")
        )
        verdict = rating_tag.get_text(strip=True) if rating_tag else None
        claim_tag = soup.select_one(".claim-text") or soup.select_one(".claim")
        claim = claim_tag.get_text(strip=True) if claim_tag else None
        rating_value = None

    return {
        "url": url,
        "title": title,
        "claim": claim,
        "verdict": verdict,
        "rating_value": rating_value,
        "image_url": image_url,
        "description": description,
        "scraped_at": datetime.now(timezone.utc).isoformat(),
        "extraction_method": "claim_review_jsonld" if claim_review else "css_fallback",
    }


def _iter_feed_entries(limit: int) -> Iterator[dict]:
    logger.info("Reading RSS feed: %s", RSS_URL)
    feed = feedparser.parse(RSS_URL)
    if feed.bozo:
        logger.warning("RSS parse warning: %s", feed.bozo_exception)
    for entry in feed.entries[:limit]:
        yield {
            "url": entry.link,
            "title": entry.title,
            "published": entry.get("published"),
            "summary": entry.get("summary"),
        }


def fetch(limit: int = 20) -> Path:
    """Scrape ``limit`` most-recent Snopes articles into ``data/raw/snopes/``.

    Args:
        limit: cap on entries pulled from the RSS feed. The feed
            typically exposes ~20 latest items.

    Returns:
        The path of the JSONL file written.

    Notes:
        Failures on a single article (HTTP errors, parse errors) are
        logged but do not abort the run — the rest of the batch is
        still produced. This matches the spec's requirement that
        "data engineering errors should be observable, not fatal".
    """
    out_dir = RAW_DIR / "snopes"
    out_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_path = out_dir / f"snopes_{timestamp}.jsonl"

    written = 0
    skipped = 0
    with out_path.open("w", encoding="utf-8") as f:
        for entry in _iter_feed_entries(limit):
            if not _robots_allowed(entry["url"]):
                logger.warning("Blocked by robots.txt: %s", entry["url"])
                skipped += 1
                continue
            try:
                html = _fetch_html(entry["url"])
                article = _parse_article(html, entry["url"])
                article["rss_title"] = entry["title"]
                article["rss_published"] = entry["published"]
                f.write(json.dumps(article, ensure_ascii=False) + "\n")
                written += 1
                logger.info(
                    "[%d/%d] %s -> verdict=%r (%s)",
                    written,
                    limit,
                    entry["url"],
                    article.get("verdict"),
                    article["extraction_method"],
                )
            except Exception as exc:
                logger.exception("Failed to scrape %s: %s", entry["url"], exc)
                skipped += 1
            time.sleep(RATE_LIMIT_SLEEP)

    logger.info("Done: %d records to %s (skipped %d)", written, out_path, skipped)
    return out_path


if __name__ == "__main__":
    fetch(limit=20)
