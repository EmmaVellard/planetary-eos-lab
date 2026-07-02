"""Centralized logging configuration for Planetary EOS Lab."""
from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Optional


DEFAULT_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
SIMPLE_FORMAT = "%(levelname)s: %(message)s"


def setup_logging(
    level: int = logging.INFO,
    log_file: Optional[Path] = None,
    verbose: bool = False,
) -> logging.Logger:
    """Configure logging for the application.

    Args:
        level: Logging level (logging.INFO, logging.DEBUG, etc.)
        log_file: Optional file path to write logs to
        verbose: If True, use detailed format; otherwise use simple format

    Returns:
        Configured root logger
    """
    fmt = DEFAULT_FORMAT if verbose else SIMPLE_FORMAT

    # Configure root logger
    logging.basicConfig(
        level=level,
        format=fmt,
        handlers=[],
    )

    root_logger = logging.getLogger()
    root_logger.handlers.clear()

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(logging.Formatter(fmt))
    root_logger.addHandler(console_handler)

    # File handler (if specified)
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)  # Always log DEBUG to file
        file_handler.setFormatter(logging.Formatter(DEFAULT_FORMAT))
        root_logger.addHandler(file_handler)

    return root_logger


def get_logger(name: str) -> logging.Logger:
    """Get a logger for a specific module.

    Args:
        name: Module name (usually __name__)

    Returns:
        Logger instance
    """
    return logging.getLogger(name)
