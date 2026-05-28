"""Image acquisition stage — makes the dataset genuinely multimodal.

Runs after ``build_dataset``. For every record that advertises an
``image_url``, it downloads the image and stores it under
``data/images/<id>.<ext>`` (the path is reconstructable from the
record id, so no schema field is needed). The records' source files
are rewritten in place with ``metadata.has_image`` corrected.

Failure policy (decided with the project owner):
    A record whose image cannot be fetched (404, timeout, non-image
    body) is **kept as text-only**: ``has_image`` is set to ``false``
    and no text is lost. The model's text branch can still use it.

Why a separate stage rather than downloading at extraction time:
    The current sources' image URLs (Guardian, Reddit, Snopes proxy)
    are stable enough that a post-hoc pass is safe, and it keeps the
    network logic in one idempotent place instead of duplicated across
    extractors. (FakeNewsNet, whose URLs expire fast, will need
    download-at-collection when it is implemented.)

Testability:
    The network call is injected as ``fetch`` so ``acquire_images`` —
    which holds the orchestration logic — is exercised without any
    real HTTP or mocking. ``_http_fetch`` is the thin real adapter.
"""

import json
import time
from collections.abc import Callable
from pathlib import Path
from urllib.parse import urlparse

import requests

from src.utils.config import PROJECT_ROOT
from src.utils.io import read_jsonl, write_processed
from src.utils.logger import get_logger

logger = get_logger(__name__)

IMAGES_DIR = PROJECT_ROOT / "data" / "images"
SPLIT_FILES = ("train.jsonl", "validation.jsonl", "test.jsonl")
USER_AGENT = "checkit-pipeline/0.1 (+https://github.com/ppluton/checkit-pipeline)"
REQUEST_TIMEOUT = 30
RATE_LIMIT_SLEEP = 1.0

_CONTENT_TYPE_EXT = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}

# Fetcher contract: url -> (body, content_type) on success, or None on failure.
Fetcher = Callable[[str], tuple[bytes, str] | None]


def _extension_for(content_type: str, url: str) -> str:
    primary = (content_type or "").split(";")[0].strip().lower()
    if primary in _CONTENT_TYPE_EXT:
        return _CONTENT_TYPE_EXT[primary]
    suffix = Path(urlparse(url).path).suffix.lower()
    return suffix if suffix in {".jpg", ".jpeg", ".png", ".webp", ".gif"} else ".jpg"


def _is_valid_image(content_type: str, body: bytes) -> bool:
    return bool(body) and (content_type or "").split(";")[0].strip().lower().startswith("image/")


def _http_fetch(url: str, session: requests.Session) -> tuple[bytes, str] | None:
    try:
        response = session.get(url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.warning("Image fetch failed for %s: %s", url, exc)
        return None
    return response.content, response.headers.get("Content-Type", "")


def acquire_images(records: list[dict], images_dir: Path, fetch: Fetcher) -> dict:
    """Download images for ``records``, correcting ``has_image`` on failure.

    Mutates each record's ``metadata.has_image`` in place. Returns a
    ``{downloaded, failed, skipped, total}`` summary.
    """
    images_dir.mkdir(parents=True, exist_ok=True)
    stats = {"downloaded": 0, "failed": 0, "skipped": 0, "total": len(records)}

    for record in records:
        url = record.get("image_url")
        if not url:
            stats["skipped"] += 1
            continue

        result = fetch(url)
        if result is None or not _is_valid_image(result[1], result[0]):
            record.setdefault("metadata", {})["has_image"] = False
            stats["failed"] += 1
            continue

        body, content_type = result
        dest = images_dir / f"{record['id']}{_extension_for(content_type, url)}"
        dest.write_bytes(body)
        record.setdefault("metadata", {})["has_image"] = True
        stats["downloaded"] += 1

    return stats


def acquire_all(images_dir: Path = IMAGES_DIR) -> dict:
    """Run image acquisition over every split file, rewriting them in place."""
    from src.utils.config import PROCESSED_DIR

    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    def fetch(url: str) -> tuple[bytes, str] | None:
        result = _http_fetch(url, session)
        time.sleep(RATE_LIMIT_SLEEP)
        return result

    totals = {"downloaded": 0, "failed": 0, "skipped": 0, "total": 0}
    for name in SPLIT_FILES:
        path = PROCESSED_DIR / name
        if not path.exists():
            logger.warning("Split file %s not found, skipping", name)
            continue
        records = read_jsonl(path)
        stats = acquire_images(records, images_dir, fetch)
        write_processed((json.dumps(r, ensure_ascii=False) for r in records), name)
        logger.info("%s: %s", name, stats)
        for key in totals:
            totals[key] += stats[key]

    from src.transformation.dataset import refresh_data_card

    refresh_data_card()
    logger.info("Image acquisition totals: %s", totals)
    return totals


if __name__ == "__main__":
    acquire_all()
