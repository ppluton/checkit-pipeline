"""Visual KPI dashboard for the ETL.

Consumes ``kpi.compute_kpis`` and renders a four-panel figure
(volumetry vs rejection, label balance, image coverage, split sizes)
plus the Markdown KPI report. Static PNG output keeps the dashboard
reproducible: re-running the script regenerates identical figures from
the current dataset.
"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from src.monitoring.kpi import compute_kpis, render_report  # noqa: E402
from src.utils.config import PROJECT_ROOT  # noqa: E402
from src.utils.logger import get_logger  # noqa: E402

logger = get_logger(__name__)

DASHBOARD_PNG = PROJECT_ROOT / "docs" / "etl_dashboard.png"
KPI_REPORT_MD = PROJECT_ROOT / "docs" / "etl_kpi_report.md"


def build_figure(kpis: dict) -> plt.Figure:
    stats = kpis["stats"]
    rej = kpis["rejection"]
    fig, axes = plt.subplots(2, 2, figsize=(12, 9))
    fig.suptitle("CheckIt.AI — Tableau de bord KPI de l'ETL", fontsize=14, fontweight="bold")

    sources = list(rej)
    raw = [rej[s]["raw"] for s in sources]
    valid = [rej[s]["valid"] for s in sources]
    x = range(len(sources))
    ax = axes[0][0]
    ax.bar([i - 0.2 for i in x], raw, width=0.4, label="brut", color="#9aa5b1")
    ax.bar([i + 0.2 for i in x], valid, width=0.4, label="valides", color="#2f6f4f")
    ax.set_xticks(list(x))
    ax.set_xticklabels(sources)
    ax.set_title("Volumétrie : brut vs valides")
    ax.legend()

    ax = axes[0][1]
    labels = list(stats["by_label"])
    ax.bar(
        labels,
        [stats["by_label"][k] for k in labels],
        color=["#2f6f4f", "#b03a2e", "#9aa5b1"][: len(labels)],
    )
    ax.set_title("Répartition des labels")

    ax = axes[1][0]
    ax.pie(
        [stats["has_image"]["true"], stats["has_image"]["false"]],
        labels=["avec image", "texte seul"],
        autopct="%1.0f%%",
        colors=["#2e86c1", "#d5dbdb"],
    )
    ax.set_title(f"Couverture image (multimodal) — {kpis['image_coverage_rate']:.0%}")

    ax = axes[1][1]
    splits = kpis["split_sizes"]
    ax.bar(list(splits), list(splits.values()), color="#7d3c98")
    ax.set_title(f"Découpage train/val/test — fuites : {kpis['leakage']}")

    fig.tight_layout(rect=(0, 0, 1, 0.96))
    return fig


def save_dashboard(kpis: dict, out_path: Path) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig = build_figure(kpis)
    fig.savefig(out_path, dpi=120)
    plt.close(fig)
    return out_path


def main() -> None:
    kpis = compute_kpis()
    save_dashboard(kpis, DASHBOARD_PNG)
    KPI_REPORT_MD.write_text(render_report(kpis), encoding="utf-8")
    logger.info("Wrote %s and %s", DASHBOARD_PNG, KPI_REPORT_MD)


if __name__ == "__main__":
    main()
