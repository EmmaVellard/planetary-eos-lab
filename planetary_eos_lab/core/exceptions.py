"""Custom exceptions for Planetary EOS Lab."""
from __future__ import annotations


class PerplexWorkbenchError(Exception):
    """Base exception for all Planetary EOS Lab errors."""

    pass


class ConfigurationError(PerplexWorkbenchError):
    """Configuration file is invalid or missing required fields."""

    pass


class ValidationError(PerplexWorkbenchError):
    """Data validation failed."""

    pass


class PerplexExecutableError(PerplexWorkbenchError):
    """Perple_X executable not found or failed to run."""

    def __init__(self, executable: str, message: str):
        self.executable = executable
        super().__init__(f"{executable}: {message}")


class PerplexOutputError(PerplexWorkbenchError):
    """Perple_X output is invalid or missing."""

    pass


class CompositionError(PerplexWorkbenchError):
    """Composition data is invalid."""

    pass


class ExportError(PerplexWorkbenchError):
    """Failed to export PlanetProfile tables."""

    pass
