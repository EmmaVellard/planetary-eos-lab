# Perple_X Workbench

Objective: provide a local GUI-first workflow for defining rock/planetary compositions, running Perple_X BUILD/VERTEX/WERAMI, validating outputs, and exporting PlanetProfile-ready EOS tables.

The included Moon near-side/far-side models are example smoke tests. They are useful for checking the workflow, not publication-ready lunar mantle compositions. For composition provenance and caveats, see [composition.md](composition.md).

## Quick Start

```bash
git clone https://github.com/EmmaVellard/perplex-workbench.git
cd perplex-workbench
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp configs/models.example.json configs/models.json
streamlit run perplex_workbench/gui/streamlit_app.py
```

The app opens in your browser. Use `configs/models.json` as your local editable config; it is ignored by Git.

Perple_X itself is an external dependency. Install it from [jadconnolly/Perple_X](https://github.com/jadconnolly/Perple_X), then set the GUI `Perple_X directory` to the local folder that contains BUILD, VERTEX, WERAMI, and the `datafiles/` directory.

## GUI Workflow

The left menu has two main workspaces:

- `Build Composition`: create a new model, copy an existing model, edit oxide values and metadata, preview normalization, and delete saved models from `configs/models.json`.
- `Run Pipeline`: select a saved model, review caveats, generate composition files, run Perple_X, validate outputs, make comparison plots, and export PlanetProfile tables.

GitHub hosts this workbench only; it does not include BUILD, VERTEX, WERAMI, or Perple_X datafiles.

## What The GUI Writes

- Source model definitions: `configs/models.json`
- Generated composition files: `compositions/`
- Perple_X work/output files: `outputs/<project>/`
- PlanetProfile exports: `outputs/planetprofile_export/` or a directory you choose in the GUI

Do not edit generated files in `compositions/` or `outputs/` as the source of truth. Edit or copy models through the GUI instead.

## Current Limitations

- Supported composition fields are `SiO2`, `TiO2`, `Al2O3`, `FeO`, `MgO`, `CaO`, `Na2O`, `K2O`, and `P2O5`.
- The default BUILD template currently passes only `NA2O MGO AL2O3 SIO2 CAO FEO` to Perple_X, so nonzero `TiO2`, `K2O`, and `P2O5` are recorded but omitted from BUILD.
- The default thermodynamic setup uses `stx21ver.dat` and `stx21_solution_model.dat` from your local Perple_X installation.

## Command Line

The GUI calls the same Python scripts that can be run directly:

```bash
python3 run_full_pipeline.py
python3 run_full_pipeline.py --project moon_far_highlands_surface_proxy
python3 run_full_pipeline.py --export-planetprofile
```

## Tests

Tests use fake Perple_X executables, so real Perple_X is not required:

```bash
pip install -r requirements-dev.txt
python3 -m pytest
```
