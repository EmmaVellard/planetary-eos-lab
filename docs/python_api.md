# Using Planetary EOS Lab from Python

The GUI only drives Python functions; everything it does can be scripted. Run scripts from the
repository root (or put it on `sys.path`), since the pipeline modules `make_compositions`,
`run_perplex`, `export_planetprofile` and `validate_tab` live there. A complete example:
[examples/warren_mantle_stx24.py](../examples/warren_mantle_stx24.py).

## With a config file

The shortest route: describe the models in `configs/models.json` (same format the GUI writes) and run
the same steps as the command line.

```python
from pathlib import Path
import make_compositions, run_perplex, export_planetprofile

config_path = Path("configs/models.json")
for model in make_compositions.models_from_config(config_path):
    make_compositions.write_configured_composition(model, outdir=Path("compositions"))

config = run_perplex.load_config(config_path)          # also registers custom_databases
for model in config.models:
    run_perplex.run_model(config.perplex_dir, model)    # BUILD, VERTEX, WERAMI, validation

export_planetprofile.main(["--config", str(config_path)])
```

## Without a config file

| Step | Function |
| --- | --- |
| Composition from a dict | `make_compositions.model_from_config_entry(entry)`; the entry has the keys of a config model (`project`, `oxides_wt_percent`, `database`, and optionally `mantle_extraction`, `excluded_oxides`) |
| Mantle after crust extraction | `make_compositions.residual_mantle_composition(bulk, crust, f)` |
| Write the composition file | `make_compositions.write_composition(model, outdir=...)` |
| One Perple_X model | `run_perplex.ModelConfig(project, composition_file, build_input_file, output_dir, work_dir, database, perplex_options, pt_range, phase_modes)` |
| Default template and WERAMI answers | `run_perplex.default_build_template_for_database(db)`, `run_perplex.default_werami_sequence_for_database(db)` |
| Grid resolution | `run_perplex.PerplexOptions(sample_on_grid, x_nodes, y_nodes, grid_levels, ...)` |
| Run it | `run_perplex.run_model(perplex_dir, model, skip_validation=False)` |
| Validate a table | `validate_tab.validate_project_output(project, output_dir, tab_path=...)` |

Outputs of a run in `output_dir`: `<project>_planetprofile_native.tab` (PlanetProfile format),
`<project>_planetprofile.tab`, `<project>_raw_werami.tab`, `<project>_phase_modes.tab` when
`phase_modes=True`, and the logs `build.log`, `vertex.log`, `werami.log`.

## Reading and checking tables

```python
from planetary_eos_lab.analysis import (
    load_table, table_quality, validity_mask, domain_check,
    profile_along, phase_fractions_along, compare_tables, resolution_convergence,
)

table = load_table("outputs/my_mantle/my_mantle_planetprofile_native.tab")
table_quality(table_path)                 # grid, NaN / Inf / non-positive counts, sha256
validity_mask(table)                      # (nP, nT) boolean: all properties finite and positive
domain_check(table, P_bar, T_K)           # which requested points are outside the table
profile_along(table, P_bar, T_K)          # rho, Vp, Vs, Cp, alpha, Ks, Gs along a path; 'inside' mask
phase_fractions_along(load_table(".../my_mantle_phase_modes.tab"), P_bar, T_K, ["O", "Opx", "Gt"])
                                          # phase names as in the header of the phase-mode table
compare_tables(table_a, table_b)          # (b - a)/a in % at common nodes: mean, RMS, max and where
resolution_convergence(coarse, fine)      # coarse interpolated onto the fine nodes
```

Units are those of the tables: P in bar, T in K, ρ in kg/m³, velocities in km/s, moduli in bar.
`profile_along` interpolates bilinearly and never extrapolates: points outside the grid get NaN and
`inside=False`. A P–T path is yours to supply (from PlanetProfile, a thermal model, or a pressure
profile); the package does not compute one.
