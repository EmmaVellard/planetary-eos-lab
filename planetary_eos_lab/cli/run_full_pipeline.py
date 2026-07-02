#!/usr/bin/env python3
"""CLI entry point for run_full_pipeline."""
from __future__ import annotations

import sys
from pathlib import Path

# Add repo root to path for imports
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import run_full_pipeline


def main() -> int:
    """Run full Perple_X pipeline."""
    return run_full_pipeline.main(sys.argv[1:])


if __name__ == "__main__":
    sys.exit(main())
