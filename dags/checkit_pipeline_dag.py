"""CheckIt.AI fake-news pipeline DAG.

Architecture:
    Four independent extraction tasks run in parallel, fan into a
    single transformation task that consumes ``data/raw/*`` and
    produces the unified ``data/processed/checkit_*.jsonl``, then a
    final task assembles the train/validation/test split and the data
    card::

        [extract_guardian]
        [extract_fakeddit]   ──►  [transform]  ──►  [build_dataset]
        [extract_snopes]
        [extract_liar]

Why a parallel fan-in:
    The three sources have no shared state — each writes to its own
    ``data/raw/<source>/`` subdirectory — so there is no reason to
    serialise them. Running them in parallel keeps total wall-clock
    time bounded by the slowest source (currently Snopes, ~30 s for
    20 articles with the politeness delay).

Why ``schedule="@daily"``:
    Snopes publishes ~20 fact-checks per week, the Guardian a few
    hundred articles/day, and Fakeddit is static. A daily run matches
    the freshness target of the spec without burning the Guardian
    quota.

Why one task per source rather than a dynamic mapping:
    Each source has its own quirks (API key, rate limit, structure)
    and its own retry profile (transient HTTP vs missing TSV file).
    Splitting them gives operators precise restart and observability,
    at the cost of three task definitions instead of one.

Why ``build_dataset`` is a separate task after ``transform``:
    Splitting and statistics operate on the *whole* unified dataset,
    so they must run once after every source has been normalised. As a
    distinct task they can be re-run (e.g. to reshuffle with a new
    seed) without repeating extraction or transformation.
"""

from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

default_args = {
    "owner": "checkit",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    dag_id="checkit_pipeline",
    default_args=default_args,
    description="ETL pipeline for fake news detection",
    schedule="@daily",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    tags=["checkit", "etl"],
) as dag:

    def _extract_guardian():
        from src.extraction import guardian

        guardian.fetch()

    def _extract_fakeddit():
        from src.extraction import fakeddit

        fakeddit.fetch()

    def _extract_snopes():
        from src.extraction import snopes

        snopes.fetch()

    def _extract_liar():
        from src.extraction import liar

        liar.fetch()

    def _transform():
        from src.transformation import pipeline

        pipeline.transform()

    def _build_dataset():
        from src.transformation import dataset

        dataset.build_dataset()

    extract_guardian = PythonOperator(
        task_id="extract_guardian",
        python_callable=_extract_guardian,
    )
    extract_fakeddit = PythonOperator(
        task_id="extract_fakeddit",
        python_callable=_extract_fakeddit,
    )
    extract_snopes = PythonOperator(
        task_id="extract_snopes",
        python_callable=_extract_snopes,
    )
    extract_liar = PythonOperator(
        task_id="extract_liar",
        python_callable=_extract_liar,
    )
    transform = PythonOperator(
        task_id="transform",
        python_callable=_transform,
    )
    build_dataset = PythonOperator(
        task_id="build_dataset",
        python_callable=_build_dataset,
    )

    (
        [extract_guardian, extract_fakeddit, extract_snopes, extract_liar]
        >> transform
        >> build_dataset
    )
