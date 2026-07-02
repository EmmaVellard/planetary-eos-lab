#!/usr/bin/env python3
"""CLI entry point for run_perplex."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Add repo root to path for imports
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from planetary_eos_lab.cli.common import create_base_parser, handle_cli_error
import run_perplex


def main(argv: list[str] | None = None) -> int:
    """Run Perple_X pipeline with improved CLI.

    Args:
        argv: Command-line arguments (default: sys.argv[1:])

    Returns:
        Exit code
    """
    parser = create_base_parser(
        prog="planetary-eos-run",
        description="Run Perple_X BUILD/VERTEX/WERAMI pipeline",
    )
    parser.add_argument(
        "--project",
        help="Run specific project only (default: all projects)",
    )
    parser.add_argument(
        "--skip-validation",
        action="store_true",
        help="Skip output validation",
    )

    args = parser.parse_args(argv)

    try:
        original_args = ["--config", str(args.config or run_perplex.DEFAULT_CONFIG)]

        if args.project:
            original_args.extend(["--project", args.project])

        if args.database:
            original_args.extend(["--database", args.database])

        if args.perplex_dir:
            original_args.extend(["--perplex-dir", str(args.perplex_dir)])

        if args.skip_validation:
            original_args.append("--skip-validation")

        return run_perplex.main(original_args)

    except Exception as e:
        from planetary_eos_lab.core.logging_config import get_logger
        return handle_cli_error(get_logger(__name__), e)


if __name__ == "__main__":
    sys.exit(main())
