#!/usr/bin/env python3
"""GUI entry point for Planetary EOS Lab."""
from __future__ import annotations

import argparse
import sys
import subprocess
from pathlib import Path

from planetary_eos_lab.cli.common import __version__


def main(argv: list[str] | None = None) -> int:
    """Launch the Streamlit GUI.

    Args:
        argv: Command-line arguments (default: sys.argv[1:])

    Returns:
        Exit code
    """
    parser = argparse.ArgumentParser(
        prog="perplex-gui",
        description="Launch Planetary EOS Lab GUI",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8501,
        help="Port to run server on (default: 8501)",
    )
    parser.add_argument(
        "--address",
        "--host",
        default="127.0.0.1",
        help="Host/interface to bind Streamlit to (default: 127.0.0.1)",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    args = parser.parse_args(argv)

    gui_script = Path(__file__).resolve().parents[1] / "gui" / "streamlit_app.py"

    if not gui_script.exists():
        print(f"Error: GUI script not found at {gui_script}", file=sys.stderr)
        return 1

    try:
        cmd = [
            "streamlit",
            "run",
            str(gui_script),
            "--server.address",
            str(args.address),
            "--server.port",
            str(args.port),
        ]
        subprocess.run(cmd, check=True)
        return 0
    except subprocess.CalledProcessError as e:
        return e.returncode
    except FileNotFoundError:
        print("Error: streamlit not found. Install with: pip install streamlit", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nShutting down GUI server...")
        return 0


if __name__ == "__main__":
    sys.exit(main())
