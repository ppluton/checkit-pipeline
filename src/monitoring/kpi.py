"""ETL KPIs — the numbers that tell whether the pipeline is healthy.

Splits responsibilities:
    * Pure helpers (``rejection_rate``, ``per_source_rejection``,
      ``leakage_count``) hold the logic and are unit-tested without IO.
    * ``compute_kpis`` reads the on-disk artefacts (latest raw batch per
      source, the unified file, the split files) and assembles the full
      KPI dictionary.
    * ``render_report`` turns that dictionary into a Markdown report.

The visual dashboard (``src/monitoring/dashboard.py``) consumes the same
``compute_kpis`` output, so the figures and the report never disagree.
"""

from collections import Counter, defaultdict

from src.transformation.dataset import SPLIT_NAMES, compute_stats
from src.utils.config import PROCESSED_DIR
from src.utils.io import latest_raw_file, read_jsonl
from src.utils.logger import get_logger

logger = get_logger(__name__)

SOURCES = ("fakeddit", "guardian", "snopes", "liar")


def rejection_rate(raw_count: int, valid_count: int) -> float:
    if raw_count <= 0:
        return 0.0
    return round((raw_count - valid_count) / raw_count, 4)


def per_source_rejection(raw_counts: dict[str, int], records: list[dict]) -> dict[str, dict]:
    valid_by_source = Counter(r.get("source") for r in records)
    out: dict[str, dict] = {}
    for source, raw in raw_counts.items():
        valid = valid_by_source.get(source, 0)
        out[source] = {
            "raw": raw,
            "valid": valid,
            "rejected": raw - valid,
            "rate": rejection_rate(raw, valid),
        }
    return out


def _content_key(record: dict) -> str:
    return (record.get("content") or "").strip().lower()


def leakage_count(splits: dict[str, list[dict]]) -> int:
    """Number of content keys present in more than one split."""
    seen: dict[str, set[str]] = defaultdict(set)
    for split_name, records in splits.items():
        for record in records:
            seen[_content_key(record)].add(split_name)
    return sum(1 for split_set in seen.values() if len(split_set) > 1)


def _raw_line_count(source: str) -> int:
    path = latest_raw_file(source)
    return len(read_jsonl(path)) if path else 0


def compute_kpis() -> dict:
    """Assemble every ETL KPI from the artefacts currently on disk.

    Stats are read from the split files (the final dataset, with
    ``has_image`` corrected after image acquisition) rather than the
    unified batch, so the KPIs match the data card. The unified batch
    is only a fallback when the splits do not exist yet.
    """
    splits = {}
    for split in SPLIT_NAMES:
        path = PROCESSED_DIR / f"{split}.jsonl"
        splits[split] = read_jsonl(path) if path.exists() else []

    final = [record for records in splits.values() for record in records]
    if not final:
        batches = sorted(PROCESSED_DIR.glob("checkit_*.jsonl"), key=lambda p: p.stat().st_mtime)
        final = read_jsonl(batches[-1]) if batches else []

    raw_counts = {source: _raw_line_count(source) for source in SOURCES}
    stats = compute_stats(final)

    return {
        "stats": stats,
        "rejection": per_source_rejection(raw_counts, final),
        "split_sizes": {name: len(records) for name, records in splits.items()},
        "leakage": leakage_count(splits),
        "image_coverage_rate": round(stats["has_image"]["true"] / stats["total"], 4)
        if stats["total"]
        else 0.0,
    }


def render_report(kpis: dict) -> str:
    """Render the KPI dictionary as a Markdown report."""
    stats = kpis["stats"]
    rej = kpis["rejection"]
    rej_rows = "\n".join(
        f"| {s} | {d['raw']} | {d['valid']} | {d['rejected']} | {d['rate']:.0%} |"
        for s, d in rej.items()
    )
    split_rows = " · ".join(f"{name} {n}" for name, n in kpis["split_sizes"].items())
    return f"""# Rapport KPI de l'ETL — CheckIt.AI

> Généré par `src/monitoring/kpi.py`. Relancer met les chiffres à jour.

## Volumétrie et taux de rejet par source

| Source | Brut | Valides | Rejetés | Taux de rejet |
| --- | --- | --- | --- | --- |
{rej_rows}

## Dataset unifié

- Total : **{stats["total"]}** records
- Labels : {", ".join(f"{k} {v}" for k, v in stats["by_label"].items())}
- Couverture image réelle : **{kpis["image_coverage_rate"]:.0%}** \
({stats["has_image"]["true"]}/{stats["total"]})

## Découpage et intégrité

- Tailles : {split_rows}
- Fuites de contenu inter-split : **{kpis["leakage"]}** (cible : 0)
"""
