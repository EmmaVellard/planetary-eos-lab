"""Your study with Planetary EOS Lab, without the GUI.

Copy this file, edit the block "YOUR STUDY" below, then run it:

    python examples/my_study.py

For each model it writes the composition file, runs Perple_X (BUILD, VERTEX, WERAMI), validates
the table, exports it in PlanetProfile format with a provenance manifest, and, if you give a P-T
path, prints the properties along it. Everything goes to outputs/<STUDY_NAME>/.
"""
from __future__ import annotations

import sys
from pathlib import Path

# ============================== YOUR STUDY: edit this block ==============================

STUDY_NAME = "my_study"
PERPLEX_DIR = "~/Documents/Code/perplex"  # folder with bin/ and datafiles/

# Built-in: stx21, stx24, hp633, hp636, se15_fes_core (Fe-S cores), dew17_hhph, hpha02_hydrous,
# dew13_hydrous, dew17_comet; or a database declared under custom_databases in configs/models.json.
DATABASE = "stx24"

# One entry per model. Oxide compositions in wt% (normalized to 100 by the pipeline); for element
# databases (se15_fes_core, dew*) use "components_wt_percent" instead of "oxides_wt_percent".
MODELS = [
    {
        "project": "warren_preferred_mantle",
        "description": "Warren (2005) Preferred bulk silicate Moon, mantle after a highlands crust",
        # Warren (2005), Meteoritics & Planetary Science 40, 477-506, Table 6, core-excluded row
        "oxides_wt_percent": {"SiO2": 46.8, "TiO2": 0.18, "Al2O3": 3.87, "FeO": 9.24, "MgO": 36.0,
                              "CaO": 3.06, "Cr2O3": 0.44, "MnO": 0.132, "Na2O": 0.051, "K2O": 0.005},
        # Optional: mantle left after extracting a crust of mass fraction f (crust mass / silicate mass).
        "mantle_extraction": {
            "crust_oxides_wt_percent": {"SiO2": 45.0, "TiO2": 0.56, "Al2O3": 24.6, "FeO": 6.6, "MgO": 6.8,
                                        "CaO": 15.8, "Na2O": 0.45, "K2O": 0.03, "Cr2O3": 0.1169, "MnO": 0.0736},
            "crust_mass_fraction": 0.0568,
            "crust_source": "Taylor (1999), The Moon, Encyclopedia of the Solar System, Table III, Highlands",
        },
        # Optional: oxides dropped after the extraction (the rest is renormalized).
        "excluded_oxides": ["TiO2", "MnO", "K2O"],
    },
    # {
    #     "project": "fe95s5_core",
    #     "database": "se15_fes_core",          # a model can use another database than DATABASE
    #     "components_wt_percent": {"Fe": 95.0, "S": 5.0},
    # },
]

# P-T domain of the tables: None keeps the database default, or e.g.
# {"pressure_bar": {"min": 1000, "max": 50000}, "temperature_k": {"min": 300, "max": 2200}}
PT_RANGE = None

COARSE_GRID = True    # True: 15 x 15 nodes, seconds, for checking a setup; False: the pipeline default (300 x 300)
PHASE_MODES = True    # also write <project>_phase_modes.tab (volume % of every phase)

# Optional P-T path (bar, K) along which to print rho, Vp, Vs; your own profile, not computed here.
P_T_PATH = [(5000, 900), (15000, 1200), (25000, 1400), (35000, 1550), (45000, 1650)]

# ==========================================================================================

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import export_planetprofile  # noqa: E402
import make_compositions  # noqa: E402
import run_perplex  # noqa: E402
from planetary_eos_lab.analysis.profiles import profile_along  # noqa: E402

COARSE = run_perplex.PerplexOptions(sample_on_grid=True, x_nodes=(15, 15), y_nodes=(15, 15), grid_levels=(1, 1))


def main() -> int:
    perplex_dir = Path(PERPLEX_DIR).expanduser()
    outdir = REPO / "outputs" / STUDY_NAME
    models = []
    for entry in MODELS:
        entry = {"database": DATABASE, **entry}
        composition = make_compositions.model_from_config_entry(entry)
        make_compositions.write_configured_composition(composition, outdir=outdir / "compositions")
        database = composition.database
        models.append(run_perplex.ModelConfig(
            project=entry["project"],
            composition_file=outdir / "compositions" / f"{entry['project']}.json",
            build_input_file=run_perplex.default_build_template_for_database(database),
            output_dir=outdir / entry["project"],
            work_dir=outdir / entry["project"] / "work",
            database=database,
            werami_input_sequence=run_perplex.default_werami_sequence_for_database(database),
            perplex_options=COARSE if COARSE_GRID else run_perplex.DEFAULT_PERPLEX_OPTIONS,
            pt_range=run_perplex.pt_range_from_config(PT_RANGE, entry["project"]),
            phase_modes=PHASE_MODES,
            planetprofile_filename=entry.get("planetprofile_filename"),
        ))

    for model in models:
        run_perplex.run_model(perplex_dir, model)

    config = run_perplex.PipelineConfig(perplex_dir=perplex_dir, database=DATABASE, models=models)
    exported = export_planetprofile.export_tables(config, models, outdir / "planetprofile")
    print(f"\nPlanetProfile tables and manifest: {(outdir / 'planetprofile').relative_to(REPO)}")
    for table in exported:
        print(f"  {table.destination.name}")

    if P_T_PATH:
        p_bar, t_k = zip(*P_T_PATH)
        for model in models:
            profile = profile_along(model.output_dir / f"{model.project}_planetprofile_native.tab", p_bar, t_k)
            print(f"\n{model.project}: P (bar)  T (K)  rho (kg/m3)  Vp (km/s)  Vs (km/s)  inside the table")
            for i, (p, t) in enumerate(P_T_PATH):
                print(f"  {p:9.0f} {t:6.0f}  {profile['rho_kgm3'][i]:10.1f}  {profile['vp_kms'][i]:9.3f}  "
                      f"{profile['vs_kms'][i]:9.3f}  {bool(profile['inside'][i])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
