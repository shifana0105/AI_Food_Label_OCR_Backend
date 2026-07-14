"""Application-wide logging configuration.

Provides a ``get_logger`` factory returning loggers configured with a
single timestamped console handler at the level given by the
``LOG_LEVEL`` environment variable.
"""

import logging
import sys

from app.core.config import settings

_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_ROOT_LOGGER_NAME = "food_label_reader"

_configured = False


def _configure_root_logger() -> None:
    """Attach a console handler to the application root logger once."""
    global _configured
    if _configured:
        return

    level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    root = logging.getLogger(_ROOT_LOGGER_NAME)
    root.setLevel(level)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    handler.setFormatter(logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT))

    root.addHandler(handler)
    root.propagate = False
    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Return a namespaced logger for the given module name.

    Args:
        name: Usually ``__name__`` of the calling module.

    Returns:
        A logger writing timestamped messages to the console.
    """
    _configure_root_logger()
    return logging.getLogger(f"{_ROOT_LOGGER_NAME}.{name}")
