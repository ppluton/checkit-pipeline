"""Interactive Streamlit KPI dashboard for the ETL.

Reads the same ``compute_kpis()`` output as the static matplotlib
dashboard and the Markdown report, so the three never disagree. The
charts are interactive (hover, zoom, sortable tables) and a source
filter lets a non-technical reader drill into per-source volumetry.

Run with::

    uv run streamlit run src/monitoring/streamlit_app.py

The data preparation lives in :func:`build_frames` (a pure function, unit
tested) so the rendering layer stays a thin shell over it.
"""

import pandas as pd
import streamlit as st

from src.monitoring.kpi import compute_kpis


def build_frames(kpis: dict) -> dict:
    """Turn the KPI dictionary into the labelled frames the UI renders."""
    stats = kpis["stats"]
    rejection = kpis["rejection"]

    total_raw = sum(d["raw"] for d in rejection.values())
    total_valid = sum(d["valid"] for d in rejection.values())
    overall_reject = (total_raw - total_valid) / total_raw if total_raw else 0.0

    volumetry = pd.DataFrame(
        {
            "brut": {s: d["raw"] for s, d in rejection.items()},
            "valides": {s: d["valid"] for s, d in rejection.items()},
        }
    )
    rejection_table = pd.DataFrame(
        [
            {
                "source": s,
                "brut": d["raw"],
                "valides": d["valid"],
                "rejetés": d["rejected"],
                "taux de rejet": f"{d['rate']:.0%}",
            }
            for s, d in rejection.items()
        ]
    )
    labels = pd.Series(stats["by_label"], name="records")
    image_coverage = pd.Series(
        {"avec image": stats["has_image"]["true"], "texte seul": stats["has_image"]["false"]},
        name="records",
    )
    splits = pd.Series(kpis["split_sizes"], name="records")
    label_detail = pd.DataFrame(
        sorted(stats["by_label_detail"].items(), key=lambda kv: kv[1], reverse=True),
        columns=["verdict d'origine", "records"],
    )

    return {
        "overall_reject": overall_reject,
        "volumetry": volumetry,
        "rejection_table": rejection_table,
        "labels": labels,
        "image_coverage": image_coverage,
        "splits": splits,
        "label_detail": label_detail,
    }


def main() -> None:
    st.set_page_config(page_title="CheckIt.AI — KPI ETL", page_icon=":bar_chart:", layout="wide")

    kpis = compute_kpis()
    stats = kpis["stats"]
    frames = build_frames(kpis)
    total = stats["total"]

    st.title("CheckIt.AI — Tableau de bord KPI de l'ETL")
    st.caption(
        "Chiffres lus depuis le dataset produit (`data/processed/`). "
        "Relancer le pipeline met le tableau à jour."
    )

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Records unifiés", total)
    c2.metric(
        "Couverture image",
        f"{kpis['image_coverage_rate']:.0%}",
        f"{stats['has_image']['true']}/{total}",
        delta_color="off",
    )
    c3.metric("Taux de rejet global", f"{frames['overall_reject']:.0%}")
    c4.metric("Fuites inter-split", kpis["leakage"], "cible : 0", delta_color="off")

    st.divider()

    left, right = st.columns([2, 1])
    with left:
        st.subheader("Volumétrie : brut vs valides")
        sources = list(frames["volumetry"].index)
        chosen = st.multiselect("Sources affichées", sources, default=sources)
        st.bar_chart(frames["volumetry"].loc[chosen] if chosen else frames["volumetry"])
    with right:
        st.subheader("Taux de rejet par source")
        st.dataframe(frames["rejection_table"], hide_index=True, use_container_width=True)

    st.divider()

    g1, g2, g3 = st.columns(3)
    with g1:
        st.subheader("Répartition des labels")
        st.bar_chart(frames["labels"])
    with g2:
        st.subheader("Couverture multimodale")
        st.bar_chart(frames["image_coverage"])
    with g3:
        st.subheader("Découpage train / val / test")
        st.bar_chart(frames["splits"])

    with st.expander("Nuances de labels préservées (`label_detail`)"):
        st.caption(
            "Les verdicts nuancés (Mixture, half-true, satire…) ne sont pas écrasés "
            "en binaire : le label d'origine reste disponible pour l'entraînement."
        )
        st.dataframe(frames["label_detail"], hide_index=True, use_container_width=True)


if __name__ == "__main__":
    main()
