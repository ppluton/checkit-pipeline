"""Normalisation stage of the transformation pipeline.

Responsibility:
    Map each source's idiosyncratic raw schema to the unified
    ``Article`` model defined in ``schema.py``. One mapping function
    per source, dispatched by the ``source`` argument.

Mapping rules (per source):
    * **Fakeddit**: ``2_way_label`` (0/1) → ``label`` (real/fake);
      ``6_way_label`` (0..5) → ``label_detail`` (true / satire /
      misleading_content / ...). ``source_credibility = medium``,
      ``label_method = community``.
    * **Guardian**: no binary label (editorial source). Leave ``label``
      empty, set ``source_credibility = high`` and use the section as
      ``label_detail`` only if useful for downstream.
    * **Snopes**: keep the original verdict verbatim in
      ``label_detail`` (``Mixture``, ``Mostly True``, ...). Map only
      the unambiguous extremes to ``label`` (``True`` → real,
      ``False``/``Fake`` → fake). ``source_credibility = high``,
      ``label_method = human_expert``.

Status: stub. Implemented in Étape 3 of the project roadmap.
"""

import pandas as pd


def normalize(df: pd.DataFrame, source: str) -> pd.DataFrame:
    """Apply the source-specific mapping to produce ``Article`` rows."""
    raise NotImplementedError
