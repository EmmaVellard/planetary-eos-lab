"""Planetary EOS Lab from Python, without the GUI.

Warren (2005) Preferred bulk silicate Moon -> residual mantle after extracting a
Taylor (1999) highlands crust -> Ti-free -> stx24 table with Perple_X -> table
quality check -> properties along a P-T path.

    python examples/warren_mantle_stx24.py --perplex-dir /path/to/perplex [--outdir DIR] [--full-grid]

By default the grid is coarse (15 x 15 nodes, a few seconds) so the example runs
quickly; --full-grid uses the pipeline default (300 x 300 after refinement).
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import make_compositions  # noqa: E402
import run_perplex  # noqa: E402
from planetary_eos_lab.analysis.profiles import profile_along  # noqa: E402
from planetary_eos_lab.analysis.quality import table_quality  # noqa: E402

# Taylor (1999), "The Moon", Encyclopedia of the Solar System, Table III, Highlands
# (Cr2O3 and MnO converted from Cr 800 ppm and Mn 570 ppm).
CRUST = {"SiO2": 45.0, "TiO2": 0.56, "Al2O3": 24.6, "FeO": 6.6, "MgO": 6.8, "CaO": 15.8,
         "Na2O": 0.45, "K2O": 0.03, "Cr2O3": 0.1169, "MnO": 0.0736}
# Crust mass / silicate mass for crust architecture A of the lunar study
# (lunar-bsm-interior-models, results/stage_e3_m1/M1_COMPOSITIONS_FULL.csv). Use your own value.
F_CRUST = 0.05680851535394975
COARSE = run_perplex.PerplexOptions(sample_on_grid=True, x_nodes=(15, 15), y_nodes=(15, 15), grid_levels=(1, 1))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--perplex-dir", required=True, type=Path)
    parser.add_argument("--outdir", type=Path, default=REPO / "outputs" / "example_warren_mantle_stx24")
    parser.add_argument("--full-grid", action="store_true")
    args = parser.parse_args()
    project = "example_warren_mantle_stx24"

    # 1. Composition: start from the published Warren (2005) row recorded in the catalogue.
    catalogue = json.loads((REPO / "configs" / "lunar_bsm_models.json").read_text())["models"]
    warren = next(m for m in catalogue if m["project"] == "moon_w05_preferred_bsm")
    entry = {
        "project": project,
        "description": "Warren (2005) Preferred mantle after a Taylor (1999) highlands crust, Ti-free",
        "oxides_wt_percent": warren["source_transformation"]["source_oxides_wt_percent"],
        "mantle_extraction": {"crust_oxides_wt_percent": CRUST, "crust_mass_fraction": F_CRUST,
                              "crust_source": "Taylor (1999), Highlands"},
        "excluded_oxides": warren["source_transformation"]["excluded_oxides"] + ["TiO2"],
        "database": "stx24",
    }
    model_composition = make_compositions.model_from_config_entry(entry)
    make_compositions.write_composition(model_composition, outdir=args.outdir)

    # 2. Perple_X: BUILD, VERTEX, WERAMI (and the phase modes).
    model = run_perplex.ModelConfig(
        project=project,
        composition_file=args.outdir / f"{project}.json",
        build_input_file=run_perplex.default_build_template_for_database("stx24"),
        output_dir=args.outdir,
        work_dir=args.outdir / "work",
        database="stx24",
        werami_input_sequence=run_perplex.default_werami_sequence_for_database("stx24"),
        perplex_options=run_perplex.DEFAULT_PERPLEX_OPTIONS if args.full_grid else COARSE,
        phase_modes=True,
    )
    run_perplex.run_model(args.perplex_dir, model, skip_validation=not args.full_grid)

    # 3. Check the table, then read it along a P-T path (an illustrative path, not a lunar geotherm).
    table = args.outdir / f"{project}_planetprofile_native.tab"
    quality = table_quality(table)
    print(json.dumps({"grid": quality["grid"], "sha256": quality["sha256"]}, indent=1))
    p_bar = [5000, 15000, 25000, 35000, 45000]
    t_k = [900, 1200, 1400, 1550, 1650]
    profile = profile_along(table, p_bar, t_k)
    print("P (bar)  T (K)   rho (kg/m3)  Vp (km/s)  Vs (km/s)  inside")
    for i, (p, t) in enumerate(zip(p_bar, t_k)):
        print(f"{p:7.0f}  {t:5.0f}   {profile['rho_kgm3'][i]:10.1f}  {profile['vp_kms'][i]:9.3f}  "
              f"{profile['vs_kms'][i]:9.3f}  {bool(profile['inside'][i])}")


if __name__ == "__main__":
    main()
