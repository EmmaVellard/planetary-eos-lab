from __future__ import annotations

import argparse

import export_planetprofile
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
        "--database",
        help="Thermodynamic database to use instead of the config value (built-in or declared in custom_databases).",
    )
    parser.add_argument(
        "--perplex-dir",
        help="Path to a Perple_X installation, overriding configs/models.json.",
    )
    parser.add_argument(
        "--skip-validation",
        action="store_true",
        help="Run BUILD/VERTEX/WERAMI but skip output validation.",
    )
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
    parser.add_argument(
        "--export-planetprofile",
        action="store_true",
        help="Copy validated native .tab files to a PlanetProfile-format export directory.",
    )
    parser.add_argument(
        "--planetprofile-export-dir",
        default=str(export_planetprofile.DEFAULT_EXPORT_DIR),
        help="Export directory used with --export-planetprofile.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if not args.skip_compositions:
        print("Generating compositions")
        composition_args = ["--config", args.config]
        if args.project:
            composition_args.extend(["--project", args.project])
        if args.database:
            composition_args.extend(["--database", args.database])
        make_compositions.main(composition_args)

    print("Running Perple_X pipeline")
    run_args = ["--config", args.config]
    if args.project:
        run_args.extend(["--project", args.project])
    if args.database:
        run_args.extend(["--database", args.database])
    if args.perplex_dir:
        run_args.extend(["--perplex-dir", args.perplex_dir])
    if args.skip_validation:
        run_args.append("--skip-validation")

    result = run_perplex.main(run_args)
    if result != 0:
        return result

    if not args.skip_plots:
        print("Generating comparison plots")
        plot_args = ["--config", args.config]
        if args.project:
            plot_args.extend(["--project", args.project])
        result = plot_comparisons.main(plot_args)
        if result != 0:
            return result

    if args.export_planetprofile:
        print("Exporting PlanetProfile tables")
        export_args = [
            "--config",
            args.config,
            "--planetprofile-export-dir",
            args.planetprofile_export_dir,
        ]
        if args.project:
            export_args.extend(["--project", args.project])
        if args.database:
            export_args.extend(["--database", args.database])
        if args.perplex_dir:
            export_args.extend(["--perplex-dir", args.perplex_dir])
        return export_planetprofile.main(export_args)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
