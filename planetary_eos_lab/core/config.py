"""Centralized configuration management for Planetary EOS Lab."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from planetary_eos_lab.core.constants import (
    DEFAULT_DATABASE_FILE,
    DEFAULT_SOLUTION_MODEL_FILE,
    DEFAULT_EXCLUDED_PHASES,
    DEFAULT_SOLUTION_MODELS,
    DEFAULT_PT_RANGE,
)
from planetary_eos_lab.core.exceptions import ConfigurationError


@dataclass
class ThermodynamicDatabase:
    """Configuration for a thermodynamic database."""

    name: str
    database_file: str
    solution_model_file: str
    excluded_phases: tuple[str, ...] = field(default_factory=tuple)
    solution_models: tuple[str, ...] = field(default_factory=tuple)
    pt_range: dict[str, dict[str, float]] = field(default_factory=dict)
    description: str = ""

    def __post_init__(self):
        if not self.pt_range:
            self.pt_range = DEFAULT_PT_RANGE.copy()


# Predefined database configurations
DATABASES = {
    "stx21": ThermodynamicDatabase(
        name="stx21",
        database_file=DEFAULT_DATABASE_FILE,
        solution_model_file=DEFAULT_SOLUTION_MODEL_FILE,
        excluded_phases=DEFAULT_EXCLUDED_PHASES,
        solution_models=DEFAULT_SOLUTION_MODELS,
        pt_range=DEFAULT_PT_RANGE.copy(),
        description="Stixrude & Lithgow-Bertelloni 2021 - default for silicate mantles",
    ),
    "hp633": ThermodynamicDatabase(
        name="hp633",
        database_file="hp633ver.dat",
        solution_model_file="solution_model.dat",
        excluded_phases=("q", "crst", "trd"),
        solution_models=("O(HP)", "Opx(HP)", "Cpx(HP)", "Gt(HP)", "Sp(HP)", "Pl(I1,HP)", "Ilm(WPH)"),
        pt_range=DEFAULT_PT_RANGE.copy(),
        description=(
            "Holland & Powell 2011 (v6.33) - includes TiO2 and K2O components; "
            "P2O5 remains source-only unless a custom P-bearing database is supplied"
        ),
    ),
}


@dataclass
class Config:
    """Central configuration for Planetary EOS Lab.

    Loads settings from:
    1. Default values
    2. Config file (configs/models.json)
    3. Environment variables (PERPLEX_DIR, PERPLEX_DATABASE, etc.)
    4. Command-line arguments (if provided)
    """

    # Perple_X installation
    perplex_dir: Path
    database: str = "stx21"

    # Build template
    build_template_file: Optional[Path] = None

    # Logging
    log_level: str = "INFO"
    log_file: Optional[Path] = None
    verbose: bool = False

    # Output
    output_base_dir: Optional[Path] = None

    # Models (loaded from config file)
    models: list[dict[str, Any]] = field(default_factory=list)

    # Raw config data
    _raw_config: dict[str, Any] = field(default_factory=dict, repr=False)

    def __post_init__(self):
        """Validate configuration after initialization."""
        # Convert strings to Path objects
        if isinstance(self.perplex_dir, str):
            self.perplex_dir = Path(self.perplex_dir).expanduser()

        if self.build_template_file and isinstance(self.build_template_file, str):
            self.build_template_file = Path(self.build_template_file).expanduser()

        if self.log_file and isinstance(self.log_file, str):
            self.log_file = Path(self.log_file).expanduser()

        if self.output_base_dir and isinstance(self.output_base_dir, str):
            self.output_base_dir = Path(self.output_base_dir).expanduser()

        # Validate database selection
        if self.database not in DATABASES:
            available = ", ".join(DATABASES.keys())
            raise ConfigurationError(
                f"Unknown database '{self.database}'. Available: {available}"
            )

    def get_database_config(self) -> ThermodynamicDatabase:
        """Get the thermodynamic database configuration.

        Returns:
            ThermodynamicDatabase configuration
        """
        return DATABASES[self.database]

    @classmethod
    def from_file(cls, config_path: Path) -> Config:
        """Load configuration from JSON file.

        Args:
            config_path: Path to config JSON file

        Returns:
            Config instance

        Raises:
            ConfigurationError: If config file is invalid
        """
        if not config_path.exists():
            raise ConfigurationError(f"Config file not found: {config_path}")

        try:
            with open(config_path) as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise ConfigurationError(f"Invalid JSON in {config_path}: {e}")

        # Extract known fields
        perplex_dir = data.get("perplex_dir")
        if not perplex_dir:
            raise ConfigurationError("Missing required field: perplex_dir")

        return cls(
            perplex_dir=Path(perplex_dir).expanduser(),
            database=data.get("database", "stx21"),
            build_template_file=Path(data["build_template_file"]).expanduser()
            if "build_template_file" in data
            else None,
            log_level=data.get("log_level", "INFO"),
            log_file=Path(data["log_file"]).expanduser() if "log_file" in data else None,
            verbose=data.get("verbose_logging", False),
            output_base_dir=Path(data["output_base_dir"]).expanduser()
            if "output_base_dir" in data
            else None,
            models=data.get("models", []),
            _raw_config=data,
        )

    @classmethod
    def from_env(cls, base_config: Optional[Config] = None) -> Config:
        """Load configuration from environment variables.

        Args:
            base_config: Optional base config to override

        Returns:
            Config instance with environment overrides
        """
        kwargs = {}

        # Override from environment
        if perplex_dir := os.getenv("PERPLEX_DIR"):
            kwargs["perplex_dir"] = Path(perplex_dir).expanduser()

        if database := os.getenv("PERPLEX_DATABASE"):
            kwargs["database"] = database

        if log_level := os.getenv("PERPLEX_LOG_LEVEL"):
            kwargs["log_level"] = log_level

        if log_file := os.getenv("PERPLEX_LOG_FILE"):
            kwargs["log_file"] = Path(log_file).expanduser()

        if verbose := os.getenv("PERPLEX_VERBOSE"):
            kwargs["verbose"] = verbose.lower() in ("1", "true", "yes")

        # Merge with base config if provided
        if base_config:
            for key, value in kwargs.items():
                setattr(base_config, key, value)
            return base_config

        # Create new config (requires perplex_dir)
        if "perplex_dir" not in kwargs:
            raise ConfigurationError(
                "PERPLEX_DIR environment variable required when not using config file"
            )

        return cls(**kwargs)

    def validate_perplex_installation(self) -> bool:
        """Validate that Perple_X is properly installed.

        Returns:
            True if valid, raises ConfigurationError otherwise
        """
        if not self.perplex_dir.exists():
            raise ConfigurationError(f"Perple_X directory not found: {self.perplex_dir}")

        # Check for executables
        executables = ["build", "vertex", "werami"]
        bin_dir = self.perplex_dir / "bin"

        # Try both bin/ subdirectory and root
        for exe_name in executables:
            found = False
            for location in [
                bin_dir / exe_name,
                bin_dir / f"{exe_name}.exe",
                self.perplex_dir / exe_name,
                self.perplex_dir / f"{exe_name}.exe",
            ]:
                if location.exists():
                    found = True
                    break

            if not found:
                raise ConfigurationError(
                    f"Perple_X executable not found: {exe_name} "
                    f"(checked {bin_dir} and {self.perplex_dir})"
                )

        # Check for datafiles
        datafiles_dir = self.perplex_dir / "datafiles"
        if not datafiles_dir.exists():
            raise ConfigurationError(
                f"Perple_X datafiles directory not found: {datafiles_dir}"
            )

        # Check for database file
        db_config = self.get_database_config()
        db_file = datafiles_dir / db_config.database_file
        if not db_file.exists():
            raise ConfigurationError(
                f"Database file not found: {db_file} "
                f"(database: {self.database})"
            )

        solution_file = datafiles_dir / db_config.solution_model_file
        if not solution_file.exists():
            raise ConfigurationError(
                f"Solution model file not found: {solution_file} "
                f"(database: {self.database})"
            )

        return True

    def to_dict(self) -> dict[str, Any]:
        """Convert config to dictionary for serialization.

        Returns:
            Dictionary representation
        """
        result = self._raw_config.copy()
        result.update(
            {
                "perplex_dir": str(self.perplex_dir),
                "database": self.database,
                "log_level": self.log_level,
                "verbose_logging": self.verbose,
            }
        )

        if self.build_template_file:
            result["build_template_file"] = str(self.build_template_file)

        if self.log_file:
            result["log_file"] = str(self.log_file)

        if self.output_base_dir:
            result["output_base_dir"] = str(self.output_base_dir)

        return result

    def save(self, config_path: Path) -> None:
        """Save configuration to JSON file.

        Args:
            config_path: Path to save config file
        """
        config_path.parent.mkdir(parents=True, exist_ok=True)

        with open(config_path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)
            f.write("\n")


def get_default_config_path() -> Path:
    """Get the default config file path.

    Returns:
        Path to configs/models.json relative to repository root
    """
    # Try to find repo root by looking for pyproject.toml
    current = Path(__file__).resolve()

    for parent in current.parents:
        if (parent / "pyproject.toml").exists():
            return parent / "configs" / "models.json"

    # Fallback to relative path
    return Path("configs/models.json")


def load_config(
    config_path: Optional[Path] = None,
    use_env: bool = True,
) -> Config:
    """Load configuration from file and environment.

    Args:
        config_path: Path to config file (uses default if None)
        use_env: Whether to apply environment variable overrides

    Returns:
        Config instance

    Raises:
        ConfigurationError: If configuration is invalid
    """
    if config_path is None:
        config_path = get_default_config_path()

    # Load from file
    config = Config.from_file(config_path)

    # Apply environment overrides
    if use_env:
        config = Config.from_env(base_config=config)

    return config
