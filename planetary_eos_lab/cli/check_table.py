#!/usr/bin/env python3
"""Inspect, domain-check and compare Perple_X .tab tables (P in bar, T in K)."""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path

import numpy as np

from planetary_eos_lab.analysis import compare_tables, domain_check, resolution_convergence, table_quality


def _jsonable(value):
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, np.ndarray)):
        return [_jsonable(item) for item in (value.tolist() if isinstance(value, np.ndarray) else value)]
    if isinstance(value, (float, np.floating)):
        return float(value) if math.isfinite(value) else None
    if isinstance(value, np.generic):
        return value.item()
    return value


def read_points_csv(path: Path) -> tuple[list[float], list[float]]:
    """Two columns P_bar, T_K; a non-numeric header row is skipped."""
    p, t = [], []
    with path.open(newline="") as handle:
        for line_number, row in enumerate(csv.reader(handle), start=1):
            if not row or not "".join(row).strip():
                continue
            try:
                p_value, t_value = float(row[0]), float(row[1])
            except (ValueError, IndexError):
                if line_number == 1:
                    continue
                raise ValueError(f"{path}:{line_number}: expected 'P_bar,T_K', got {row!r}")
            p.append(p_value)
            t.append(t_value)
    return p, t


def _fmt(value) -> str:
    return "-" if value is None else f"{value:.6g}"


def _stats_lines(properties: dict) -> list[str]:
    lines = [f"  {'property':<14s} {'n':>8s} {'mean|%|':>10s} {'rms%':>10s} {'max|%|':>10s}  at (P bar, T K)"]
    for name, stats in properties.items():
        if not stats["n_compared"]:
            lines.append(f"  {name:<14s} {0:>8d}  no comparable values")
            continue
        lines.append(
            f"  {name:<14s} {stats['n_compared']:>8d} {_fmt(stats['mean_abs_pct']):>10s} {_fmt(stats['rms_pct']):>10s}"
            f" {_fmt(stats['max_abs_pct']):>10s}  ({_fmt(stats['p_bar_at_max'])}, {_fmt(stats['t_k_at_max'])})"
        )
    return lines


def format_text(command: str, result: dict) -> str:
    if command == "quality":
        grid = result["grid"]
        lines = [f"TABLE: {result['path']}", f"SHA256: {result['sha256']}"]
        for axis, unit in (("p_bar", "bar"), ("t_k", "K")):
            a = grid[axis]
            lines.append(f"{axis}: {_fmt(a['min'])} .. {_fmt(a['max'])} {unit}, n={a['n']}, step={_fmt(a['step'])}")
        lines.append(f"nodes: {grid['n_nodes']} ({grid['n_missing_nodes']} missing)")
        lines.append(f"  {'column':<14s} {'n_nan':>7s} {'n_inf':>7s} {'n_nonpos':>8s} {'min':>12s} {'max':>12s}")
        for name, c in result["columns"].items():
            nonpos = "-" if c["n_non_positive"] is None else str(c["n_non_positive"])
            lines.append(
                f"  {name:<14s} {c['n_nan']:>7d} {c['n_inf']:>7d} {nonpos:>8s} {_fmt(c['min']):>12s} {_fmt(c['max']):>12s}"
            )
        return "\n".join(lines)
    if command == "domain":
        d = result["domain"]
        lines = [
            f"domain: P {_fmt(d['p_bar'][0])} .. {_fmt(d['p_bar'][1])} bar, T {_fmt(d['t_k'][0])} .. {_fmt(d['t_k'][1])} K",
            f"points: {result['n_points']}, outside: {result['n_outside']}",
        ]
        lines += [
            f"  OUTSIDE #{pt['index']}: P={_fmt(pt['p_bar'])} bar, T={_fmt(pt['t_k'])} K" for pt in result["outside_points"]
        ]
        return "\n".join(lines)
    if command == "compare":
        return "\n".join([f"common nodes: {result['n_common_nodes']}  (b - a) / a"] + _stats_lines(result["properties"]))
    return "\n".join(
        [
            f"fine nodes: {result['n_fine_nodes']}, inside coarse domain: {result['n_inside_coarse_domain']}"
            "  (fine - coarse) / coarse"
        ]
        + _stats_lines(result["properties"])
    )


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true", help="Print JSON instead of text.")
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    quality = sub.add_parser("quality", parents=[common], help="Grid extent and per-column NaN/Inf/non-positive counts.")
    quality.add_argument("tab", type=Path)

    domain = sub.add_parser("domain", parents=[common], help="Report requested (P, T) points outside the table domain.")
    domain.add_argument("tab", type=Path)
    domain.add_argument("--p-bar", type=float, nargs="+", help="Pressures in bar.")
    domain.add_argument("--t-k", type=float, nargs="+", help="Temperatures in K (same count as --p-bar).")
    domain.add_argument("--points", type=Path, help="CSV file with columns P_bar,T_K (optional header row).")

    compare = sub.add_parser("compare", parents=[common], help="(b - a) / a in percent at common nodes.")
    compare.add_argument("tab_a", type=Path)
    compare.add_argument("tab_b", type=Path)

    convergence = sub.add_parser("convergence", parents=[common], help="Fine table vs coarse table interpolated onto it.")
    convergence.add_argument("coarse", type=Path)
    convergence.add_argument("fine", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Exit 0 on success, 1 when domain points fall outside the table, 2 on input errors."""
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        if args.command == "quality":
            result = table_quality(args.tab)
        elif args.command == "domain":
            if args.points:
                p, t = read_points_csv(args.points)
            elif args.p_bar and args.t_k and len(args.p_bar) == len(args.t_k):
                p, t = args.p_bar, args.t_k
            else:
                raise ValueError("give --points CSV, or --p-bar and --t-k with the same number of values")
            result = domain_check(args.tab, p, t)
        elif args.command == "compare":
            result = compare_tables(args.tab_a, args.tab_b)
        else:
            result = resolution_convergence(args.coarse, args.fine)
    except (FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(_jsonable(result), indent=2) if args.json else format_text(args.command, result))
    return 1 if args.command == "domain" and result["n_outside"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
