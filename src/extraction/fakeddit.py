"""FAKEDDIT extraction.

Streams the multimodal Fakeddit TSV (~1M rows) and writes raw records to
``data/raw/fakeddit/`` as JSON Lines. Source is configured via
``FAKEDDIT_TSV_PATH`` (local file or URL). Only rows with an ``image_url``
are kept.

Reference: https://github.com/entitize/Fakeddit
"""

import json
from pathlib import Path
from typing import Iterator

import pandas as pd

from src.utils.config import FAKEDDIT_TSV_PATH, RAW_DIR
from src.utils.logger import get_logger

logger = get_logger(__name__)

LABEL_6WAY = {
    "0": "true",
    "1": "satire",
    "2": "misleading_content",
    "3": "imposter_content",
    "4": "false_connection",
    "5": "manipulated_content",
}

LABEL_2WAY = {"0": "real", "1": "fake"}

CHUNK_SIZE = 10_000


def _resolve_source() -> str:
    if not FAKEDDIT_TSV_PATH:
        raise RuntimeError(
            "FAKEDDIT_TSV_PATH is not set. Point it to a local TSV file or "
            "a downloadable URL. See https://github.com/entitize/Fakeddit."
        )
    return FAKEDDIT_TSV_PATH


def _iter_records(source: str, limit: int | None) -> Iterator[dict]:
    reader = pd.read_csv(
        source,
        sep="\t",
        chunksize=CHUNK_SIZE,
        on_bad_lines="skip",
        dtype=str,
    )
    yielded = 0
    for chunk in reader:
        chunk = chunk.dropna(subset=["image_url"])
        for row in chunk.to_dict(orient="records"):
            yield row
            yielded += 1
            if limit is not None and yielded >= limit:
                return


def fetch(limit: int | None = None, output_name: str = "fakeddit.jsonl") -> Path:
    source = _resolve_source()
    out_dir = RAW_DIR / "fakeddit"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / output_name

    logger.info("Reading from %s", source)
    written = 0
    with out_path.open("w", encoding="utf-8") as f:
        for record in _iter_records(source, limit):
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            written += 1
            if written % 1000 == 0:
                logger.info("Wrote %d records", written)

    logger.info("Done: %d records to %s", written, out_path)
    return out_path


if __name__ == "__main__":
    fetch(limit=100)
