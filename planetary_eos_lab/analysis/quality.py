"""Grid loading, numerical quality and P-T domain checks for Perple_X tables.

P and T axes are identified from the header labels (P(bar), T(K)), never from
column position or array shape. Units are those of the tables: P in bar, T in K.
"""
from __future__ import annotations

import hashlib
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np

# validate_tab lives at the repository root, as for the other CLI wrappers.
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from validate_tab import REQUIRED_COLUMNS, canonical_column, column_indices, parse_numeric_row, read_tab  # noqa: E402

AXES = ("p_bar", "t_k")
# Required properties that must be strictly positive at a valid node; alpha only needs to be finite.
POSITIVE_PROPERTIES = tuple(name for name in REQUIRED_COLUMNS if name not in AXES and name != "alpha_pk")


@dataclass(frozen=True)
class Table:
    """A rectangular P-T grid. values[i, j, k] is column names[k] at (pressure_bar[i], temperature_k[j])."""

    path: Path | None
    names: tuple[str, ...]  # canonical name for known properties, raw header label otherwise
    pressure_bar: np.ndarray
    temperature_k: np.ndarray
    values: np.ndarray
    n_missing_nodes: int = 0

    def column(self, name: str) -> np.ndarray:
        return self.values[:, :, self.names.index(name)]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_rows(path: Path) -> tuple[list[str], list[list[float]]]:
    try:
        tab = read_tab(path)
        return tab.headers, tab.rows
    except ValueError:
        pass
    # Phase-mode tables have only P and T as known columns, which read_tab rejects.
    lines = path.read_text(errors="replace").splitlines()
    for index, line in enumerate(lines):
        headers = line.split()
        if len(headers) >= 3 and {"p_bar", "t_k"} <= set(column_indices(headers)):
            rows = [parse_numeric_row(other.split(), len(headers)) for other in lines[index + 1 :]]
            rows = [row for row in rows if row is not None]
            if rows:
                return headers, rows
    raise ValueError(f"{path}: no header with P(bar) and T(K) columns followed by numeric rows.")


def load_table(path: str | Path) -> Table:
    path = Path(path)
    headers, rows = _read_rows(path)
    indices = column_indices(headers)
    if "p_bar" not in indices or "t_k" not in indices:
        raise ValueError(f"{path}: P(bar) and T(K) columns are required.")
    data = np.asarray(rows, dtype=float)
    p_col, t_col = data[:, indices["p_bar"]], data[:, indices["t_k"]]
    keep = [k for k in range(len(headers)) if k not in (indices["p_bar"], indices["t_k"])]
    names = tuple(canonical_column(headers[k]) or headers[k] for k in keep)

    pressures, temperatures = np.unique(p_col), np.unique(t_col)
    values = np.full((pressures.size, temperatures.size, len(keep)), np.nan)
    i, j = np.searchsorted(pressures, p_col), np.searchsorted(temperatures, t_col)
    values[i, j] = data[:, keep]
    n_nodes = len(set(zip(i.tolist(), j.tolist())))
    return Table(path, names, pressures, temperatures, values, pressures.size * temperatures.size - n_nodes)


def as_table(table: Table | str | Path) -> Table:
    return table if isinstance(table, Table) else load_table(table)


def _axis_summary(axis: np.ndarray) -> dict:
    return {
        "min": float(axis[0]),
        "max": float(axis[-1]),
        "n": int(axis.size),
        "step": float((axis[-1] - axis[0]) / (axis.size - 1)) if axis.size > 1 else 0.0,
    }


def table_quality(path: str | Path) -> dict:
    """Grid extent and per-column NaN/Inf/non-positive counts and finite range."""
    table = load_table(path)
    columns = {}
    for k, name in enumerate(table.names):
        arr = table.values[:, :, k]
        finite = arr[np.isfinite(arr)]
        # Phase modes and alpha may legitimately be zero or negative.
        check_sign = name in POSITIVE_PROPERTIES
        columns[name] = {
            "n": int(arr.size),
            "n_nan": int(np.isnan(arr).sum()),
            "n_inf": int(np.isinf(arr).sum()),
            "n_non_positive": int((finite <= 0).sum()) if check_sign else None,
            "min": float(finite.min()) if finite.size else None,
            "max": float(finite.max()) if finite.size else None,
        }
    return {
        "path": str(path),
        "sha256": sha256_file(Path(path)),
        "grid": {
            "p_bar": _axis_summary(table.pressure_bar),
            "t_k": _axis_summary(table.temperature_k),
            "n_nodes": int(table.pressure_bar.size * table.temperature_k.size),
            "n_missing_nodes": table.n_missing_nodes,
        },
        "columns": columns,
    }


def validity_mask(table: Table | str | Path) -> np.ndarray:
    """(nP, nT) mask: every required property finite, and strictly positive except alpha."""
    table = as_table(table)
    required = [name for name in REQUIRED_COLUMNS if name not in AXES]
    missing = [REQUIRED_COLUMNS[name] for name in required if name not in table.names]
    if missing:
        raise ValueError(f"Missing required column(s): {', '.join(missing)}")
    mask = np.ones(table.values.shape[:2], dtype=bool)
    for name in required:
        arr = table.column(name)
        mask &= np.isfinite(arr)
        if name in POSITIVE_PROPERTIES:
            mask &= arr > 0
    return mask


def inside_domain(table: Table, p_bar, t_k) -> np.ndarray:
    p, t = np.asarray(p_bar, dtype=float), np.asarray(t_k, dtype=float)
    return (
        np.isfinite(p) & np.isfinite(t)
        & (p >= table.pressure_bar[0]) & (p <= table.pressure_bar[-1])
        & (t >= table.temperature_k[0]) & (t <= table.temperature_k[-1])
    )


def domain_check(table: Table | str | Path, P_bar, T_K) -> dict:
    """Which requested (P, T) points fall outside the rectangular table domain (non-finite points count as outside)."""
    table = as_table(table)
    p, t = np.broadcast_arrays(np.atleast_1d(np.asarray(P_bar, dtype=float)), np.atleast_1d(np.asarray(T_K, dtype=float)))
    inside = inside_domain(table, p, t)
    return {
        "domain": {
            "p_bar": [float(table.pressure_bar[0]), float(table.pressure_bar[-1])],
            "t_k": [float(table.temperature_k[0]), float(table.temperature_k[-1])],
        },
        "n_points": int(inside.size),
        "n_outside": int((~inside).sum()),
        "inside": inside,
        "outside_points": [
            {"index": int(k), "p_bar": float(p[k]), "t_k": float(t[k])} for k in np.flatnonzero(~inside)
        ],
    }
