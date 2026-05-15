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

    def _extract_newsdata():
        from src.extraction import newsdata
        newsdata.fetch()

    def _extract_fakeddit():
        from src.extraction import fakeddit
        fakeddit.fetch()

    def _extract_snopes():
        from src.extraction import snopes
        snopes.fetch()

    def _transform():
        pass

    extract_newsdata = PythonOperator(
        task_id="extract_newsdata",
        python_callable=_extract_newsdata,
    )
    extract_fakeddit = PythonOperator(
        task_id="extract_fakeddit",
        python_callable=_extract_fakeddit,
    )
    extract_snopes = PythonOperator(
        task_id="extract_snopes",
        python_callable=_extract_snopes,
    )
    transform = PythonOperator(
        task_id="transform",
        python_callable=_transform,
    )

    [extract_newsdata, extract_fakeddit, extract_snopes] >> transform
