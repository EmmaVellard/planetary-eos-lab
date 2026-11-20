"""Compare two tables property by property: (b - a) / a in percent."""
from __future__ import annotations

import numpy as np

from planetary_eos_lab.analysis.profiles import profile_along
from planetary_eos_lab.analysis.quality import Table, as_table


def relative_diff_stats(a, b, p_bar, t_k) -> dict:
    """Statistics of 100 (b - a) / a over points where both are finite and a != 0."""
    a, b, p, t = (np.ravel(np.asarray(x, dtype=float)) for x in np.broadcast_arrays(a, b, p_bar, t_k))
    valid = np.isfinite(a) & np.isfinite(b) & (a != 0)
    if not valid.any():
        return {"n_compared": 0}
    pct = 100.0 * (b[valid] - a[valid]) / a[valid]
    k = int(np.argmax(np.abs(pct)))
    return {
        "n_compared": int(valid.sum()),
        "mean_abs_pct": float(np.mean(np.abs(pct))),
        "rms_pct": float(np.sqrt(np.mean(pct**2))),
        "max_abs_pct": float(np.abs(pct[k])),
        "p_bar_at_max": float(p[valid][k]),
        "t_k_at_max": float(t[valid][k]),
    }


def _common_names(a: Table, b: Table) -> list[str]:
    return [name for name in a.names if name in b.names]


def compare_tables(a: Table | str, b: Table | str) -> dict:
    """b relative to a at nodes present in both grids (exact P and T match), per common property."""
    a, b = as_table(a), as_table(b)
    # shortcut: nodes must match exactly as parsed; tables written on different grids share only coincident nodes.
    p, ia, ib = np.intersect1d(a.pressure_bar, b.pressure_bar, return_indices=True)
    t, ja, jb = np.intersect1d(a.temperature_k, b.temperature_k, return_indices=True)
    pp, tt = np.meshgrid(p, t, indexing="ij")
    properties = {
        name: relative_diff_stats(
            a.column(name)[np.ix_(ia, ja)], b.column(name)[np.ix_(ib, jb)], pp, tt
        )
        for name in _common_names(a, b)
    }
    return {"n_common_nodes": int(p.size * t.size), "properties": properties}


def resolution_convergence(coarse: Table | str, fine: Table | str) -> dict:
    """Fine table relative to the coarse table bilinearly interpolated onto the fine nodes inside its domain."""
    coarse, fine = as_table(coarse), as_table(fine)
    pp, tt = np.meshgrid(fine.pressure_bar, fine.temperature_k, indexing="ij")
    interpolated = profile_along(coarse, pp, tt)
    properties = {
        name: relative_diff_stats(interpolated[name], fine.column(name), pp, tt)
        for name in _common_names(coarse, fine)
    }
    return {
        "n_fine_nodes": int(pp.size),
        "n_inside_coarse_domain": int(interpolated["inside"].sum()),
        "properties": properties,
    }
