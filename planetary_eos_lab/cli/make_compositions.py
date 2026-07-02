#!/usr/bin/env python3
"""CLI entry point for make_compositions."""
from __future__ import annotations

import sys
from pathlib import Path

# Add repo root to path for imports
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import make_compositions


def main() -> int:
    """Generate composition files."""
    return make_compositions.main(sys.argv[1:])


if __name__ == "__main__":
    sys.exit(main())
