"""Sample table properties along a P-T path (for example a T(r) profile). P in bar, T in K.

Points outside the table domain are returned as NaN with inside=False: never extrapolated.
"""
from __future__ import annotations

import numpy as np

from planetary_eos_lab.analysis.quality import Table, as_table, inside_domain


def _bracket(axis: np.ndarray, x: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Lower/upper node index and fractional weight of x on a sorted axis (x clipped into range)."""
    if axis.size == 1:
        zero = np.zeros(x.shape, dtype=int)
        return zero, zero, np.zeros(x.shape)
    x = np.clip(x, axis[0], axis[-1])
    lo = np.clip(np.searchsorted(axis, x, side="right") - 1, 0, axis.size - 2)
    return lo, lo + 1, (x - axis[lo]) / (axis[lo + 1] - axis[lo])


def _path(table: Table, P_bar, T_K) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    p, t = np.broadcast_arrays(np.atleast_1d(np.asarray(P_bar, dtype=float)), np.atleast_1d(np.asarray(T_K, dtype=float)))
    return p, t, inside_domain(table, p, t)


def profile_along(table: Table | str, P_bar, T_K) -> dict[str, np.ndarray]:
    """Bilinear interpolation in P and T of every non-axis column; a NaN corner node gives NaN."""
    table = as_table(table)
    p, t, inside = _path(table, P_bar, T_K)
    i0, i1, wp = _bracket(table.pressure_bar, np.where(inside, p, table.pressure_bar[0]))
    j0, j1, wt = _bracket(table.temperature_k, np.where(inside, t, table.temperature_k[0]))
    wp, wt = wp[..., None], wt[..., None]
    v = table.values

    def term(node, weight):
        # A zero-weight corner must not spread its NaN onto a point lying on a node or edge.
        return np.where(weight == 0, 0.0, node * weight)

    result = (
        term(v[i0, j0], (1 - wp) * (1 - wt)) + term(v[i1, j0], wp * (1 - wt))
        + term(v[i0, j1], (1 - wp) * wt) + term(v[i1, j1], wp * wt)
    )
    result[~inside] = np.nan
    out = {name: result[..., k] for k, name in enumerate(table.names)}
    out["inside"] = inside
    return out


def phase_fractions_along(phase_table: Table | str, P_bar, T_K, phases) -> dict[str, np.ndarray]:
    """Nearest-node modal fraction per named phase, summing repeated columns of that name.

    A phase with no column in the table is NaN everywhere; NaN entries count as absent (0).
    """
    table = as_table(phase_table)
    p, t, inside = _path(table, P_bar, T_K)
    pi = np.abs(table.pressure_bar[:, None] - p.ravel()[None, :]).argmin(axis=0).reshape(p.shape)
    tj = np.abs(table.temperature_k[:, None] - t.ravel()[None, :]).argmin(axis=0).reshape(t.shape)
    out: dict[str, np.ndarray] = {}
    for phase in phases:
        columns = [k for k, name in enumerate(table.names) if name.strip() == phase]
        if not columns:
            out[phase] = np.full(p.shape, np.nan)
            continue
        frac = np.nansum(table.values[pi, tj][..., columns], axis=-1)
        out[phase] = np.where(inside, frac, np.nan)
    out["inside"] = inside
    return out
