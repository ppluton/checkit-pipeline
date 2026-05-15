"""IO helpers shared across extraction modules.

Why this lives here:
    Every extractor needs the same five-step ritual to persist raw
    records: resolve ``data/raw/<source>/``, ensure the directory
    exists, pick a filename (optionally timestamped), open a UTF-8
    handle, and write one JSON object per line. Centralising it
    removes ~15 duplicated lines per extractor and gives a single
    place to evolve the on-disk format (compression, partitioning,
    schema attribution, etc.).
"""

import json
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path

from src.utils.config import RAW_DIR
from src.utils.logger import get_logger

logger = get_logger(__name__)


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def write_jsonl(
    records: Iterable[dict],
    source: str,
    filename: str | None = None,
    log_every: int = 1000,
) -> tuple[Path, int]:
    """Persist ``records`` as JSON Lines under ``data/raw/<source>/``.

    Args:
        records: iterable of JSON-serialisable dicts. Streamed, so the
            caller is free to yield from a generator over a large
            source without materialising it.
        source: subdirectory name under ``data/raw/`` (e.g.
            ``"guardian"``, ``"snopes"``).
        filename: target filename. ``None`` produces
            ``<source>_<UTC-timestamp>.jsonl``, which is suitable for
            scheduled runs that should not overwrite each other.
            Static datasets like Fakeddit may pass a fixed name.
        log_every: emit a progress log every N records written.

    Returns:
        ``(path, count)`` — the path of the file written and the
        number of records actually persisted.
    """
    out_dir = RAW_DIR / source
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / (filename or f"{source}_{_timestamp()}.jsonl")

    written = 0
    with out_path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            written += 1
            if written % log_every == 0:
                logger.info("Wrote %d records to %s", written, out_path.name)

    logger.info("Done: %d records to %s", written, out_path)
    return out_path, written
