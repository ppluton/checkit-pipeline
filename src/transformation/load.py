"""Load stage — persist the unified dataset into Postgres (the "L" of ETL).

Runs last in the DAG, after image acquisition has finalised
``metadata.has_image``. The load is a **full refresh** inside a single
transaction: ``checkit.articles`` is truncated and re-inserted from the
current split files. This makes the task idempotent — re-running it leaves
the table identical to the produced dataset — without needing a stable
natural key (the pipeline regenerates record UUIDs on each run).

Connection uses the least-privilege ``checkit_app`` role (see
``docker/postgres/init.sh``): it owns only the ``checkit`` schema and has
no rights on the Airflow metadata database.
"""

from sqlalchemy import create_engine, text

from src.transformation.dataset import SPLIT_NAMES
from src.utils.config import CHECKIT_DB_URL, PROCESSED_DIR
from src.utils.io import read_jsonl
from src.utils.logger import get_logger

logger = get_logger(__name__)

_DDL = """
CREATE TABLE IF NOT EXISTS checkit.articles (
    id UUID PRIMARY KEY,
    source TEXT NOT NULL,
    split TEXT,
    title TEXT,
    content TEXT,
    image_url TEXT,
    label TEXT,
    label_detail TEXT,
    language TEXT,
    domain TEXT,
    collected_at TIMESTAMPTZ,
    source_credibility TEXT,
    has_image BOOLEAN,
    label_method TEXT,
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT now()
)
"""

_INSERT = text(
    """
    INSERT INTO checkit.articles (
        id, source, split, title, content, image_url, label, label_detail,
        language, domain, collected_at, source_credibility, has_image, label_method
    ) VALUES (
        :id, :source, :split, :title, :content, :image_url, :label, :label_detail,
        :language, :domain, :collected_at, :source_credibility, :has_image, :label_method
    )
    """
)


def _to_row(record: dict, split: str) -> dict:
    """Flatten a unified record (with nested ``metadata``) into a table row."""
    meta = record.get("metadata") or {}
    return {
        "id": record.get("id"),
        "source": record.get("source"),
        "split": split,
        "title": record.get("title"),
        "content": record.get("content"),
        "image_url": record.get("image_url"),
        "label": record.get("label"),
        "label_detail": record.get("label_detail"),
        "language": record.get("language"),
        "domain": record.get("domain"),
        "collected_at": record.get("collected_at"),
        "source_credibility": meta.get("source_credibility"),
        "has_image": meta.get("has_image"),
        "label_method": meta.get("label_method"),
    }


def _collect_rows() -> list[dict]:
    rows: list[dict] = []
    for split in SPLIT_NAMES:
        path = PROCESSED_DIR / f"{split}.jsonl"
        if not path.exists():
            logger.warning("Split file %s not found, skipping", path.name)
            continue
        rows.extend(_to_row(record, split) for record in read_jsonl(path))
    return rows


def load_splits(db_url: str = CHECKIT_DB_URL) -> int:
    """Full-refresh ``checkit.articles`` from the split files; return row count."""
    rows = _collect_rows()
    engine = create_engine(db_url)
    try:
        with engine.begin() as conn:
            conn.execute(text(_DDL))
            conn.execute(text("TRUNCATE checkit.articles"))
            if rows:
                conn.execute(_INSERT, rows)
    finally:
        engine.dispose()
    logger.info("Loaded %d rows into checkit.articles", len(rows))
    return len(rows)


if __name__ == "__main__":
    load_splits()
