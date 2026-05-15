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
    * **Load via HuggingFace's auto-converted Parquet branch** rather
      than the deprecated ``load_dataset("liar")`` Python loader.
      Recent ``datasets`` versions reject script-based datasets;
      Parquet files on the ``refs/convert/parquet`` branch work as
      a stable, script-free format.
    * **Single output file**, all three splits concatenated, with the
      origin split kept as a ``split`` column. The normalizer can
      stratify later if needed; the raw layer just persists what the
      source provides.
    * **No filtering at extraction** — every statement is kept,
      including ambiguous ``half-true`` labels. The normalizer
      decides what becomes ``label = fake``, ``real`` or ``null``.

Reference:
    - Paper: https://arxiv.org/abs/1705.00648
    - HF dataset: https://huggingface.co/datasets/ucsbnlp/liar
"""

import json
from pathlib import Path
from typing import Iterator

import pandas as pd

from src.utils.config import RAW_DIR
from src.utils.logger import get_logger

logger = get_logger(__name__)

PARQUET_BASE = (
    "https://huggingface.co/datasets/ucsbnlp/liar/resolve/"
    "refs%2Fconvert%2Fparquet/default"
)
SPLITS = ("train", "validation", "test")

LIAR_LABELS: dict[int, str] = {
    0: "false",
    1: "half-true",
    2: "mostly-true",
    3: "true",
    4: "barely-true",
    5: "pants-fire",
}


def _load_split(split: str) -> pd.DataFrame:
    url = f"{PARQUET_BASE}/{split}/0000.parquet"
    df = pd.read_parquet(url)
    df["split"] = split
    return df


def _iter_records(splits: tuple[str, ...], limit: int | None) -> Iterator[dict]:
    yielded = 0
    for split in splits:
        logger.info("Loading split %r", split)
        df = _load_split(split)
        logger.info("  %d records in split %r", len(df), split)
        for row in df.to_dict(orient="records"):
            row["label_text"] = LIAR_LABELS.get(row["label"])
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
        splits: which HF splits to include. Default keeps all three
            (``train`` + ``validation`` + ``test``); the ``split``
            field is added to each record so downstream code can
            re-stratify.
        limit: optional cap on total records, useful for smoke tests.
        output_name: filename under ``data/raw/liar/``.

    Returns:
        Path to the JSONL file written.
    """
    out_dir = RAW_DIR / "liar"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / output_name

    written = 0
    with out_path.open("w", encoding="utf-8") as f:
        for record in _iter_records(splits, limit):
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            written += 1
            if written % 2000 == 0:
                logger.info("Wrote %d records", written)

    logger.info("Done: %d records to %s", written, out_path)
    return out_path


if __name__ == "__main__":
    fetch(limit=100)
