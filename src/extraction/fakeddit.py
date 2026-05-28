"""FAKEDDIT extraction.

What this module does:
    Reads the *multimodal* Fakeddit TSV (~1 million Reddit posts with
    paired images and 6-class labels) and writes raw records as JSON
    Lines to ``data/raw/fakeddit/``. Rows missing an ``image_url`` are
    dropped so the output stays multimodal-only.

Why this source matters for CheckIt.AI:
    Fakeddit is the project's primary training source: it is large
    enough to train, natively multimodal, and labelled at two
    granularities (binary real/fake + 6 sub-categories including
    *satire*, *misleading content*, *manipulated content*). The
    6-class label is critical: a satirical post is not the same kind
    of misinformation as a manipulated image, and the model needs
    that nuance to be useful in production.

Key design choices:
    * **Streaming with ``pd.read_csv(chunksize=...)``** — the file has
      ~1 M rows and would not fit in memory if loaded fully on a
      modest workstation. The reader yields 10k-row chunks and we
      process them sequentially.
    * **Raw output, no normalisation here** — this module respects the
      ``extract → transform`` contract: it only filters, never
      interprets. Label mapping (e.g. ``LABEL_6WAY[5] →
      "manipulated_content"``) is exposed as constants for the
      ``normalizer`` to reuse, not applied at extraction time.
    * **Configurable source path** — ``FAKEDDIT_TSV_PATH`` accepts
      either a local file path or a remote URL. ``pandas`` handles
      both transparently, which keeps the code identical between
      local development and a future Airflow worker pulling from S3.

Reference: https://github.com/entitize/Fakeddit
"""

from collections.abc import Iterator
from pathlib import Path

import pandas as pd

from src.utils.config import FAKEDDIT_TSV_PATH
from src.utils.io import write_jsonl
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
        chunk = chunk[chunk["image_url"].fillna("").str.len() > 0]
        for row in chunk.to_dict(orient="records"):
            yield row
            yielded += 1
            if limit is not None and yielded >= limit:
                return


def fetch(limit: int | None = None, output_name: str = "fakeddit.jsonl") -> Path:
    """Stream the Fakeddit TSV to ``data/raw/fakeddit/<output_name>``.

    Args:
        limit: optional row cap, useful for smoke tests. ``None`` means
            "read the whole TSV".
        output_name: name of the JSONL file inside ``data/raw/fakeddit/``.

    Returns:
        The path of the JSONL file actually written.
    """
    source = _resolve_source()
    logger.info("Reading from %s", source)
    out_path, _ = write_jsonl(_iter_records(source, limit), "fakeddit", filename=output_name)
    return out_path


if __name__ == "__main__":
    fetch(limit=100)
