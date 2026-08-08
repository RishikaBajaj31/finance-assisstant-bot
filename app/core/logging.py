"""Structured logging module."""

import logging
import sys
from app.config import settings


def setup_logging() -> logging.Logger:
    """Configure structured console logging for the application."""
    logger = logging.getLogger("financial_assistant")
    logger.setLevel(settings.LOG_LEVEL.upper())

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            "[%(asctime)s] [%(levelname)s] [%(name)s:%(lineno)d]: %(message)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger


logger = setup_logging()
