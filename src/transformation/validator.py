"""Validation stage of the transformation pipeline.

Responsibility:
    The single gate for the dataset's invariants before any record
    reaches ``data/processed/``:
      * Every record validates against the ``Article`` Pydantic model
        (closed label vocabulary, metadata literals, types).
      * ``title`` and ``content`` are non-empty after stripping.
      * ``image_url``, when present, is a syntactically valid URL.
    Rejected rows are logged with a precise reason so failures are
    observable rather than silent.

Why it returns ``Article`` objects:
    The writer downstream serialises with ``Article.to_jsonl()``; the
    validator is the boundary where loosely-typed DataFrame rows become
    strongly-typed domain objects.
"""

from urllib.parse import urlparse

import pandas as pd
from pydantic import ValidationError

from src.transformation.schema import Article
from src.utils.logger import get_logger

logger = get_logger(__name__)


def _is_valid_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def _clean_row(row: dict) -> dict:
    return {k: (None if isinstance(v, float) and pd.isna(v) else v) for k, v in row.items()}


def validate(df: pd.DataFrame) -> list[Article]:
    """Return the rows that satisfy the ``Article`` invariants as objects."""
    valid: list[Article] = []
    for raw in df.to_dict(orient="records"):
        row = _clean_row(raw)
        if not str(row.get("title") or "").strip():
            logger.warning("Rejected: empty title (source=%s)", row.get("source"))
            continue
        if not str(row.get("content") or "").strip():
            logger.warning("Rejected: empty content (source=%s)", row.get("source"))
            continue
        image_url = row.get("image_url")
        if image_url is not None and not _is_valid_url(str(image_url)):
            logger.warning(
                "Rejected: invalid image_url %r (source=%s)", image_url, row.get("source")
            )
            continue
        try:
            valid.append(Article(**row))
        except ValidationError as exc:
            logger.warning(
                "Rejected: schema violation (source=%s): %s", row.get("source"), exc.errors()
            )
    return valid
