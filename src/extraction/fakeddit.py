from src.utils.logger import get_logger

logger = get_logger(__name__)


def fetch() -> list[dict]:
    raise NotImplementedError
