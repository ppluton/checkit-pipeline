"""LIAR dataset extraction (text-only auxiliary NLP source).

What this module does:
    Loads the original LIAR dataset (Wang, 2017) — 12 836 short political
    statements labelled with 6-level truthfulness by PolitiFact experts —
    and writes raw records as JSON Lines to ``data/raw/liar/``.

Why this source matters for CheckIt.AI:
    LIAR is the gold standard for **text-only** misinformation
    detection: human-expert labels, fine-grained 6-class taxonomy
    (``pants-fire`` → ``true``), and rich context (speaker, party,
    venue) that the model can use as auxiliary features.

    It is included as an **auxiliary NLP source**: the future
    multimodal classifier is expected to have a text-only branch that
    benefits from LIAR even though images are absent. The schema
    already accommodates this: ``image_url`` is nullable, and
    ``metadata.has_image`` will be ``false`` after normalisation.

    Concretely, LIAR is complementary to Snopes (Snopes covers viral
    claims, LIAR covers political statements) and gives the model a
    high-quality signal on fine label distinctions where Fakeddit's
    community labels are noisier.

Key design choices:
    * **Load from the original UCSB archive** rather than via
      ``load_dataset("liar")`` or HuggingFace's Parquet branch. The
      script loader is rejected by ``datasets>=4`` and the
      ``refs/convert/parquet`` auto-conversion no longer exists for
      ``ucsbnlp/liar`` (its ``converts`` ref is empty). The author's
      canonical ZIP of tab-separated splits is the stable, script-free
      source that does not depend on HF infrastructure.
    * **Single output file**, all three splits concatenated, with the
      origin split kept as a ``split`` column. The normalizer can
      stratify later if needed; the raw layer just persists what the
      source provides.
    * **No filtering at extraction** — every statement is kept,
      including ambiguous ``half-true`` labels. The normalizer
      decides what becomes ``label = fake``, ``real`` or ``null``.

Reference:
    - Paper: https://arxiv.org/abs/1705.00648
    - Data: https://www.cs.ucsb.edu/~william/data/liar_dataset.zip
"""

import csv
import io
import zipfile
from collections.abc import Iterator
from pathlib import Path

import pandas as pd
import requests

from src.utils.io import write_jsonl
from src.utils.logger import get_logger

logger = get_logger(__name__)

LIAR_ZIP_URL = "https://www.cs.ucsb.edu/~william/data/liar_dataset.zip"
SPLITS = ("train", "validation", "test")
_SPLIT_FILES = {"train": "train.tsv", "validation": "valid.tsv", "test": "test.tsv"}

# Original LIAR TSV layout (Wang, 2017): 14 tab-separated, unquoted columns.
# The label is already a string here (``false``, ``half-true``, ...), so no
# integer-to-text mapping is needed — it is read straight into ``label_text``,
# which the normalizer consumes.
_COLUMNS = [
    "id",
    "label_text",
    "statement",
    "subjects",
    "speaker",
    "job_title",
    "state_info",
    "party",
    "barely_true_counts",
    "false_counts",
    "half_true_counts",
    "mostly_true_counts",
    "pants_on_fire_counts",
    "context",
]


def _download_archive() -> zipfile.ZipFile:
    resp = requests.get(LIAR_ZIP_URL, timeout=30)
    resp.raise_for_status()
    return zipfile.ZipFile(io.BytesIO(resp.content))


def _load_split(archive: zipfile.ZipFile, split: str) -> pd.DataFrame:
    with archive.open(_SPLIT_FILES[split]) as handle:
        df = pd.read_csv(
            handle,
            sep="\t",
            header=None,
            names=_COLUMNS,
            dtype=str,
            quoting=csv.QUOTE_NONE,
            keep_default_na=False,
            encoding="utf-8",
        )
    df["split"] = split
    return df


def _iter_records(splits: tuple[str, ...], limit: int | None) -> Iterator[dict]:
    archive = _download_archive()
    yielded = 0
    for split in splits:
        logger.info("Loading split %r", split)
        df = _load_split(archive, split)
        logger.info("  %d records in split %r", len(df), split)
        for row in df.to_dict(orient="records"):
            yield row
            yielded += 1
            if limit is not None and yielded >= limit:
                return


def fetch(
    splits: tuple[str, ...] = SPLITS,
    limit: int | None = None,
    output_name: str = "liar.jsonl",
) -> Path:
    """Download and persist the LIAR dataset as raw JSON Lines.

    Args:
        splits: which LIAR splits to include. Default keeps all three
            (``train`` + ``validation`` + ``test``); the ``split``
            field is added to each record so downstream code can
            re-stratify.
        limit: optional cap on total records, useful for smoke tests.
        output_name: filename under ``data/raw/liar/``.

    Returns:
        Path to the JSONL file written.
    """
    out_path, _ = write_jsonl(
        _iter_records(splits, limit),
        "liar",
        filename=output_name,
        log_every=2000,
    )
    return out_path


if __name__ == "__main__":
    fetch(limit=100)
