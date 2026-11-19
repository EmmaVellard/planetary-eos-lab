# 🪐 Planetary EOS Lab

[![Tests](https://github.com/EmmaVellard/planetary-eos-lab/workflows/Tests/badge.svg)](https://github.com/EmmaVellard/planetary-eos-lab/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-b19cd9.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-b19cd9.svg)](https://www.python.org/downloads/)

A laboratory for planetary equation-of-state modeling with Perple_X and PlanetProfile integration.

The included Moon near-side/far-side models are example smoke tests. They are useful for checking the workflow, not publication-ready lunar mantle compositions. For composition provenance and caveats, see [composition.md](composition.md).

## Installation

### Prerequisites
- Python 3.10 or later
- [Perple_X](https://github.com/jadconnolly/Perple_X) installed locally (tested with Perple_X 7.2.5, June 2026)
- Docker (optional, for containerized usage)

### Quick Install

**Option 1: From source**
```bash
git clone https://github.com/EmmaVellard/planetary-eos-lab.git
cd planetary-eos-lab
pip install -e .
planetary-eos-gui
```

**Option 2: Development install**
```bash
git clone https://github.com/EmmaVellard/planetary-eos-lab.git
cd planetary-eos-lab
pip install -e ".[dev]"
pytest  # Run tests
planetary-eos-gui
```

### First-Time Setup

1. **Copy example config**
   ```bash
   cp configs/models.example.json configs/models.json
   ```

2. **Install Perple_X**
   - Download from [jadconnolly/Perple_X](https://github.com/jadconnolly/Perple_X)
   - Note the installation path (contains BUILD, VERTEX, WERAMI executables)

3. **Launch the GUI**
   ```bash
   planetary-eos-gui
   # Or: streamlit run planetary_eos_lab/gui/streamlit_app.py
   ```

4. **Configure Perple_X path**
   - In the GUI: Step 1 → enter your Perple_X directory path → Save
   - Or edit `configs/models.json` and set `"perplex_dir": "/path/to/perplex"`

The app opens in your browser at http://localhost:8501 (it listens on 127.0.0.1 only; `--port` changes the port). Use `configs/models.json` as your local editable config; it is ignored by Git. The published lunar BSM compositions can be added to it from *Composition > Catalog*.

### First Run

```bash
python examples/first_run.py --perplex-dir /path/to/perplex
```

Checks the installation, creates `configs/models.json` from the example if you have none, runs the
first example model on a coarse grid (about 10 s) and prints where the table is.

For your own study without the GUI, copy [examples/my_study.py](examples/my_study.py) and edit its
"YOUR STUDY" block (database, compositions, crust extraction, oxides to drop, P–T range, grid, a P–T
path), then run it: compositions, Perple_X, validation, PlanetProfile export and a profile, in
`outputs/<study name>/`.

### Verify Your Installation

```bash
planetary-eos-selftest --perplex-dir /path/to/perplex
```

It checks Python and the dependencies, the Perple_X executables and version, the data files of every
database, then runs a small stx21 model through BUILD, VERTEX and WERAMI (about 5 s) and compares
density and velocities at three nodes with reference values computed with Perple_X 7.2.5 (1 %
tolerance). Every check prints PASS, WARN or FAIL; the command exits with 1 if one fails. With
`PERPLEX_DIR` set, `pytest` runs the same test.

### Docker Installation (Alternative)

Run in an isolated container:

```bash
# Build image
docker build -t planetary-eos-lab .

# Run with GUI
docker run -p 8501:8501 \
  -v /path/to/perplex:/opt/perplex:ro \
  -v $(pwd)/outputs:/app/outputs \
  planetary-eos-lab

# Or use docker-compose
docker-compose up -d
```

See [DOCKER.md](DOCKER.md) for detailed Docker usage.

## GUI Workflow

The left menu has three main workspaces:

- `Composition`: create a new model in `Composition > Build`, generate sweeps in `Composition > Batch Processing`, review saved models in `Composition > Catalog`, edit oxide values and metadata, preview normalization, and delete saved models from `configs/models.json`.
- `Run Pipeline`: select a saved model, review caveats, generate composition files, run Perple_X, validate outputs, make comparison plots, and export PlanetProfile tables.
- `Compare Models`: inspect interactive comparisons across saved model outputs.

GitHub hosts this workbench only; it does not include BUILD, VERTEX, WERAMI, or Perple_X datafiles.

## What The GUI Writes

- Source model definitions: `configs/models.json`
- Generated composition files: `compositions/`
- Perple_X work/output files: `outputs/<project>/`
- PlanetProfile exports: `outputs/planetprofile_export/` or a directory you choose in the GUI

Do not edit generated files in `compositions/` or `outputs/` as the source of truth. Edit or copy models through the GUI instead.

## Thermodynamic Databases

### Available Databases

**stx21 (default)** - Stixrude & Lithgow-Bertelloni 2021
- Modeled oxides: Na2O, MgO, Al2O3, SiO2, CaO, FeO
- Best for: Silicate mantles, standard compositions
- Database file: `stx21ver.dat`

**stx24** - Stixrude & Lithgow-Bertelloni 2024
- Modeled oxides: Na2O, MgO, Al2O3, SiO2, CaO, FeO, Cr2O3
- FeO is passed to BUILD as the components Fe + O (split by their molar weights in `stx24ver.dat`; iron taken as ferrous), so Perple_X computes the Fe2+/Fe3+ partitioning
- Template range: 0.1-5 GPa, 300-2200 K; no excluded phase
- Database files: `stx24ver.dat`, `stx24_solution_model.dat`
- The template was reconstructed in November 2026; tables rebuilt with it differ from the August 2026 lunar tables on about 5 % of the nodes (median relative difference 1e-5)

**hp636** - Holland & Powell data set v6.36
- Same components, solution models and excluded phases as hp633 (checked with a real BUILD)
- Use it for Ti-bearing compositions; add `"excluded_oxides": ["TiO2"]` to a model for a Ti-free control
- Database file: `hp636ver.dat`

**se15_fes_core** - Saxena & Eriksson (2015) Fe–S data set, for metallic cores
- Components: Fe and S, entered as `components_wt_percent` (e.g. `{"Fe": 95, "S": 5}`)
- Solution models: pyrrhotite `Po(SE)` and Fe–S liquid `FeS_liq`; default range 4–9 GPa, 500–2000 K
  (use `pt_range` for other bodies)
- The same setup as PlanetProfile's `<x>Fe<y>S_core.tab` tables; molten nodes take the properties of
  the Fe–S liquid (Vs = 0 in the liquid)
- Database file: `se15ver.dat`. PlanetProfile reads the exported table with `Planet.Core.coreEOS`
  (see [docs/planetprofile_usage.md](docs/planetprofile_usage.md))
- Checked for Fe-5 wt% S with Perple_X 7.2.5 against PlanetProfile's `95Fe5S_core.tab` (Perple_X
  6.6.6): density and Ks agree to 0.01 % and 0.07 % on average over the grid. Shear differs: the
  liquid (above about 1260 K at 4 GPa and 1120 K at 9 GPa for Fe-5 wt% S) has Gs = 0 here, while the
  6.6.6 table gives it a modulus estimated from a Poisson ratio. The shear moduli of solid Fe (FeBCC,
  FeSIV) are not in the data set either; WERAMI estimates them from a Poisson ratio of 0.35, so Vs and
  Gs of the core are not data. The data set was published for ultra-high pressures (Saxena & Eriksson
  2015, "Thermodynamics of Fe-S at ultra-high pressure"). `phase_modes` shows the liquid fraction.

**hp633** - Holland & Powell 2011 (v6.33)
- Modeled oxides: Na2O, MgO, Al2O3, SiO2, K2O, CaO, TiO2, FeO
- Source-only oxide in the default profile: P2O5
- Default excluded phases: `q`, `crst`, `trd`
- Best for: Compositions requiring TiO2 or K2O
- Database file: `hp633ver.dat`
- Solution model file: `solution_model.dat`

**Your own database**: declare it under `custom_databases` in `configs/models.json`, with its data
files, components and BUILD template; no code change is needed. See
[docs/adding_a_database.md](docs/adding_a_database.md).

### Selecting a Database

**In config file:**
```json
{
  "database": "hp633",
  "perplex_dir": "/path/to/perplex"
}
```

**Via environment variable:**
```bash
export PERPLEX_DATABASE=hp633
planetary-eos-gui
```

**Via CLI flag:**
```bash
planetary-eos-run --database hp633
```

The GUI still lets you record `TiO2`, `K2O`, and `P2O5` because they are common source-composition fields. With the default stx21 profile, all three are source-only. With the default hp633 profile, TiO2 and K2O are passed to BUILD, while P2O5 remains source-only. The hp633 template also excludes `q`, `crst`, and `trd` so the default PlanetProfile-facing seismic table remains finite. Use a custom thermodynamic database, solution model file, and BUILD input before interpreting P-bearing effects.


### Icy-World Component Models

Moon-style models can use `oxides_wt_percent`. Icy-world models can instead use `components_wt_percent` for Perple_X components such as `H2`, `C`, `Mg`, `S2`, `O2`, `N2`, or hydrous components such as `H2O`. The tool writes a generated composition file, renders a BUILD input template, runs BUILD/VERTEX/WERAMI, validates the table, and exports PlanetProfile-ready output. BUILD is required for every run; the pipeline does not copy existing PlanetProfile `.dat` or `.tab` files and does not fall back to prebuilt `.dat` files.

See `configs/icy_worlds.example.json` for first-pass CI, CM, CV, cometary, Ganymede-like, and hydrous CV3 examples.

**📖 For detailed guidance on modeling icy worlds (Europa, Titan, comets, etc.), see [docs/icy_worlds_guide.md](docs/icy_worlds_guide.md)** which covers:
- Database selection guide (when to use dew17_hhph vs dew13_hydrous vs others)
- Component vs oxide compositions
- Example bodies (Europa core, Titan mantle, Enceladus, Comet 67P)
- Composition data sources and references
- Troubleshooting common issues

## Model Options

Options of a model entry in `configs/models.json`, besides the composition and the database:

| Option | Effect |
| --- | --- |
| `mantle_extraction` | `{"crust_oxides_wt_percent": {...}, "crust_mass_fraction": f, "crust_source": "..."}`: the mantle left after extracting the crust, X_mantle = (X_bulk − f·X_crust)/(1 − f), recorded in the composition file. Also in the GUI: *Composition > Build > Derive a mantle by crust extraction*. |
| `excluded_oxides` | oxides removed before normalization (e.g. `["TiO2"]`), recorded in the composition file |
| `pt_range` | `{"pressure_bar": {"min", "max"}, "temperature_k": {"min", "max"}}`, replacing the database range (lunar templates) |
| `phase_modes` | `true` writes `<project>_phase_modes.tab`, the volume % of every phase on the same grid (also `planetary-eos-run --phase-modes`) |
| `perplex_options` | grid resolution (`x_nodes`, `y_nodes`, `grid_levels`, ...) |

`configs/models.example.json` includes a low-temperature example (stx24, 300–900 K, 0.1–1.3 GPa, phase modes).

## Command Line Interface

After installation, all functionality is available via command-line tools:

```bash
# Launch GUI
planetary-eos-gui

# Run full pipeline
planetary-eos-pipeline
planetary-eos-pipeline --project moon_far_highlands_surface_proxy
planetary-eos-pipeline --export-planetprofile

# Generate compositions only
planetary-eos-compositions --config configs/models.json

# Run Perple_X (BUILD/VERTEX/WERAMI)
planetary-eos-run --config configs/models.json --project my_project

# Export PlanetProfile tables
planetary-eos-export --config configs/models.json --planetprofile-export-dir outputs/export

# Generate comparison plots
planetary-eos-plot --config configs/models.json --output-dir outputs/plots

# Check a table: quality, P-T domain, comparison of two tables, resolution convergence
planetary-eos-check-table quality outputs/my_project/my_project_planetprofile_native.tab
planetary-eos-check-table domain my_table.tab --p-bar 10000 40000 --t-k 1200 1600
planetary-eos-check-table compare stx21_table.tab stx24_table.tab
planetary-eos-check-table convergence coarse.tab fine.tab --json

# Check the installation
planetary-eos-selftest --perplex-dir /path/to/perplex
```

## Python Without the GUI

Every step is a Python function: compositions (`make_compositions`), Perple_X runs
(`run_perplex.load_config`, `run_perplex.run_model`), export (`export_planetprofile`) and table
tools (`planetary_eos_lab.analysis`: quality, validity masks, domain checks, properties along a
P–T path, comparisons). [examples/warren_mantle_stx24.py](examples/warren_mantle_stx24.py) goes from
a published bulk composition to a mantle, a stx24 table and a profile in about 6 s on a coarse grid;
[docs/python_api.md](docs/python_api.md) lists the functions.

## Using the Tables in PlanetProfile

See [docs/planetprofile_usage.md](docs/planetprofile_usage.md). Every export writes
`planetprofile_export_manifest.json` with the EoS Lab commit, the Perple_X version, the sha256 of
each table and of its BUILD template, and no local absolute path, so a table can be cited and rebuilt.

Legacy scripts at the repository root (`run_perplex.py`, `make_compositions.py`, etc.) still work for backward compatibility.

## Tests

Tests use fake Perple_X executables, so real Perple_X is not required; the real-Perple_X test
runs only when `PERPLEX_DIR` is set:

```bash
pip install -e ".[dev]"
pytest
PERPLEX_DIR=/path/to/perplex pytest
```

## Future Work

- **Solidus and melt fraction.** The mantle tables are computed without a silicate liquid, so a
  node hotter than the solidus of its composition is not physical (it should contain melt). Planned:
  compute the dry solidus T(P) of each composition with Perple_X and a melt model (for example
  `Melt(JH)`, Jennings & Holland 2015, J. Petrol. 56, 869–892), flag the table nodes above it, and
  report the melt fraction there. Even a small melt fraction lowers Vs strongly and raises tidal
  dissipation, so it matters for seismic and tidal forward models.
- **Fe–S core tables in 3-D.** One core table per composition is supported (database
  `se15_fes_core`); stacking several Fe–S compositions into the `Fe-S_3D_EOS*.mat` file PlanetProfile
  interpolates in wFe would need scipy.

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for:
- Development setup
- Code style guidelines
- Testing requirements
- Pull request process

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Citation

If you use this software in your research, please cite it (see [CITATION.cff](CITATION.cff); GitHub shows it under "Cite this repository"):

```bibtex
@software{planetary_eos_lab,
  author = {Vellard, Emma},
  title = {Planetary EOS Lab: GUI workflow for planetary thermodynamics},
  year = {2026},
  url = {https://github.com/EmmaVellard/planetary-eos-lab}
}
```

## Acknowledgments

- [Perple_X](https://github.com/jadconnolly/Perple_X) by James Connolly
- [PlanetProfile](https://github.com/vancesteven/PlanetProfile) by Steve Vance
- Lunar composition data from published literature (see [composition.md](composition.md))
