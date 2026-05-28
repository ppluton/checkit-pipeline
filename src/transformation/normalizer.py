"""Normalisation stage of the transformation pipeline.

Responsibility:
    Map each source's idiosyncratic raw schema to the unified
    ``Article`` shape (one mapping function per source, dispatched on
    ``source``) and sanitise free text via ``cleaner.sanitize_text``.

Label policy (decided with the project owner):
    * **Fakeddit**: ``2_way_label`` 0/1 -> real/fake; ``6_way_label``
      -> ``label_detail`` (true / satire / manipulated_content / ...).
      Community labels => ``source_credibility = medium``,
      ``label_method = community``.
    * **Guardian**: no per-claim verdict, but the source is the
      high-credibility "real" baseline that balances the classifier,
      so ``label = real`` with ``label_method = human_expert`` (editorial
      review). ``label_detail`` is left null.
    * **Snopes** / **LIAR**: keep the verdict verbatim in
      ``label_detail`` and map only the *unambiguous extremes* to the
      binary ``label`` (Snopes ``True``/``False``; LIAR
      ``true``/``false``/``pants-fire``). Ambiguous verdicts
      (``Mixture``, ``half-true``, ...) get ``label = None`` so the
      nuance is preserved and not forced into a noisy binary.

``collected_at`` is supplied by the caller (the DAG's run timestamp)
rather than derived per source, since the raw layer does not record a
uniform collection time across all four sources.
"""

from datetime import datetime

import pandas as pd

from src.extraction.fakeddit import LABEL_2WAY, LABEL_6WAY
from src.transformation.cleaner import sanitize_text

LANGUAGE = "en"

_SNOPES_BINARY = {"true": "real", "false": "fake", "fake": "fake"}
_LIAR_BINARY = {"true": "real", "false": "fake", "pants-fire": "fake"}


def _record(
    *,
    source: str,
    title: str,
    content: str,
    image_url: str | None,
    label: str | None,
    label_detail: str | None,
    domain: str | None,
    credibility: str,
    label_method: str,
    collected_at: datetime,
) -> dict:
    return {
        "source": source,
        "title": sanitize_text(title),
        "content": sanitize_text(content),
        "image_url": image_url,
        "label": label,
        "label_detail": label_detail,
        "language": LANGUAGE,
        "domain": domain,
        "collected_at": collected_at,
        "metadata": {
            "source_credibility": credibility,
            "has_image": bool(image_url),
            "label_method": label_method,
        },
    }


def _from_fakeddit(row: dict, collected_at: datetime) -> dict | None:
    return _record(
        source="fakeddit",
        title=row.get("clean_title"),
        content=row.get("clean_title"),
        image_url=row.get("image_url"),
        label=LABEL_2WAY.get(str(row.get("2_way_label"))),
        label_detail=LABEL_6WAY.get(str(row.get("6_way_label"))),
        domain=row.get("domain"),
        credibility="medium",
        label_method="community",
        collected_at=collected_at,
    )


def _from_guardian(row: dict, collected_at: datetime) -> dict | None:
    fields = row.get("fields") or {}
    return _record(
        source="guardian",
        title=fields.get("headline") or row.get("webTitle"),
        content=fields.get("body") or fields.get("trailText"),
        image_url=fields.get("thumbnail"),
        label="real",
        label_detail=None,
        domain="theguardian.com",
        credibility="high",
        label_method="human_expert",
        collected_at=collected_at,
    )


def _from_snopes(row: dict, collected_at: datetime) -> dict | None:
    verdict = row.get("verdict")
    if not verdict or (isinstance(verdict, float) and pd.isna(verdict)):
        return None
    return _record(
        source="snopes",
        title=row.get("title") or row.get("rss_title"),
        content=row.get("claim") or row.get("description"),
        image_url=row.get("image_url"),
        label=_SNOPES_BINARY.get(str(verdict).strip().lower()),
        label_detail=str(verdict).strip(),
        domain="snopes.com",
        credibility="high",
        label_method="human_expert",
        collected_at=collected_at,
    )


def _from_liar(row: dict, collected_at: datetime) -> dict | None:
    label_text = row.get("label_text")
    return _record(
        source="liar",
        title=row.get("statement"),
        content=row.get("statement"),
        image_url=None,
        label=_LIAR_BINARY.get(str(label_text).strip().lower()),
        label_detail=label_text,
        domain="politifact.com",
        credibility="high",
        label_method="human_expert",
        collected_at=collected_at,
    )


_MAPPERS = {
    "fakeddit": _from_fakeddit,
    "guardian": _from_guardian,
    "snopes": _from_snopes,
    "liar": _from_liar,
}


def normalize(df: pd.DataFrame, source: str, collected_at: datetime) -> pd.DataFrame:
    """Apply the source-specific mapping to produce ``Article``-shaped rows.

    Rows the mapper rejects (e.g. Snopes narrative articles with no
    verdict) are dropped. ``id`` is intentionally left unset: the
    validator assigns it via the ``Article`` model's ``uuid4`` default.
    """
    mapper = _MAPPERS[source]
    records = [mapper(row, collected_at) for row in df.to_dict(orient="records")]
    return pd.DataFrame([r for r in records if r is not None])
