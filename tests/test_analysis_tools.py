from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

from planetary_eos_lab.analysis import (
    compare_tables,
    domain_check,
    load_table,
    phase_fractions_along,
    profile_along,
    resolution_convergence,
    table_quality,
    validity_mask,
)
from planetary_eos_lab.cli import check_table

P_AXIS = np.linspace(1000.0, 50000.0, 8)  # bar
T_AXIS = np.linspace(800.0, 2200.0, 6)  # K

# Linear in P and T, so bilinear interpolation is exact. alpha is deliberately negative-capable.
PROPERTIES = {
    "rho,kg/m3": lambda p, t: 3000.0 + 0.01 * p - 0.1 * t,
    "vp,km/s": lambda p, t: 7.5 + 2.0e-5 * p - 3.0e-4 * t,
    "vs,km/s": lambda p, t: 4.2 + 1.0e-5 * p - 2.0e-4 * t,
    "cp,J/K/m3": lambda p, t: 3.5e6 + 1.0 * p + 100.0 * t,
    "alpha,1/K": lambda p, t: 3.0e-5 + 1.0e-11 * p - 1.0e-9 * t,
    "Ks,bar": lambda p, t: 1.2e6 + 5.0 * p - 100.0 * t,
    "Gs,bar": lambda p, t: 7.0e5 + 2.0 * p - 80.0 * t,
}


def write_tab(path: Path, p_axis, t_axis, columns: dict, *, p_first: bool = False, drop=()) -> Path:
    """Perple_X-style table; columns maps header label -> f(P, T) or a (nP, nT) array."""
    labels = (["P(bar)", "T(K)"] if p_first else ["T(K)", "P(bar)"]) + list(columns)
    lines = ["|6.6.6", path.stem, "2"]
    for name, axis in (("T(K)", t_axis), ("P(bar)", p_axis)):
        lines += [name, f"{axis[0]!r}", f"{(axis[-1] - axis[0]) / (len(axis) - 1)!r}", str(len(axis))]
    lines += [str(len(labels)), "  ".join(labels)]
    for i, p in enumerate(p_axis):
        for j, t in enumerate(t_axis):
            if (i, j) in drop:
                continue
            values = [col(p, t) if callable(col) else col[i][j] for col in columns.values()]
            axes = [p, t] if p_first else [t, p]
            lines.append(" ".join(repr(float(v)) for v in axes + values))
    path.write_text("\n".join(lines) + "\n")
    return path


def property_columns(**overrides) -> dict:
    """Property arrays on the standard grid, with optional {label: {(i, j): value}} overrides."""
    pp, tt = np.meshgrid(P_AXIS, T_AXIS, indexing="ij")
    columns = {label: f(pp, tt) for label, f in PROPERTIES.items()}
    for label, edits in overrides.items():
        for node, value in edits.items():
            columns[label][node] = value
    return columns


def test_load_table_identifies_axes_from_header_not_position(tmp_path: Path) -> None:
    t_first = load_table(write_tab(tmp_path / "a.tab", P_AXIS, T_AXIS, PROPERTIES))
    p_first = load_table(write_tab(tmp_path / "b.tab", P_AXIS, T_AXIS, PROPERTIES, p_first=True))

    assert np.array_equal(t_first.pressure_bar, P_AXIS)
    assert np.array_equal(t_first.temperature_k, T_AXIS)
    assert t_first.names == p_first.names
    assert "rho_kgm3" in t_first.names and "gs_bar" in t_first.names
    np.testing.assert_array_equal(t_first.values, p_first.values)
    np.testing.assert_allclose(t_first.column("rho_kgm3")[3, 2], PROPERTIES["rho,kg/m3"](P_AXIS[3], T_AXIS[2]))


def test_table_quality_reports_grid_counts_and_hash(tmp_path: Path) -> None:
    columns = property_columns(**{
        "rho,kg/m3": {(0, 0): np.nan, (1, 1): np.nan},
        "vs,km/s": {(2, 2): -0.5, (2, 3): 0.0},
        "Ks,bar": {(4, 4): np.inf},
        "alpha,1/K": {(5, 5): -1.0e-5},
    })
    path = write_tab(tmp_path / "q.tab", P_AXIS, T_AXIS, columns, drop={(7, 5)})

    report = table_quality(path)

    assert report["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    grid = report["grid"]
    assert grid["p_bar"] == {"min": 1000.0, "max": 50000.0, "n": 8, "step": 7000.0}
    assert grid["t_k"] == {"min": 800.0, "max": 2200.0, "n": 6, "step": 280.0}
    assert grid["n_nodes"] == 48 and grid["n_missing_nodes"] == 1
    cols = report["columns"]
    assert cols["rho_kgm3"]["n_nan"] == 3  # two NaN values + the missing node
    assert cols["ks_bar"]["n_inf"] == 1
    assert cols["ks_bar"]["max"] < np.inf  # min/max over finite values only
    assert cols["vs_kms"]["n_non_positive"] == 2
    assert cols["alpha_pk"]["n_non_positive"] is None
    assert cols["vp_kms"]["min"] == pytest.approx(PROPERTIES["vp,km/s"](1000.0, 2200.0))


def test_validity_mask_flags_nonfinite_and_non_positive_nodes(tmp_path: Path) -> None:
    columns = property_columns(**{
        "rho,kg/m3": {(0, 0): np.nan},
        "vs,km/s": {(2, 2): 0.0},
        "alpha,1/K": {(3, 3): -1.0e-5, (4, 4): np.inf},
    })
    mask = validity_mask(write_tab(tmp_path / "v.tab", P_AXIS, T_AXIS, columns))

    expected = np.ones((8, 6), dtype=bool)
    expected[0, 0] = expected[2, 2] = expected[4, 4] = False  # negative finite alpha stays valid
    np.testing.assert_array_equal(mask, expected)


def test_validity_mask_requires_all_property_columns(tmp_path: Path) -> None:
    partial = {k: v for k, v in PROPERTIES.items() if k != "Gs,bar"}
    with pytest.raises(ValueError, match="GS_bar"):
        validity_mask(write_tab(tmp_path / "p.tab", P_AXIS, T_AXIS, partial))


def test_domain_check_lists_points_outside(tmp_path: Path) -> None:
    table = load_table(write_tab(tmp_path / "d.tab", P_AXIS, T_AXIS, PROPERTIES))
    p = [1000.0, 50000.0, 999.0, 20000.0, np.nan]
    t = [800.0, 2200.0, 1000.0, 2300.0, 1000.0]

    result = domain_check(table, p, t)

    assert result["domain"] == {"p_bar": [1000.0, 50000.0], "t_k": [800.0, 2200.0]}
    assert result["n_points"] == 5 and result["n_outside"] == 3
    np.testing.assert_array_equal(result["inside"], [True, True, False, False, False])
    assert [pt["index"] for pt in result["outside_points"]] == [2, 3, 4]


def test_profile_along_is_exact_for_linear_fields_and_never_extrapolates(tmp_path: Path) -> None:
    table = load_table(write_tab(tmp_path / "pr.tab", P_AXIS, T_AXIS, PROPERTIES))
    rng = np.random.default_rng(0)
    p = np.concatenate([rng.uniform(1000.0, 50000.0, 50), [50000.0, 1000.0, 60000.0, 20000.0]])
    t = np.concatenate([rng.uniform(800.0, 2200.0, 50), [2200.0, 800.0, 1000.0, 700.0]])

    profile = profile_along(table, p, t)

    inside = profile["inside"]
    np.testing.assert_array_equal(inside, [True] * 52 + [False, False])
    for label, f in PROPERTIES.items():
        name = {"rho,kg/m3": "rho_kgm3", "vp,km/s": "vp_kms", "vs,km/s": "vs_kms", "cp,J/K/m3": "cp_jm3k",
                "alpha,1/K": "alpha_pk", "Ks,bar": "ks_bar", "Gs,bar": "gs_bar"}[label]
        np.testing.assert_allclose(profile[name][inside], f(p[inside], t[inside]), rtol=1e-12)
        assert np.isnan(profile[name][~inside]).all()


def test_profile_along_nan_node_only_affects_its_cells(tmp_path: Path) -> None:
    columns = property_columns(**{"rho,kg/m3": {(3, 3): np.nan}})
    table = load_table(write_tab(tmp_path / "n.tab", P_AXIS, T_AXIS, columns))
    rho = PROPERTIES["rho,kg/m3"]
    p = [P_AXIS[3], P_AXIS[2], 0.5 * (P_AXIS[2] + P_AXIS[3]), P_AXIS[2]]
    t = [T_AXIS[2], T_AXIS[3], 0.5 * (T_AXIS[2] + T_AXIS[3]), 0.5 * (T_AXIS[2] + T_AXIS[3])]

    out = profile_along(table, p, t)["rho_kgm3"]

    assert out[0] == pytest.approx(rho(p[0], t[0]))  # on a node next to the NaN node
    assert out[1] == pytest.approx(rho(p[1], t[1]))
    assert np.isnan(out[2])  # inside a cell with the NaN corner
    assert out[3] == pytest.approx(rho(p[3], t[3]))  # on an edge not touching the NaN node


def test_phase_fractions_along_nearest_node_sums_repeated_columns(tmp_path: Path) -> None:
    pp, tt = np.meshgrid(P_AXIS, T_AXIS, indexing="ij")
    ol_a = 40.0 + 0.0 * pp
    ol_b = np.where(pp > 25000.0, 10.0, np.nan)  # second olivine column present only at high P
    cpx = 60.0 - ol_b.copy()
    cpx[np.isnan(ol_b)] = 60.0
    gt = np.full_like(pp, np.nan)
    path = write_tab(tmp_path / "modes.tab", P_AXIS, T_AXIS, {"Ol": ol_a, "Cpx": cpx, "Ol ": ol_b, "Gt": gt}, p_first=True)
    # "Ol " is written as a second "Ol" header token.

    p = [1000.0, 50000.0, 23000.0, 60000.0]  # 23000 is nearest to node 22000 (<= 25000)
    t = [800.0, 2100.0, 1500.0, 1500.0]
    out = phase_fractions_along(path, p, t, ["Ol", "Cpx", "Gt", "Wad"])

    np.testing.assert_array_equal(out["inside"], [True, True, True, False])
    np.testing.assert_array_equal(out["Ol"][:3], [40.0, 50.0, 40.0])
    np.testing.assert_array_equal(out["Cpx"][:3], [60.0, 50.0, 60.0])
    np.testing.assert_array_equal(out["Gt"][:3], [0.0, 0.0, 0.0])  # NaN modes count as absent
    assert np.isnan(out["Wad"]).all()  # phase not in the table
    assert np.isnan(out["Ol"][3])  # outside the domain


def test_compare_tables_at_common_nodes(tmp_path: Path) -> None:
    a = write_tab(tmp_path / "a.tab", P_AXIS, T_AXIS, PROPERTIES)
    b_props = dict(PROPERTIES)
    b_props["rho,kg/m3"] = lambda p, t: PROPERTIES["rho,kg/m3"](p, t) * (1.0 + 1.0e-6 * p)
    b_props["vp,km/s"] = lambda p, t: np.where(p > 1.0e9, 0.0, np.nan)  # all NaN: nothing to compare
    b = write_tab(tmp_path / "b.tab", P_AXIS[2:], T_AXIS[:4], b_props)

    result = compare_tables(a, b)

    assert result["n_common_nodes"] == 6 * 4
    rho = result["properties"]["rho_kgm3"]
    pct = 1.0e-4 * P_AXIS[2:]
    assert rho["n_compared"] == 24
    assert rho["max_abs_pct"] == pytest.approx(pct.max())
    assert rho["mean_abs_pct"] == pytest.approx(pct.mean())
    assert rho["rms_pct"] == pytest.approx(np.sqrt(np.mean(pct**2)))
    assert rho["p_bar_at_max"] == 50000.0
    assert T_AXIS[0] <= rho["t_k_at_max"] <= T_AXIS[3]
    assert result["properties"]["vp_kms"] == {"n_compared": 0}
    assert result["properties"]["vs_kms"]["max_abs_pct"] == 0.0


def test_resolution_convergence_interpolates_coarse_onto_fine_nodes(tmp_path: Path) -> None:
    coarse = write_tab(tmp_path / "coarse.tab", P_AXIS[::2], T_AXIS[::2], PROPERTIES)
    fine_p = np.linspace(1000.0, 60000.0, 21)  # extends beyond the coarse domain
    fine_t = np.linspace(800.0, 1800.0, 11)
    fine_props = dict(PROPERTIES)
    fine_props["Gs,bar"] = lambda p, t: PROPERTIES["Gs,bar"](p, t) * 1.01
    fine = write_tab(tmp_path / "fine.tab", fine_p, fine_t, fine_props)

    result = resolution_convergence(coarse, fine)

    p_max = P_AXIS[::2][-1]
    n_inside = int((fine_p <= p_max).sum()) * fine_t.size
    assert result["n_fine_nodes"] == fine_p.size * fine_t.size
    assert result["n_inside_coarse_domain"] == n_inside
    rho = result["properties"]["rho_kgm3"]
    assert rho["n_compared"] == n_inside
    assert rho["max_abs_pct"] == pytest.approx(0.0, abs=1e-9)
    assert result["properties"]["gs_bar"]["mean_abs_pct"] == pytest.approx(1.0)


def run_cli(capsys, argv) -> tuple[int, dict]:
    code = check_table.main(argv + ["--json"])
    return code, json.loads(capsys.readouterr().out)


def test_check_table_cli_json(tmp_path: Path, capsys) -> None:
    columns = property_columns(**{"rho,kg/m3": {(0, 0): np.nan}})
    a = write_tab(tmp_path / "a.tab", P_AXIS, T_AXIS, columns)
    b = write_tab(tmp_path / "b.tab", P_AXIS, T_AXIS, PROPERTIES)
    points = tmp_path / "points.csv"
    points.write_text("P_bar,T_K\n2000,900\n70000,900\n")

    code, quality = run_cli(capsys, ["quality", str(a)])
    assert code == 0 and quality["columns"]["rho_kgm3"]["n_nan"] == 1
    assert quality["sha256"] == hashlib.sha256(a.read_bytes()).hexdigest()

    code, domain = run_cli(capsys, ["domain", str(a), "--p-bar", "2000", "3000", "--t-k", "900", "1000"])
    assert code == 0 and domain["n_outside"] == 0 and domain["inside"] == [True, True]

    code, domain = run_cli(capsys, ["domain", str(a), "--points", str(points)])
    assert code == 1 and domain["outside_points"] == [{"index": 1, "p_bar": 70000.0, "t_k": 900.0}]

    code, compared = run_cli(capsys, ["compare", str(a), str(b)])
    assert code == 0 and compared["properties"]["rho_kgm3"]["n_compared"] == 47

    code, converged = run_cli(capsys, ["convergence", str(b), str(b)])
    assert code == 0 and converged["properties"]["vp_kms"]["max_abs_pct"] == pytest.approx(0.0, abs=1e-9)


def test_check_table_cli_text_and_errors(tmp_path: Path, capsys) -> None:
    a = write_tab(tmp_path / "a.tab", P_AXIS, T_AXIS, PROPERTIES)

    assert check_table.main(["quality", str(a)]) == 0
    assert "rho_kgm3" in capsys.readouterr().out
    assert check_table.main(["compare", str(a), str(a)]) == 0
    assert "common nodes: 48" in capsys.readouterr().out
    assert check_table.main(["domain", str(a), "--p-bar", "1", "--t-k", "900"]) == 1
    assert "OUTSIDE #0" in capsys.readouterr().out
    assert check_table.main(["domain", str(a), "--p-bar", "2000"]) == 2
    assert check_table.main(["quality", str(tmp_path / "missing.tab")]) == 2
