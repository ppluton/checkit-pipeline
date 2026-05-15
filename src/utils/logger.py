"""Centralised logger factory.

Why centralised:
    Every module emits logs in the same format so that operator-facing
    output (CLI runs, Airflow task logs, log aggregation) is consistent
    and grep-friendly.

Design choices:
    * One handler per logger, attached only on the first call. Subsequent
      ``get_logger(name)`` calls return the same logger to avoid the
      classic duplicated-log-line bug.
    * ``propagate = False`` so records do not bubble up to the root
      logger (Airflow attaches its own handlers there and would
      double-print everything).
    * Output goes to stdout, which is what Airflow captures by default.
"""

import logging
import sys


def get_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """Return a stdout logger with the project's standard format.

    Idempotent: calling it twice with the same ``name`` does not stack
    handlers, so loops or repeated imports cannot produce duplicate
    log lines.
    """
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(level)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s | %(name)s | %(levelname)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    logger.addHandler(handler)
    logger.propagate = False
    return logger
