"""First use of Planetary EOS Lab, from a fresh clone, in one command.

    python examples/first_run.py --perplex-dir /path/to/perplex

1. checks the installation (planetary-eos-selftest);
2. creates configs/models.json from configs/models.example.json if it does not exist,
   with your Perple_X folder (an existing config is never changed);
3. runs the first example model (lunar near-side surface proxy, stx21) on a coarse
   grid in outputs/first_run/, validates the table and writes it in PlanetProfile format;
4. prints the table's grid and ranges, and where the files are.

Then open the GUI with `planetary-eos-gui`, or adapt examples/warren_mantle_stx24.py.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

import make_compositions  # noqa: E402
import run_perplex  # noqa: E402
from planetary_eos_lab.analysis.quality import table_quality  # noqa: E402
from planetary_eos_lab.cli import selftest  # noqa: E402

COARSE = run_perplex.PerplexOptions(sample_on_grid=True, x_nodes=(15, 15), y_nodes=(15, 15), grid_levels=(1, 1))


def main() -> int:
    parser = argparse.ArgumentParser(description="First use of Planetary EOS Lab.")
    parser.add_argument("--perplex-dir", required=True, type=Path, help="Perple_X folder (with bin/ and datafiles/)")
    args = parser.parse_args()
    perplex_dir = args.perplex_dir.expanduser().resolve()

    print("== 1. Installation check")
    if selftest.main(["--perplex-dir", str(perplex_dir)]) != 0:
        print("Fix the FAIL lines above, then run this script again.")
        return 1

    print("\n== 2. Config")
    config_path = REPO / "configs" / "models.json"
    if config_path.exists():
        print(f"Keeping your existing {config_path.relative_to(REPO)}")
    else:
        config = json.loads((REPO / "configs" / "models.example.json").read_text())
        config["perplex_dir"] = str(perplex_dir)
        config_path.write_text(json.dumps(config, indent=2) + "\n")
        print(f"Created {config_path.relative_to(REPO)} from models.example.json")

    print("\n== 3. First model")
    example = json.loads((REPO / "configs" / "models.example.json").read_text())["models"][0]
    outdir = REPO / "outputs" / "first_run"
    composition = make_compositions.model_from_config_entry(example)
    make_compositions.write_configured_composition(composition, outdir=outdir)
    model = run_perplex.ModelConfig(
        project=example["project"],
        composition_file=outdir / f"{example['project']}.json",
        build_input_file=run_perplex.default_build_template_for_database(composition.database),
        output_dir=outdir,
        work_dir=outdir / "work",
        database=composition.database,
        werami_input_sequence=run_perplex.default_werami_sequence_for_database(composition.database),
        perplex_options=COARSE,
    )
    run_perplex.run_model(perplex_dir, model)

    print("\n== 4. Result")
    table = outdir / f"{example['project']}_planetprofile_native.tab"
    quality = table_quality(table)
    grid = quality["grid"]
    print(f"Table: {table.relative_to(REPO)}")
    print(f"  P {grid['p_bar']['min']:g}-{grid['p_bar']['max']:g} bar, T {grid['t_k']['min']:g}-{grid['t_k']['max']:g} K, "
          f"{grid['n_nodes']} nodes (coarse grid for this check; the pipeline default is finer)")
    for name in ("rho_kgm3", "vp_kms", "vs_kms"):
        column = quality["columns"][name]
        print(f"  {name}: {column['min']:.4g} to {column['max']:.4g}, {column['n_nan']} NaN")
    print("\nNext: planetary-eos-gui, or python examples/warren_mantle_stx24.py --perplex-dir ...")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
