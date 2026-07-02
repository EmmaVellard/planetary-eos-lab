"""Common CLI utilities and argument parsing."""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Optional

from planetary_eos_lab.core.config import load_config, get_default_config_path
from planetary_eos_lab.core.logging_config import setup_logging, get_logger
from planetary_eos_lab.core.exceptions import ConfigurationError


__version__ = "1.0"


def add_common_arguments(parser: argparse.ArgumentParser) -> None:
    """Add common arguments to a parser.

    Args:
        parser: Argument parser to add arguments to
    """
    parser.add_argument(
        "--config",
        type=Path,
        help=f"Path to config file (default: {get_default_config_path()})",
    )
    parser.add_argument(
        "--database",
        choices=["stx21", "hp633"],
        help="Thermodynamic database to use (default: from config or stx21)",
    )
    parser.add_argument(
        "--perplex-dir",
        type=Path,
        help="Path to Perple_X installation (overrides config)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose output",
    )
    parser.add_argument(
        "--log-file",
        type=Path,
        help="Write logs to file",
    )
    parser.add_argument(
        "--log-level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level (default: INFO)",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )


def setup_cli_environment(args: argparse.Namespace) -> tuple[object, logging.Logger]:
    """Setup configuration and logging from CLI arguments.

    Args:
        args: Parsed command-line arguments

    Returns:
        Tuple of (config, logger)
    """
    # Setup logging first
    log_level = getattr(logging, args.log_level)
    setup_logging(
        level=log_level,
        log_file=args.log_file,
        verbose=args.verbose,
    )
    logger = get_logger(__name__)

    # Load configuration
    try:
        config = load_config(config_path=args.config)

        # Apply CLI overrides
        if hasattr(args, "database") and args.database:
            config.database = args.database

        if hasattr(args, "perplex_dir") and args.perplex_dir:
            config.perplex_dir = args.perplex_dir

        if args.verbose:
            config.verbose = True

        # Validate Perple_X installation
        config.validate_perplex_installation()

        logger.info(f"Using Perple_X from: {config.perplex_dir}")
        logger.info(f"Using database: {config.database}")

        return config, logger

    except ConfigurationError as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)


def handle_cli_error(logger: logging.Logger, error: Exception, exit_code: int = 1) -> int:
    """Handle CLI errors with proper logging.

    Args:
        logger: Logger instance
        error: Exception that occurred
        exit_code: Exit code to return

    Returns:
        Exit code
    """
    if isinstance(error, KeyboardInterrupt):
        logger.info("Interrupted by user")
        return 130  # Standard SIGINT exit code

    logger.error(f"{type(error).__name__}: {error}")

    if logger.level == logging.DEBUG:
        logger.exception("Full traceback:")

    return exit_code


def create_base_parser(
    prog: str,
    description: str,
    add_common: bool = True,
) -> argparse.ArgumentParser:
    """Create a base argument parser with common options.

    Args:
        prog: Program name
        description: Program description
        add_common: Whether to add common arguments

    Returns:
        Configured ArgumentParser
    """
    parser = argparse.ArgumentParser(
        prog=prog,
        description=description,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    if add_common:
        add_common_arguments(parser)

    return parser
