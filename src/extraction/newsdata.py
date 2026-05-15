from src.utils.config import NEWSDATA_API_KEY
from src.utils.logger import get_logger

logger = get_logger(__name__)


def fetch(query: str | None = None) -> list[dict]:
    raise NotImplementedError
