"""Transformation orchestration: raw JSONL -> unified processed JSONL.

Chains the three stages defined in this package — ``cleaner`` (dedup
+ structural sanitation), ``normalizer`` (map to the unified schema)
and ``validator`` (enforce invariants) — for each source, then writes
the validated ``Article`` records to ``data/processed/``.

``transform_source`` is the pure, IO-free core (tested directly);
``transform`` wraps it with the file reads/writes the DAG needs.
"""

from datetime import UTC, datetime

import pandas as pd

from src.transformation.cleaner import clean
from src.transformation.normalizer import normalize
from src.transformation.schema import Article
from src.transformation.validator import validate
from src.utils.io import latest_raw_file, read_jsonl, write_processed
from src.utils.logger import get_logger

logger = get_logger(__name__)

SOURCES = ("fakeddit", "guardian", "snopes", "liar")


def transform_source(df: pd.DataFrame, source: str, collected_at: datetime) -> list[Article]:
    """Run clean -> normalize -> validate for a single source."""
    if df.empty:
        return []
    return validate(normalize(clean(df, source), source, collected_at))


def transform(sources: tuple[str, ...] = SOURCES) -> int:
    """Read each source's latest raw batch and write a unified processed file.

    Returns the number of validated records written.
    """
    collected_at = datetime.now(UTC)
    articles: list[Article] = []
    for source in sources:
        path = latest_raw_file(source)
        if path is None:
            logger.warning("No raw file for source %r, skipping", source)
            continue
        df = pd.DataFrame(read_jsonl(path))
        kept = transform_source(df, source, collected_at)
        logger.info("%s: %d raw -> %d valid", source, len(df), len(kept))
        articles.extend(kept)

    _, written = write_processed(a.to_jsonl() for a in articles)
    return written


if __name__ == "__main__":
    transform()
