"""CheckIt.AI fake-news pipeline DAG.

Architecture:
    Four independent extraction tasks run in parallel, fan into a
    single transformation task that consumes ``data/raw/*`` and
    produces the unified ``data/processed/checkit_*.jsonl``,
    ``build_dataset`` assembles the train/validation/test split and the
    data card, and ``acquire_images`` downloads the referenced images
    to make the dataset multimodal::

        [extract_guardian]
        [extract_fakeddit]  ─► [transform] ─► [build_dataset] ─► [acquire_images]
        [extract_snopes]                                              │
        [extract_liar]                          [load_to_postgres] ◄──┘ ─► [report_kpis]

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

Why ``acquire_images`` runs last (after the split):
    Image download is the slowest, most failure-prone step (one HTTP
    request per record). Keeping it last means a failure there never
    blocks the production of the unified dataset and split, and it can
    be retried on its own. It rewrites the split files in place,
    correcting ``has_image`` for any image that could not be fetched.

Why ``load_to_postgres`` after ``acquire_images``:
    The "L" of ETL: the finalised split files (with ``has_image``
    corrected) are loaded into Postgres as a full refresh inside one
    transaction, through a least-privilege role. It runs after image
    acquisition so the loaded rows reflect the multimodal-corrected
    dataset, and before ``report_kpis`` so a run ends with both the
    database and the dashboard in sync.

Why ``report_kpis`` closes the pipeline:
    Once the dataset is final, this task recomputes the ETL KPIs and
    regenerates the dashboard, so every run leaves an up-to-date,
    auditable picture of volumetry, rejection rates, image coverage and
    split integrity.

Why ``max_active_runs=1``:
    Every task writes to shared on-disk artefacts (``data/raw``,
    ``data/processed``, ``data/images``). Two concurrent runs would
    clobber each other's files. Serialising runs keeps the dataset
    consistent and makes a manual trigger safe even while a scheduled
    run exists.
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

from airflow import DAG
from airflow.operators.python import PythonOperator

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

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
    max_active_runs=1,
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

        liar.fetch(limit=100)

    def _transform():
        from src.transformation import pipeline

        pipeline.transform()

    def _build_dataset():
        from src.transformation import dataset

        dataset.build_dataset()

    def _acquire_images():
        from src.transformation import images

        images.acquire_all()

    def _load_to_postgres():
        from src.transformation import load

        load.load_splits()

    def _report_kpis():
        from src.monitoring import dashboard

        dashboard.main()

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
    acquire_images = PythonOperator(
        task_id="acquire_images",
        python_callable=_acquire_images,
    )
    load_to_postgres = PythonOperator(
        task_id="load_to_postgres",
        python_callable=_load_to_postgres,
    )
    report_kpis = PythonOperator(
        task_id="report_kpis",
        python_callable=_report_kpis,
    )

    (
        [extract_guardian, extract_fakeddit, extract_snopes, extract_liar]
        >> transform
        >> build_dataset
        >> acquire_images
        >> load_to_postgres
        >> report_kpis
    )
