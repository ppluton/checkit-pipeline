"""Cleaning stage of the transformation pipeline.

Responsibility:
    Take raw records from ``data/raw/<source>/*.jsonl`` and remove
    structural noise before normalisation:
      * Drop duplicates on the source-specific natural key (URL or
        post ID — duplicates are common when reruns overlap).
      * Drop rows missing the bare-minimum fields (text and image).
      * Strip residual HTML, decode mojibake, collapse whitespace.

Why a separate stage:
    Cleaning is purely *structural* — it does not interpret the data.
    Keeping it before ``normalizer`` makes the latter free to assume
    well-formed inputs.

Status: stub. Implemented in Étape 3 of the project roadmap.
"""

import pandas as pd


def clean(df: pd.DataFrame) -> pd.DataFrame:
    """Drop duplicates, prune malformed rows, sanitise text fields."""
    raise NotImplementedError
