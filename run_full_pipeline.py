from __future__ import annotations

import argparse

import make_compositions
import plot_comparisons
import run_perplex


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate compositions, run Perple_X, and validate WERAMI outputs."
    )
    parser.add_argument("--config", default=str(run_perplex.DEFAULT_CONFIG), help="Path to configs/models.json.")
    parser.add_argument("--project", help="Run only one project from the config.")
    parser.add_argument(
        "--skip-compositions",
        action="store_true",
        help="Skip regenerating composition files before running Perple_X.",
    )
    parser.add_argument(
        "--skip-plots",
        action="store_true",
        help="Skip generating comparison SVGs after Perple_X validation passes.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if not args.skip_compositions:
        print("Generating compositions")
        make_compositions.main()

    print("Running Perple_X pipeline")
    run_args = ["--config", args.config]
    if args.project:
        run_args.extend(["--project", args.project])

    result = run_perplex.main(run_args)
    if result != 0 or args.skip_plots:
        return result

    print("Generating comparison plots")
    plot_args = ["--config", args.config]
    if args.project:
        plot_args.extend(["--project", args.project])
    return plot_comparisons.main(plot_args)


if __name__ == "__main__":
    raise SystemExit(main())
