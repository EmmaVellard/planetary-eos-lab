"""Integration utilities for adding logging to existing scripts."""
from __future__ import annotations

import functools
import logging
import sys
from typing import Any, Callable, TypeVar, cast

from planetary_eos_lab.core.logging_config import get_logger


T = TypeVar("T", bound=Callable[..., Any])


def with_logging(func: T) -> T:
    """Decorator to add logging to existing functions.

    Args:
        func: Function to wrap

    Returns:
        Wrapped function with logging
    """

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        logger = get_logger(func.__module__)
        logger.debug(f"Calling {func.__name__}")

        try:
            result = func(*args, **kwargs)
            logger.debug(f"{func.__name__} completed successfully")
            return result
        except Exception as e:
            logger.error(f"{func.__name__} failed: {e}")
            raise

    return cast(T, wrapper)


class LoggerWriter:
    """File-like object that redirects writes to logger.

    Useful for capturing print() statements.
    """

    def __init__(self, logger: logging.Logger, level: int = logging.INFO):
        self.logger = logger
        self.level = level
        self.buffer = ""

    def write(self, message: str) -> int:
        """Write message to logger.

        Args:
            message: Message to write

        Returns:
            Number of characters written
        """
        if message != "\n":
            self.buffer += message
            if "\n" in self.buffer:
                lines = self.buffer.split("\n")
                for line in lines[:-1]:
                    if line.strip():
                        self.logger.log(self.level, line.strip())
                self.buffer = lines[-1]

        return len(message)

    def flush(self) -> None:
        """Flush any remaining buffer."""
        if self.buffer.strip():
            self.logger.log(self.level, self.buffer.strip())
            self.buffer = ""


def redirect_print_to_log(logger: logging.Logger, level: int = logging.INFO) -> tuple[object, object]:
    """Redirect stdout/stderr to logger.

    Args:
        logger: Logger to redirect to
        level: Log level for messages

    Returns:
        Tuple of (original_stdout, original_stderr)
    """
    original_stdout = sys.stdout
    original_stderr = sys.stderr

    sys.stdout = LoggerWriter(logger, level)  # type: ignore
    sys.stderr = LoggerWriter(logger, logging.ERROR)  # type: ignore

    return original_stdout, original_stderr


def restore_print(original_stdout: object, original_stderr: object) -> None:
    """Restore original stdout/stderr.

    Args:
        original_stdout: Original stdout object
        original_stderr: Original stderr object
    """
    sys.stdout = original_stdout  # type: ignore
    sys.stderr = original_stderr  # type: ignore


def log_subprocess_output(logger: logging.Logger, stdout: str, stderr: str, level: int = logging.DEBUG) -> None:
    """Log subprocess output.

    Args:
        logger: Logger instance
        stdout: Subprocess stdout
        stderr: Subprocess stderr
        level: Log level for stdout
    """
    if stdout.strip():
        for line in stdout.strip().split("\n"):
            logger.log(level, f"stdout: {line}")

    if stderr.strip():
        for line in stderr.strip().split("\n"):
            logger.error(f"stderr: {line}")


def progress_logger(logger: logging.Logger, total: int, desc: str = "") -> Callable[[int], None]:
    """Create a progress callback that logs.

    Args:
        logger: Logger instance
        total: Total number of items
        desc: Description of task

    Returns:
        Callback function(current_item)
    """

    def callback(current: int) -> None:
        percent = (current / total) * 100 if total > 0 else 0
        logger.info(f"{desc} {current}/{total} ({percent:.1f}%)")

    return callback
