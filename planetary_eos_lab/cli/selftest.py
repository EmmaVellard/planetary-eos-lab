#!/usr/bin/env python3
"""Installation self-test: checks Python, Perple_X and one real BUILD/VERTEX/WERAMI run.

Prints one PASS/WARN/FAIL/SKIP line per check and exits non-zero on any FAIL.
"""
from __future__ import annotations

import argparse
import contextlib
import datetime
import io
import importlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import run_perplex  # noqa: E402
from planetary_eos_lab.core.config import DATABASES  # noqa: E402
from validate_tab import column_indices, read_tab, validate_project_output  # noqa: E402

REFERENCE_FILE = Path(__file__).resolve().parents[1] / "selftest_reference.json"
DEPENDENCIES = ("streamlit", "pandas", "plotly", "openpyxl", "numpy")
EXECUTABLES = ("build", "vertex", "werami")
DEFAULT_DATABASE = "stx21"
COMPOSITION_ID = "moon_near_maria_surface_proxy"
COMPOSITION_FILE = REPO_ROOT / "compositions" / f"{COMPOSITION_ID}.json"
SELFTEST_OPTIONS = run_perplex.PerplexOptions(
    sample_on_grid=True, x_nodes=(15, 15), y_nodes=(15, 15), grid_levels=(1, 1)
)
COMPARED_PROPERTIES = ("rho_kgm3", "vp_kms", "vs_kms")
TOLERANCE_REL = 0.01


class Report:
    def __init__(self) -> None:
        self.failed = False

    def line(self, status: str, name: str, detail: str = "") -> None:
        self.failed |= status == "FAIL"
        print(f"{status:<4}  {name}" + (f": {detail}" if detail else ""), flush=True)


def default_perplex_dir() -> Path | None:
    if os.environ.get("PERPLEX_DIR"):
        return Path(os.environ["PERPLEX_DIR"]).expanduser()
    config = REPO_ROOT / "configs" / "models.json"
    try:
        value = json.loads(config.read_text(encoding="utf-8")).get("perplex_dir")
    except (OSError, json.JSONDecodeError):
        return None
    return run_perplex.resolve_path(value, REPO_ROOT) if value else None


def check_python(report: Report) -> None:
    version = ".".join(map(str, sys.version_info[:3]))
    report.line("PASS" if sys.version_info >= (3, 10) else "FAIL", "python version", f"{version} (need >= 3.10)")
    for name in DEPENDENCIES:
        try:
            module = importlib.import_module(name)
        except Exception as exc:  # any import-time failure means the dependency is unusable
            report.line("FAIL", f"import {name}", f"{type(exc).__name__}: {exc}")
        else:
            report.line("PASS", f"import {name}", getattr(module, "__version__", "?"))


def perplex_version(build: Path) -> str | None:
    """Return the release string BUILD prints when started with empty stdin."""
    with tempfile.TemporaryDirectory() as cwd:
        try:
            result = subprocess.run(
                run_perplex.executable_command(build), input="", text=True,
                capture_output=True, cwd=cwd, timeout=60,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
    match = re.search(r"Perple_X release\s+(\S+)", result.stdout + result.stderr)
    return match.group(1) if match else None


def check_perplex(report: Report, perplex_dir: Path | None) -> str | None:
    """Check the install; return the Perple_X version (or "unknown") if executables are usable, else None."""
    if perplex_dir is None:
        report.line("FAIL", "Perple_X directory", "not set; pass --perplex-dir, set PERPLEX_DIR or perplex_dir in configs/models.json")
        return None
    if not perplex_dir.is_dir():
        report.line("FAIL", "Perple_X directory", f"{perplex_dir} does not exist")
        return None
    report.line("PASS", "Perple_X directory", str(perplex_dir))

    usable = True
    for name in EXECUTABLES:
        path = run_perplex.executable_path(perplex_dir, name)
        try:
            run_perplex.ensure_executable(path, name)
        except (FileNotFoundError, PermissionError) as exc:
            report.line("FAIL", f"executable {name}", str(exc))
            usable = False
        else:
            report.line("PASS", f"executable {name}", str(path))
    if not usable:
        return None

    version = perplex_version(run_perplex.executable_path(perplex_dir, "build"))
    if version:
        report.line("PASS", "Perple_X version", version)
    else:
        report.line("WARN", "Perple_X version", "BUILD did not print 'Perple_X release ...'")
    return version or "unknown"


def stx24_predates_correction(path: Path) -> bool:
    """Perple_X data files start with a version line ("730 DO NOT DELETE THIS LINE"); stx24 was corrected in 7.2.13."""
    first = path.read_text(errors="replace").split("\n", 1)[0].split()
    return not first or not first[0].isdigit() or int(first[0]) < 720


def check_databases(report: Report, perplex_dir: Path) -> bool:
    """Check data files of every built-in database; return True if the default (stx21) is complete."""
    default_ok = True
    for name, db in DATABASES.items():
        missing = [f for f in (db.database_file, db.solution_model_file) if not (perplex_dir / "datafiles" / f).is_file()]
        if not missing and name == "stx24" and stx24_predates_correction(perplex_dir / "datafiles" / db.database_file):
            report.line("WARN", f"database {name}", "stx24ver.dat predates the stx24 correction of Perple_X 7.2.13 "
                        "(October 2026): update Perple_X before using stx24")
        elif not missing:
            report.line("PASS", f"database {name}", f"{db.database_file}, {db.solution_model_file}")
        elif name == DEFAULT_DATABASE:
            report.line("FAIL", f"database {name}", f"missing in datafiles/: {', '.join(missing)} (default database)")
            default_ok = False
        else:
            report.line("WARN", f"database {name}", f"missing in datafiles/: {', '.join(missing)} (only needed for {name} models)")
    return default_ok


def run_pipeline(report: Report, perplex_dir: Path, run_dir: Path) -> Path | None:
    """Run BUILD/VERTEX/WERAMI on the self-test model and validate it; return the PlanetProfile table."""
    output_dir = run_dir / "output"
    model = run_perplex.ModelConfig(
        project=COMPOSITION_ID,
        composition_file=COMPOSITION_FILE,
        build_input_file=run_perplex.default_build_template_for_database(DEFAULT_DATABASE),
        output_dir=output_dir,
        work_dir=output_dir / "work",
        database=DEFAULT_DATABASE,
        perplex_options=SELFTEST_OPTIONS,
    )
    started = time.monotonic()
    try:
        with contextlib.redirect_stdout(io.StringIO()):  # keep the pipeline's progress prints out of the report
            model.work_dir.mkdir(parents=True, exist_ok=True)
            run_perplex.validate_thermodynamic_setup(perplex_dir, model)
            run_perplex.write_options(model.work_dir, model.perplex_options)
            run_perplex.run_build(perplex_dir, model)
            run_perplex.require_dat_file(model.work_dir, model.project)
            run_perplex.run_vertex(perplex_dir, model)
            tab_path = run_perplex.run_werami(perplex_dir, model)
    except Exception as exc:
        report.line("FAIL", "BUILD/VERTEX/WERAMI run", f"{type(exc).__name__}: {exc}")
        return None
    report.line("PASS", "BUILD/VERTEX/WERAMI run", f"{COMPOSITION_ID}, {DEFAULT_DATABASE}, {time.monotonic() - started:.1f} s")

    result = validate_project_output(model.project, output_dir, tab_path=tab_path)
    if result.passed:
        report.line("PASS", "output validation", f"{len(read_tab(tab_path).rows)} rows")
    else:
        report.line("FAIL", "output validation", "; ".join(result.issues))
        return None
    return tab_path


def node_values(tab_path: Path) -> list[dict[str, float]]:
    tab = read_tab(tab_path)
    idx = column_indices(tab.headers)
    keys = ("p_bar", "t_k") + COMPARED_PROPERTIES
    return [{key: row[idx[key]] for key in keys} for row in tab.rows]


def pick_reference_nodes(rows: list[dict[str, float]]) -> list[dict[str, float]]:
    """First, middle and last row with finite values: low, mid and high corner of the grid."""
    finite = [row for row in rows if all(math.isfinite(row[k]) for k in COMPARED_PROPERTIES)]
    if len(finite) < 3:
        raise ValueError("fewer than 3 table rows with finite rho/Vp/Vs")
    return [finite[0], finite[len(finite) // 2], finite[-1]]


def compare_reference(report: Report, rows: list[dict[str, float]], reference: dict) -> None:
    for node in reference["nodes"]:
        label = f"reference node P={node['p_bar']:g} bar T={node['t_k']:g} K"
        match = next(
            (r for r in rows if math.isclose(r["p_bar"], node["p_bar"], rel_tol=1e-6)
             and math.isclose(r["t_k"], node["t_k"], rel_tol=1e-6)),
            None,
        )
        if match is None:
            report.line("FAIL", label, "node not in table (grid differs from reference)")
            continue
        errors = {k: abs(match[k] - node[k]) / abs(node[k]) for k in COMPARED_PROPERTIES}
        detail = ", ".join(f"{k}={match[k]:.6g} (ref {node[k]:.6g}, {errors[k]:.2%})" for k in COMPARED_PROPERTIES)
        tolerance = reference.get("tolerance_rel", TOLERANCE_REL)
        report.line("PASS" if max(errors.values()) <= tolerance else "FAIL", label, detail)


def write_reference(path: Path, rows: list[dict[str, float]], version: str) -> None:
    options = SELFTEST_OPTIONS
    data = {
        "_purpose": "Reference values for planetary-eos-selftest; regenerate with --write-reference, never edit by hand.",
        "perplex_version": version,
        "database": DEFAULT_DATABASE,
        "composition_id": COMPOSITION_ID,
        "perplex_options": {
            "sample_on_grid": options.sample_on_grid,
            "x_nodes": list(options.x_nodes),
            "y_nodes": list(options.y_nodes),
            "grid_levels": list(options.grid_levels),
        },
        "generated": datetime.date.today().isoformat(),
        "tolerance_rel": TOLERANCE_REL,
        "units": {"p_bar": "bar", "t_k": "K", "rho_kgm3": "kg/m3", "vp_kms": "km/s", "vs_kms": "km/s"},
        "nodes": pick_reference_nodes(rows),
    }
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="planetary-eos-selftest",
        description="Check that Python, Perple_X and the BUILD/VERTEX/WERAMI pipeline work on this machine.",
    )
    parser.add_argument("--perplex-dir", type=Path, help="Perple_X install (default: $PERPLEX_DIR, else perplex_dir in configs/models.json)")
    parser.add_argument("--reference", type=Path, default=REFERENCE_FILE, help=argparse.SUPPRESS)
    parser.add_argument("--write-reference", action="store_true", help="regenerate the reference values from this run")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    perplex_dir = args.perplex_dir.expanduser() if args.perplex_dir else default_perplex_dir()
    report = Report()

    check_python(report)
    version = check_perplex(report, perplex_dir)
    if version is None or not check_databases(report, perplex_dir):
        report.line("SKIP", "BUILD/VERTEX/WERAMI run", "Perple_X install incomplete")
        return 1

    run_dir = Path(tempfile.mkdtemp(prefix="planetary_eos_selftest_"))
    tab_path = run_pipeline(report, perplex_dir, run_dir)
    if tab_path is None:
        print(f"Logs kept in {run_dir / 'output'}")
        return 1
    rows = node_values(tab_path)
    shutil.rmtree(run_dir, ignore_errors=True)

    if args.write_reference:
        write_reference(args.reference, rows, version)
        report.line("PASS", "reference written", str(args.reference))
    elif args.reference.is_file():
        compare_reference(report, rows, json.loads(args.reference.read_text(encoding="utf-8")))
    else:
        report.line("FAIL", "reference values", f"{args.reference} missing; run with --write-reference")

    print("SELFTEST " + ("FAILED" if report.failed else "PASSED"))
    return 1 if report.failed else 0


if __name__ == "__main__":
    sys.exit(main())
