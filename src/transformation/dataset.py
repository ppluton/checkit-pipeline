"""Dataset assembly: statistics and a leakage-safe stratified split.

This stage runs after the unified ``data/processed/*.jsonl`` file is
produced. It does two things the model training step depends on:

1. ``compute_stats`` — a JSON-serialisable summary of the dataset
   (sizes, label and source distributions, image coverage, content
   length, duplicate count) used both for the data card and to spot
   anomalies early.
2. ``assign_splits`` — a deterministic train/validation/test split,
   stratified by ``(source, label)`` so every split keeps the same
   mix, and **leakage-safe**: records sharing identical content are
   grouped and always land in the same split, so the same article can
   never appear in both train and test.

Why determinism (fixed ``seed``):
    A reproducible split is a hard requirement for honest evaluation —
    re-running the pipeline must yield the same train/test partition,
    otherwise results are not comparable across runs.
"""

import hashlib
import json
import statistics
from collections import Counter, defaultdict
from datetime import UTC, datetime
from random import Random

from src.utils.config import PROCESSED_DIR, PROJECT_ROOT
from src.utils.io import read_jsonl, write_processed
from src.utils.logger import get_logger

logger = get_logger(__name__)

DEFAULT_RATIOS = (0.70, 0.15, 0.15)
SPLIT_NAMES = ("train", "validation", "test")
DEFAULT_SEED = 42


def _content_key(record: dict) -> str:
    text = (record.get("content") or "").strip().lower()
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _label_key(record: dict) -> str:
    label = record.get("label")
    return "null" if label is None else str(label)


def compute_stats(records: list[dict]) -> dict:
    """Return a JSON-serialisable summary of the dataset."""
    lengths = [len(r.get("content") or "") for r in records]
    content_groups = Counter(_content_key(r) for r in records)
    has_image = Counter(bool(r.get("metadata", {}).get("has_image")) for r in records)
    return {
        "total": len(records),
        "by_source": dict(Counter(r.get("source") for r in records)),
        "by_label": dict(Counter(_label_key(r) for r in records)),
        "by_label_detail": dict(Counter(r.get("label_detail") for r in records)),
        "by_language": dict(Counter(r.get("language") for r in records)),
        "has_image": {"true": has_image[True], "false": has_image[False]},
        "content_length": {
            "min": min(lengths) if lengths else 0,
            "max": max(lengths) if lengths else 0,
            "mean": round(statistics.mean(lengths), 1) if lengths else 0,
            "median": int(statistics.median(lengths)) if lengths else 0,
        },
        "duplicate_content_groups": sum(1 for n in content_groups.values() if n > 1),
    }


def _split_sizes(n: int, ratios: tuple[float, float, float]) -> tuple[int, int, int]:
    n_train = round(n * ratios[0])
    n_val = round(n * ratios[1])
    if n_train + n_val > n:
        n_val = n - n_train
    return n_train, n_val, n - n_train - n_val


def assign_splits(
    records: list[dict],
    ratios: tuple[float, float, float] = DEFAULT_RATIOS,
    seed: int = DEFAULT_SEED,
) -> list[dict]:
    """Tag each record with a ``split`` key, stratified and leakage-safe.

    Records are grouped by content (so duplicates stay together), each
    group is assigned to a stratum keyed by ``(source, label)`` of its
    first member, and within each stratum the groups are shuffled
    deterministically and partitioned by ``ratios``.
    """
    groups: dict[str, list[dict]] = defaultdict(list)
    for record in records:
        groups[_content_key(record)].append(record)

    strata: dict[tuple[str, str], list[str]] = defaultdict(list)
    for key, members in groups.items():
        head = members[0]
        strata[(head.get("source"), _label_key(head))].append(key)

    rng = Random(seed)
    for stratum_key in sorted(strata, key=lambda k: (str(k[0]), k[1])):
        keys = sorted(strata[stratum_key])
        rng.shuffle(keys)
        n_train, n_val, _ = _split_sizes(len(keys), ratios)
        bounds = {"train": (0, n_train), "validation": (n_train, n_train + n_val)}
        for i, key in enumerate(keys):
            split = next(
                (name for name, (lo, hi) in bounds.items() if lo <= i < hi),
                "test",
            )
            for member in groups[key]:
                member["split"] = split

    return records


def _md_table(headers: list[str], rows: list[list]) -> str:
    def line(cells: list) -> str:
        return "| " + " | ".join(str(c) for c in cells) + " |"

    sep = "| " + " | ".join("---" for _ in headers) + " |"
    return "\n".join([line(headers), sep, *(line(r) for r in rows)])


def render_data_card(stats: dict, breakdown: dict, generated_on: str = "") -> str:
    """Render a Markdown data card from the dataset stats and split breakdown."""
    sources = sorted(stats["by_source"])
    split_rows = [
        [
            split,
            *(breakdown.get(split, {}).get(s, 0) for s in sources),
            sum(breakdown.get(split, {}).values()),
        ]
        for split in SPLIT_NAMES
    ]
    cl = stats["content_length"]
    header = f"# Fiche dataset — CheckIt.AI{f' (généré le {generated_on})' if generated_on else ''}"
    return f"""{header}

> Document généré automatiquement par `src/transformation/dataset.py`.
> Ne pas éditer à la main : relancer la génération met les chiffres à jour.

## Vue d'ensemble

- **Total de records** : {stats["total"]}
- **Langues** : {", ".join(f"{k} ({v})" for k, v in stats["by_language"].items())}
- **Groupes de contenu dupliqué** : {stats["duplicate_content_groups"]}

## Répartition par source

{_md_table(["Source", "Records"], [[s, stats["by_source"][s]] for s in sources])}

## Répartition des labels

{_md_table(["Label", "Records"], [[k, v] for k, v in stats["by_label"].items()])}

Le label `null` n'est pas une absence d'information : il marque les verdicts
*nuancés* (Mixture, half-true…) pour lesquels on refuse de forcer un binaire
trompeur. La nuance d'origine est conservée dans `label_detail`.

## Couverture image (multimodal)

- Avec image : {stats["has_image"]["true"]}
- Sans image (texte seul) : {stats["has_image"]["false"]}

## Longueur de contenu (caractères)

- min {cl["min"]} · médiane {cl["median"]} · moyenne {cl["mean"]} · max {cl["max"]}

## Découpage train / validation / test

{_md_table(["Split", *sources, "Total"], split_rows)}

**Méthodologie.** Split déterministe (seed fixe), stratifié par
`(source × label)` pour que chaque partition garde le même mélange de sources
et de classes. Il est *leakage-safe* : les records au contenu identique sont
regroupés et placés dans le même split, donc un même texte ne peut jamais
apparaître à la fois en entraînement et en test.

## Limites connues

- **Multimodal partiel** : on stocke des adresses d'images, pas encore les
  images elles-mêmes (elles peuvent expirer).
- **Hétérogénéité des sources** : statements politiques (LIAR), posts Reddit
  (Fakeddit), claims (Snopes) et articles de presse (Guardian) ont des styles
  très différents. Le split stratifié atténue le risque que le modèle apprenne
  la *source* plutôt que la véracité, mais une évaluation out-of-distribution
  resterait plus exigeante.
- **Taille** : le volume actuel est modeste ; Fakeddit n'est pas encore passé
  à l'échelle.
"""


def build_dataset(seed: int = DEFAULT_SEED) -> dict:
    """Read the latest unified file, write splits, and refresh the data card.

    Returns the computed statistics.
    """
    batches = sorted(PROCESSED_DIR.glob("checkit_*.jsonl"), key=lambda p: p.stat().st_mtime)
    if not batches:
        raise FileNotFoundError(
            "No data/processed/checkit_*.jsonl batch found. Run the pipeline first."
        )
    latest = batches[-1]
    records = read_jsonl(latest)
    logger.info("Building dataset from %s (%d records)", latest.name, len(records))

    stats = compute_stats(records)
    tagged = assign_splits(records, seed=seed)

    breakdown: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for record in tagged:
        breakdown[record["split"]][record["source"]] += 1

    for split in SPLIT_NAMES:
        lines = (
            json.dumps({k: v for k, v in r.items() if k != "split"}, ensure_ascii=False)
            for r in tagged
            if r["split"] == split
        )
        _, count = write_processed(lines, f"{split}.jsonl")
        logger.info("Wrote %d records to %s.jsonl", count, split)

    card = render_data_card(
        stats,
        {s: dict(breakdown[s]) for s in SPLIT_NAMES},
        generated_on=datetime.now(UTC).date().isoformat(),
    )
    card_path = PROJECT_ROOT / "docs" / "data_card.md"
    card_path.write_text(card, encoding="utf-8")
    logger.info("Wrote data card to %s", card_path)
    return stats


if __name__ == "__main__":
    build_dataset()
