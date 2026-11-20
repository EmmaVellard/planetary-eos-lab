# 🪐 Planetary EOS Lab

[![Tests](https://github.com/EmmaVellard/planetary-eos-lab/workflows/Tests/badge.svg)](https://github.com/EmmaVellard/planetary-eos-lab/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-b19cd9.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-b19cd9.svg)](https://www.python.org/downloads/)

Planetary EOS Lab turns a rock or ice composition into the equation-of-state tables a planetary
interior model needs. You give a composition (oxides or elements) and choose a thermodynamic
database; the lab runs [Perple_X](https://www.perplex.ethz.ch) (BUILD, VERTEX, WERAMI), checks the
result, and writes tables of density, seismic velocities, heat capacity, thermal expansion and
elastic moduli over a pressure–temperature grid, in the format
[PlanetProfile](https://github.com/vancesteven/PlanetProfile) reads, with a record of how each table
was made.

Everything can be done from a web interface (GUI) or from Python scripts. Perple_X itself is not
included: you install it separately.

## What it does

- **Compositions**: oxide compositions for rocky mantles, element compositions for icy and
  chondritic bodies, Fe–S compositions for metallic cores; normalization, Mg#, oxides dropped on
  purpose (e.g. a Ti-free control), and the **mantle left after extracting a crust** (mass balance).
  The published lunar bulk compositions (Hauri et al. 2015, Warren 2005) come with the lab.
- **Thermodynamic databases**: stx21, stx24, hp633, hp636, an Fe–S core set and four icy-world sets,
  plus any other Perple_X database you declare (no code change).
- **Perple_X runs**: BUILD, VERTEX and WERAMI driven for you, with a P–T range and grid per model,
  an optional table of the volume of every phase (phase modes), and clear errors when Perple_X fails.
- **Checks**: table quality, validity per node, coverage of the P–T range a model needs, comparison of
  two tables (two databases, two Perple_X versions, two resolutions), properties along a P–T path, and
  an installation self-test against reference values.
- **Export**: tables ready for PlanetProfile, with a manifest giving the code commit, the Perple_X
  version, the database and the sha256 of every table, so a table can be cited and rebuilt.

Typical uses: tables for the mantle of a rocky body from published compositions; comparing
compositions, databases or thermal assumptions; core tables for an Fe–S core; tables for icy-moon
silicates; checking which phases are stable along a profile.

Not covered (yet): melting (solidus and melt fraction), Fe–S core tables in 3-D (composition varying),
and the interior structure itself (mass, moment of inertia, tides), which PlanetProfile and other tools
compute from these tables. See [Limits and future work](#limits-and-future-work).

## Quick start

You need Python 3.10 or later and Perple_X (7.2.13 or later; tested with 7.2.5 and 7.3.3).
[INSTALL.md](INSTALL.md) explains every step, including the problems you may meet on macOS.

```bash
git clone https://github.com/EmmaVellard/planetary-eos-lab.git
cd planetary-eos-lab
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
python examples/first_run.py --perplex-dir /path/to/perplex
planetary-eos-gui
```

`first_run.py` checks the installation, creates your configuration file `configs/models.json`, runs a
first model in about 10 seconds and tells you where its table is. `planetary-eos-gui` starts the
interface: open http://localhost:8501 in your browser.

## Using the interface

The left menu has four workspaces.

| Workspace | What you do there |
| --- | --- |
| **Home** | Start: build a composition, open the catalog, or run Perple_X. |
| **Composition** | *Thermodynamic Models*: what each database contains, and a form to add your own. *Build*: create, copy or edit a composition, or derive a mantle by crust extraction. *Batch Processing*: generate series of compositions. *Catalog*: review saved compositions, import or export them, add the published lunar compositions. |
| **Run Pipeline** | 1. choose the models and their database, template and grid; 2. write the composition files; 3. run Perple_X; 4. validate and export to PlanetProfile. |
| **Compare Models** | Phase diagrams, density and velocity plots, and output ranges of several models side by side. |

The sidebar holds the path of your Perple_X folder and of your configuration file, and the **run
history**: every run started from the interface, with its status, its log and the files it wrote.
The interface listens on your computer only (127.0.0.1); `planetary-eos-gui --port 8502` changes the port.

## Using it without the interface

**A study script.** Copy [examples/my_study.py](examples/my_study.py) and edit its "YOUR STUDY"
block: database, compositions, crust extraction, oxides to drop, P–T range, grid, and a P–T path.
Running it writes the compositions, runs Perple_X, validates and exports the tables, and prints the
properties along your path, all in `outputs/<study name>/`.

**Command-line tools.**

| Command | Does |
| --- | --- |
| `planetary-eos-pipeline --project NAME --export-planetprofile` | compositions, Perple_X, validation and export for one model of `configs/models.json` |
| `planetary-eos-compositions`, `planetary-eos-run`, `planetary-eos-export` | the same steps one at a time (`planetary-eos-run --phase-modes` adds the phase table) |
| `planetary-eos-check-table quality|domain|compare|convergence ...` | check one table, or compare two |
| `planetary-eos-selftest --perplex-dir DIR` | check the installation |
| `planetary-eos-plot` | comparison plots of the configured models |

Every command has `--help`. **Python**: every step is a function;
[docs/python_api.md](docs/python_api.md) lists them and
[examples/warren_mantle_stx24.py](examples/warren_mantle_stx24.py) goes from a published composition
to a mantle table and a profile.

## Databases

| Name | For | Components |
| --- | --- | --- |
| `stx21` (default) | silicate mantles (Stixrude & Lithgow-Bertelloni 2021) | Na2O MgO Al2O3 SiO2 CaO FeO |
| `stx24` | silicate mantles, with Cr and explicit Fe redox, down to 300 K (Stixrude & Lithgow-Bertelloni 2024) | Na2O MgO Al2O3 SiO2 CaO Fe O Cr2O3 |
| `hp633`, `hp636` | silicate mantles with Ti and K (Holland & Powell 2011, data sets 6.33 and 6.36) | SiO2 TiO2 Al2O3 Cr2O3 FeO MnO NiO MgO CaO Na2O K2O H2O |
| `se15_fes_core` | Fe–S metallic cores (Saxena & Eriksson 2015); checked between 4 and 9 GPa only | Fe S |
| `dew17_hhph`, `dew13_hydrous`, `hpha02_hydrous`, `dew17_comet` | icy-world and chondritic interiors | elements or hydrous oxides |

Oxides a database does not model are kept in the composition file and reported as left out. Details,
caveats (the stx24 correction of Perple_X 7.2.13, the limits of the Fe–S set) and the icy-world sets:
[docs/databases.md](docs/databases.md) and [docs/icy_worlds_guide.md](docs/icy_worlds_guide.md). To add
a database: [docs/adding_a_database.md](docs/adding_a_database.md), or the form in *Composition >
Thermodynamic Models*.

## Configuration

Your models live in `configs/models.json` (created from `configs/models.example.json`; Git ignores
it). Each model has a `project` name, a composition (`oxides_wt_percent` or
`components_wt_percent`), a `database`, and optional settings:

| Setting | Effect |
| --- | --- |
| `mantle_extraction` | `{"crust_oxides_wt_percent": {...}, "crust_mass_fraction": f, "crust_source": "..."}`: the mantle left after extracting a crust, X_mantle = (X_bulk − f·X_crust)/(1 − f) |
| `excluded_oxides` | oxides removed before normalization, e.g. `["TiO2"]` |
| `pt_range` | `{"pressure_bar": {"min": ..., "max": ...}, "temperature_k": {"min": ..., "max": ...}}` instead of the database range |
| `phase_modes` | `true`: also write the volume % of every phase on the same grid |
| `perplex_options` | grid resolution (`x_nodes`, `y_nodes`, `grid_levels`, ...) |

`models.example.json` shows a surface composition, a low-temperature stx24 run with phase modes, and
an Fe–S core. Every choice is written into the composition file and the export manifest.

## What is written where

| Folder | Content |
| --- | --- |
| `compositions/` | one composition file per model: raw and normalized values, provenance, what BUILD receives |
| `outputs/<project>/` | the tables (`<project>_planetprofile_native.tab` for PlanetProfile, the raw WERAMI table, the phase table), the Perple_X logs, the validation report; Perple_X's own files in `work/` |
| `outputs/planetprofile_export/` | the exported tables and `planetprofile_export_manifest.json` |
| `outputs/streamlit_runs/` | logs of the runs started from the interface |

To use a table in PlanetProfile, see [docs/planetprofile_usage.md](docs/planetprofile_usage.md).

## Checking results

- `planetary-eos-selftest` runs a small model with your Perple_X and compares it with reference values.
- Each run is validated (missing columns, non-finite or negative values); a Perple_X program waiting for
  an answer it never gets is stopped, and the error shows its last question.
- `planetary-eos-check-table` gives the grid, the counts of missing values and the ranges of a table, and
  compares two tables node by node.
- `pytest` runs the test suite with stand-in Perple_X programs; with `PERPLEX_DIR=/path/to/perplex` it
  also runs a real model.

## Limits and future work

- **No melting.** The mantle tables contain no silicate liquid, so nodes hotter than the solidus of the
  composition are not physical. Planned: the dry solidus of each composition with Perple_X and a melt
  model (for example `Melt(JH)`, Jennings & Holland 2015, J. Petrol. 56, 869–892), the nodes above it
  flagged, and the melt fraction reported.
- **Fe–S cores** are checked between 4 and 9 GPa only; the shear modulus of solid Fe comes from a
  Poisson ratio, not data; one table per composition (no 3-D table interpolated in composition yet).
- The included lunar surface compositions are examples for testing the workflow, not mantle
  compositions; see [composition.md](composition.md).

## Documentation

| File | Content |
| --- | --- |
| [INSTALL.md](INSTALL.md) | installation, step by step, and common problems |
| [docs/databases.md](docs/databases.md) | the databases in detail |
| [docs/adding_a_database.md](docs/adding_a_database.md) | adding a Perple_X database |
| [docs/icy_worlds_guide.md](docs/icy_worlds_guide.md) | icy worlds and element compositions |
| [docs/python_api.md](docs/python_api.md) | using the lab from Python |
| [docs/planetprofile_usage.md](docs/planetprofile_usage.md) | using the tables in PlanetProfile |
| [composition.md](composition.md) | the example lunar compositions |
| [DOCKER.md](DOCKER.md) | running in a container |
| [CONTRIBUTING.md](CONTRIBUTING.md), [CHANGELOG.md](CHANGELOG.md) | contributing, version history |

## Citation

If you use Planetary EOS Lab in your research, please cite it. GitHub shows the reference under
"Cite this repository" ([CITATION.cff](CITATION.cff)); in BibTeX:

```bibtex
@software{planetary_eos_lab,
  author  = {Vellard, Emma},
  title   = {Planetary EOS Lab: a Perple_X workbench for planetary interior equations of state},
  year    = {2026},
  url     = {https://github.com/EmmaVellard/planetary-eos-lab}
}
```

Please also cite Perple_X (Connolly 2005, Earth Planet. Sci. Lett. 236, 524–541; Connolly 2009,
Geochem. Geophys. Geosyst. 10, Q10014) and the thermodynamic database you used. To make a table
reproducible, give the EoS Lab commit and the Perple_X version recorded in its export manifest.

## License and acknowledgments

MIT License, see [LICENSE](LICENSE).
[Perple_X](https://github.com/jadconnolly/Perple_X) is by James Connolly;
[PlanetProfile](https://github.com/vancesteven/PlanetProfile) by Steve Vance and collaborators.
Lunar compositions are from the published literature listed in [composition.md](composition.md) and
`configs/lunar_bsm_models.json`.
