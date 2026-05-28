"""Cleaning stage of the transformation pipeline.

Responsibility:
    Structural sanitation of raw records before normalisation:
      * Drop duplicates on the source-specific natural key (URL or
        post ID — duplicates are common when scheduled reruns overlap).
      * Own the text-sanitisation primitive (``sanitize_text``): strip
        residual HTML, unescape entities, normalise Unicode (NFKC) and
        collapse whitespace.

Why ``sanitize_text`` lives here but is applied by the normalizer:
    Cleaning is conceptually the "HTML/Unicode" stage, so the logic
    belongs here. But only the normalizer knows *which* raw field
    carries the human text (``clean_title`` for Fakeddit, the nested
    ``fields.body`` for the Guardian, ...). The normalizer therefore
    imports ``sanitize_text`` and applies it as it maps each field,
    rather than the cleaner guessing column names per source.

Why field-level pruning is deferred to the validator:
    The validator is the single gate for the dataset's invariants
    (non-empty title/content, valid image URL). Duplicating those
    checks here would split the contract across two modules.
"""

import html
import re
import unicodedata

import pandas as pd
from bs4 import BeautifulSoup

NATURAL_KEY = {
    "fakeddit": "id",
    "guardian": "id",
    "snopes": "url",
    "liar": "id",
}

_WHITESPACE = re.compile(r"\s+")


def sanitize_text(value: object) -> str:
    """Strip HTML, unescape entities, NFKC-normalise and collapse whitespace."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    text = BeautifulSoup(html.unescape(str(value)), "html.parser").get_text(separator=" ")
    text = unicodedata.normalize("NFKC", text)
    return _WHITESPACE.sub(" ", text).strip()


def clean(df: pd.DataFrame, source: str) -> pd.DataFrame:
    """Drop null-key and duplicate rows on the source's natural key."""
    key = NATURAL_KEY[source]
    return (
        df.dropna(subset=[key]).drop_duplicates(subset=[key], keep="first").reset_index(drop=True)
    )
