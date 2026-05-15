"""Validation stage of the transformation pipeline.

Responsibility:
    Enforce the dataset's invariants before any record is written to
    ``data/processed/``:
      * Every record validates against the ``Article`` Pydantic model.
      * ``image_url`` is a syntactically valid URL.
      * ``title`` and ``content`` are non-empty.
      * Rejected rows are logged with a precise reason so failures are
        observable, not silent.

Why a dedicated stage:
    Cleaning and normalisation may still produce invalid rows (e.g.
    if a source changes its API contract without notice). The
    validator is the last gate before the dataset reaches the model
    training job.

Status: stub. Implemented in Étape 3 of the project roadmap.
"""

import pandas as pd


def validate(df: pd.DataFrame) -> pd.DataFrame:
    """Return only the rows that satisfy the Article invariants."""
    raise NotImplementedError
