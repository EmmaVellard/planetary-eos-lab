# Lunar Perple_X Workbench

This repository is a local Perple_X workbench and PlanetProfile EOS table export helper. It automates composition-file generation, Perple_X BUILD/VERTEX/WERAMI runs, validation, plotting, and PlanetProfile-format export.

The included lunar cases are first-pass near-side/far-side surface or terrane proxies. They are useful for testing the mechanics of the workflow and for early contrast experiments, but they are not final lunar mantle compositions and should not be presented as publication-ready Moon mantle EOS tables.

For the current composition numbers and caveats, see [composition.md](composition.md).

The target PlanetProfile-facing table columns are:

```text
T(K), P(bar), rho_kgm3, VP_kms, VS_kms, Cp_Jm3K, alpha_pK, KS_bar, GS_bar
```

## GitHub Quick Start

The repository can be cloned and run directly, but the full Perple_X steps are local: GitHub does not provide the BUILD, VERTEX, WERAMI executables or Perple_X datafiles.

```bash
git clone https://github.com/EmmaVellard/perplex-workbench.git
cd perplex-workbench
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp configs/models.example.json configs/models.json
streamlit run perplex_workbench/gui/streamlit_app.py
```

In the GUI, set the Perple_X directory to your local installation before running Perple_X. The included default config uses portable placeholders, so users should not need Emma-specific paths.

## Current Scientific Status

The included model identifiers are deliberately conservative:

- `moon_far_highlands_surface_proxy`: farside/highlands-like surface proxy.
- `moon_near_maria_surface_proxy`: nearside/maria-like surface proxy.

The far-side/highlands case uses a commonly tabulated highlands surface average: SiO2 45.5, Al2O3 24.0, CaO 15.9, FeO 5.9, MgO 7.5, TiO2 0.6, and Na2O 0.6 wt%. The near-side/maria case uses a commonly tabulated maria surface average: SiO2 45.4, Al2O3 14.9, CaO 11.8, FeO 14.1, MgO 9.2, TiO2 3.9, and Na2O 0.6 wt%. These values capture the expected surface contrast that maria are richer in Fe and Ti, while highlands are richer in Al and Ca.

Important caveat: in the default `stx21` BUILD setup, `TiO2` is not part of the active Perple_X component list. The pipeline records TiO2 in the composition JSON and export manifest, but it is omitted from BUILD. This weakens any near-side versus far-side interpretation that depends on Ti-rich mare mineralogy.

Reference trail for these first-pass choices:

- [Lunar surface chemical composition table](https://en.wikipedia.org/wiki/Geology_of_the_Moon#Elemental_composition), which reproduces common maria/highlands oxide averages and cites Taylor and Papike lunar petrology references.
- [Lu et al. (2020), Seamless maps of major elements of the Moon](https://arxiv.org/abs/2007.15858), for the mapped contrast between mare and highland major-element abundances.
- [Sossi et al. (2024), Composition, Structure and Origin of the Moon](https://arxiv.org/abs/2408.16840), for broader bulk silicate Moon and lunar mantle composition context.

Do not add native Fe, Ni, or Cu unless you are intentionally modeling metallic phases and have verified elastic properties for every relevant phase. Invalid or missing elastic properties can produce bad seismic columns while still allowing Perple_X to write a table.

KREEP, Th, U, and K effects should mostly be represented through PlanetProfile thermal and radiogenic parameters. Oxide composition alone is not a complete treatment of near-side radiogenic structure.

## Scientific Readiness Levels

- `smoke_test`: useful to test pipeline mechanics only.
- `surface_proxy`: useful for terrane contrast experiments, not mantle EOS interpretation.
- `mantle_candidate`: candidate mantle composition requiring scientific review of composition, database, solution models, phase exclusions, P-T grid, and validation outputs.
- `publication_ready`: reviewed composition, thermodynamic file choice, solution model list, P-T grid, Perple_X logs, validation reports, and PlanetProfile integration.

The current included models are `surface_proxy_smoke_test`, with `planetprofile_readiness` set to `mechanically_exportable_not_scientifically_final`.

## What Is Automated

- Writes normalized near-side and far-side surface proxy oxide compositions.
- Writes reproducible `perplex_option.dat` into each model's repo-local work directory.
- Runs BUILD in the model work directory when a configured build input file exists.
- Requires an existing `<project>.dat` in the model work directory when BUILD input is absent.
- Runs VERTEX.
- Runs WERAMI for system properties on a 2D grid using property 38.
- Copies `<work_dir>/<project>_1.tab` to `outputs/<project>/<project>_raw_werami.tab`.
- Writes `outputs/<project>/<project>_planetprofile.tab` with temperature before pressure.
- Writes `outputs/<project>/<project>_planetprofile_native.tab` in the native Perple_X/PlanetProfile table layout.
- Saves `build.log`, `vertex.log`, and `werami.log`.
- Warns when nonzero oxides in the composition JSON are omitted from the active Perple_X BUILD component list.
- Writes local comparison SVG plots under `outputs/comparisons/`.
- Exports PlanetProfile-format `.tab` files plus a provenance manifest to a chosen directory when requested.
- Writes `validation_report.txt`.
- Exits nonzero when validation fails.

## What Is Not Automated

- Choosing publication-quality lunar mantle compositions.
- Auditing each BUILD prompt for thermodynamic database and solution model choices.
- Deciding whether Perple_X solution models are appropriate for the scientific question.
- Confirming final PlanetProfile thermal, radiogenic, and grid assumptions.

BUILD should still be checked manually because a syntactically valid `.dat` file can encode the wrong database, components, solution model choices, saturation assumptions, or variable ranges.

## Files

```text
configs/models.example.json
build_inputs/lunar_stx21_template.build.in
run_full_pipeline.py
make_compositions.py
run_perplex.py
validate_tab.py
plot_comparisons.py
planetprofile_tables.py
export_planetprofile.py
composition.md
requirements.txt
requirements-dev.txt
compositions/
build_inputs/
outputs/
tests/
```

Copy `configs/models.example.json` to `configs/models.json` and set `perplex_dir` to your local Perple_X install. `configs/models.json` is ignored because it is machine-local. The Perple_X install is treated as an external executable dependency; generated files are written under this repository, using `outputs/<project>/work` by default.

For normal use, `configs/models.json` is the only source file you need to edit. Each model block contains the project name, scientific metadata, the optional PlanetProfile export filename, and the oxide composition. `compositions/` is generated from this config and should not be treated as the source of truth.

```json
{
  "project": "moon_far_highlands_surface_proxy",
  "planetprofile_filename": "Moon_Far_Highlands_proxy_PerpleX.tab",
  "scientific_status": "surface_proxy_smoke_test",
  "model_scope": "surface_terrane_proxy",
  "planetprofile_readiness": "mechanically_exportable_not_scientifically_final",
  "composition_interpretation": "Average highlands-like lunar surface oxide composition used to test a terrane contrast; not a final lunar mantle EOS composition.",
  "oxides_wt_percent": {
    "SiO2": 45.5,
    "TiO2": 0.6,
    "Al2O3": 24.0,
    "FeO": 5.9,
    "MgO": 7.5,
    "CaO": 15.9,
    "Na2O": 0.6,
    "K2O": 0.0,
    "P2O5": 0.0
  }
}
```

The pipeline turns these inline model definitions into `compositions/<project>.json`, renders the generic BUILD transcript, runs Perple_X, validates the generated table, and optionally exports a PlanetProfile-format `.tab` file.

Advanced overrides are still supported. A model can set `composition_file`, `build_input_file`, `output_dir`, or `work_dir` if it needs custom files or non-default directories. If those fields are omitted, the pipeline uses the inline oxides, `build_inputs/lunar_stx21_template.build.in`, and `outputs/<project>/`.

The included BUILD template uses `stx21ver.dat` and `stx21_solution_model.dat` from the configured Perple_X install. It uses `${PERPLEX_DIR}` placeholders, which the runner replaces from `configs/models.json` at runtime. It also uses `${PERPLEX_BULK_VALUES}`, which the runner expands from each composition JSON in the Perple_X component order `NA2O MGO AL2O3 SIO2 CAO FEO`. That Stixrude 2021 setup supports the active components `NA2O`, `MGO`, `AL2O3`, `SIO2`, `CAO`, and `FEO` in the current template, so `TiO2`, `K2O`, and `P2O5` are retained in the composition record but are not passed to BUILD.

When a composition contains a nonzero oxide that is not passed to BUILD, the runner prints a warning, writes `outputs/<project>/oxide_omissions.txt`, records the omission in the generated composition JSON, and includes it in the PlanetProfile export manifest.

The BUILD template currently excludes pure `qtz` because this database can produce invalid quartz seismic properties for the highlands-like proxy over the smoke-test P-T grid. This is a numerical/modeling guard for the current smoke-test setup, not a final scientific statement about lunar crust or mantle mineralogy. Revisit it before any publication-quality crustal, mantle, or mantle-crust equilibrium model.

Default BUILD template assumptions recorded in provenance:

- thermodynamic database: `stx21ver.dat`
- solution model file: `stx21_solution_model.dat`
- active components: `NA2O MGO AL2O3 SIO2 CAO FEO`
- pressure range: `1000` to `50000` bar
- temperature range: `800` to `2200` K
- excluded phase: `qtz`
- solution models: `O`, `Opx`, `Cpx`, `Gt`, `Sp`, `Pl`, `C2/c`, `NaAl`

These assumptions are suitable for current smoke-test mechanics only. A scientific model should revisit the database, component set, Ti-bearing phases, solution models, phase exclusions, and P-T grid.

## Streamlit GUI

Launch from the repository root after installing `requirements.txt`:

```bash
streamlit run perplex_workbench/gui/streamlit_app.py
```

The GUI has two main workspaces:

- `Build Composition`: create a model, copy an existing model, edit oxides/metadata, preview normalized composition, and delete saved models from `configs/models.json` with a confirmation popup.
- `Run Pipeline`: select a saved model, review caveats, generate composition files, run BUILD/VERTEX/WERAMI, validate outputs, plot comparisons, and export PlanetProfile tables.

The first GUI version only supports the oxide set used by the current source schema: `SiO2`, `TiO2`, `Al2O3`, `FeO`, `MgO`, `CaO`, `Na2O`, `K2O`, and `P2O5`. Other elements/components require extending the schema and BUILD template first.

The GUI cannot make the current models scientifically final. Perple_X must still be installed locally, generated files in `compositions/` should not be edited manually, and the included lunar models remain surface-proxy smoke tests.

## Run Full Pipeline

Run the whole pipeline from this directory:

```bash
python3 run_full_pipeline.py
```

This is the recommended entry point. It reads `configs/models.json`, regenerates the configured compositions, renders BUILD input from the template, runs BUILD/VERTEX/WERAMI, writes PlanetProfile-facing tables, validates the outputs, and writes comparison plots.

To run one project:

```bash
python3 run_full_pipeline.py --project moon_far_highlands_surface_proxy
```

The default full run writes:

```text
outputs/comparisons/composition_oxides.svg
outputs/comparisons/planetprofile_properties.svg
```

Small tracked examples live under `outputs/examples/`; local reruns write to `outputs/<project>/` and `outputs/comparisons/`.

To debug Perple_X without regenerating compositions:

```bash
python3 run_full_pipeline.py --skip-compositions
```

To skip comparison plots:

```bash
python3 run_full_pipeline.py --skip-plots
```

To generate, validate, and export PlanetProfile-format EOS files into this repository:

```bash
python3 run_full_pipeline.py --export-planetprofile
```

This writes export copies and a manifest under:

```text
outputs/planetprofile_export/
```

The export manifest is machine-readable JSON and includes each table's project name, exported filename, source native table, scientific status, model scope, composition interpretation, active Perple_X components, omitted oxides, BUILD template, Perple_X directory, database file, solution model file, P-T range, excluded phases, WERAMI sequence, and a warning that export success does not imply scientific readiness.

To export directly to a PlanetProfile checkout, pass the target EOS table directory explicitly:

```bash
python3 run_full_pipeline.py \
  --export-planetprofile \
  --planetprofile-export-dir /path/to/PlanetProfile/PlanetProfile/Thermodynamics/EOStables/Perple_X
```

Then set the relevant PlanetProfile config field, for example `Planet.Sil.mantleEOS`, to the exported filename.

## Add A New Model

For a new composition, add one block to `configs/models.json` under `models`:

```json
{
  "project": "moon_custom_model",
  "description": "Short scientific description",
  "planetprofile_filename": "Moon_Custom_Model_PerpleX.tab",
  "scientific_status": "surface_proxy",
  "model_scope": "surface_terrane_proxy",
  "planetprofile_readiness": "mechanically_exportable_not_scientifically_final",
  "composition_interpretation": "State what this composition represents, what it does not represent, and whether omitted oxides affect the interpretation.",
  "literature_proxy": true,
  "source_note": "Where these numbers came from and what they represent.",
  "oxides_wt_percent": {
    "SiO2": 45.0,
    "TiO2": 1.0,
    "Al2O3": 18.0,
    "FeO": 10.0,
    "MgO": 12.0,
    "CaO": 13.0,
    "Na2O": 1.0,
    "K2O": 0.0,
    "P2O5": 0.0
  }
}
```

Then run only that model:

```bash
python3 run_full_pipeline.py --project moon_custom_model --export-planetprofile
```

The oxide values do not need to add to exactly 100; the composition generator normalizes them and records both the raw and normalized values. If you include oxides that are not in the active BUILD component list, such as `TiO2`, the pipeline keeps them in the composition record and prints an omission warning when they are not passed to Perple_X.

## Generate Compositions

Run from this directory:

```bash
python3 make_compositions.py
```

This reads `configs/models.json` and writes one composition set per configured model, for example:

```text
compositions/moon_far_highlands_surface_proxy.json
compositions/moon_far_highlands_surface_proxy_bulk_values.txt
compositions/moon_far_highlands_surface_proxy_summary.txt
compositions/moon_near_maria_surface_proxy.json
compositions/moon_near_maria_surface_proxy_bulk_values.txt
compositions/moon_near_maria_surface_proxy_summary.txt
```

The human-readable bulk values are ordered as:

```text
SiO2, TiO2, Al2O3, FeO, MgO, CaO, Na2O, K2O, P2O5
```

## Run Perple_X

Run from this directory:

```bash
python3 run_perplex.py
```

To run one project:

```bash
python3 run_perplex.py --project moon_far_highlands_surface_proxy
```

By default, the runner renders `build_inputs/lunar_stx21_template.build.in` for each configured model and feeds the rendered transcript to BUILD from the repo-local model work directory. If a model sets a custom `build_input_file`, that file is rendered instead. If no BUILD input is available, `<project>.dat` must already exist in that work directory.

BUILD input files may use these portable placeholders:

```text
${PERPLEX_DIR}
${PROJECT}
${COMPOSITION_FILE}
${OUTPUT_DIR}
${WORK_DIR}
${PERPLEX_BULK_VALUES}
${BUILD_TITLE}
```

The default `perplex_option.dat` written by the runner is intentionally a smoke-test grid:

```text
grid_levels 1 1
x_nodes 20 40
y_nodes 20 40
```

Increase these values only after the pipeline passes validation, because high auto-refine grids can make VERTEX much slower.

WERAMI is called with:

```text
project name
2
38
1
2
13
14
3
4
10
11
0
n
1
0
```

This sequence is stored as the default `DEFAULT_WERAMI_INPUT_SEQUENCE` in `run_perplex.py`. A model can override it with a `werami_input_sequence` list in `configs/models.json`, but the default behavior remains unchanged.

## Plot Comparisons

After valid PlanetProfile tables exist, regenerate the comparison SVGs directly with:

```bash
python3 plot_comparisons.py
```

This writes `composition_oxides.svg` and `planetprofile_properties.svg` under `outputs/comparisons/` by default. The property plot compares pressure profiles averaged over the sampled temperature grid.

## Recreate PlanetProfile Table Format

PlanetProfile's existing Perple_X EOS tables use the native WERAMI-style header, for example:

```text
|6.6.6
example_1.tab
           2
T(K)
...
P(bar)
...
           9
T(K) P(bar) rho,kg/m3 vp,km/s ...
```

The pipeline now writes that format automatically as:

```text
outputs/<project>/<project>_planetprofile_native.tab
```

You can also convert any generated WERAMI table directly:

```bash
python3 planetprofile_tables.py convert \
  --input outputs/moon_far_highlands_surface_proxy/moon_far_highlands_surface_proxy_raw_werami.tab \
  --output outputs/moon_far_highlands_surface_proxy/moon_far_highlands_surface_proxy_planetprofile_native.tab \
  --source-name moon_far_highlands_surface_proxy_1.tab
```

## Export Existing Outputs

If the pipeline has already been run, export the validated native tables without rerunning Perple_X:

```bash
python3 export_planetprofile.py
```

or for a specific project and destination:

```bash
python3 export_planetprofile.py \
  --project moon_far_highlands_surface_proxy \
  --planetprofile-export-dir /path/to/PlanetProfile/PlanetProfile/Thermodynamics/EOStables/Perple_X
```

## Validate Outputs

Validation runs automatically at the end of `run_perplex.py`. You can also run it directly:

```bash
python3 validate_tab.py
```

Or for one project:

```bash
python3 validate_tab.py --project moon_far_highlands_surface_proxy
```

Validation fails on:

- `Reading solution models from file: not requested`
- `warning ver177`
- `cannot be computed because of missing/invalid properties`
- `0.100000E+100` or `-0.100000E+100`
- missing `.tab` output
- missing required columns
- NaN-only columns
- zero-only `alpha_pK`
- negative density, Vp, Vs, bulk modulus, or shear modulus

A run can have technical success and readiness failure at the same time. Technical success means Perple_X ran and wrote a `.tab` file. Readiness success means the logs and PlanetProfile-facing table pass validation checks.

## Run Tests

The tests do not require real Perple_X. They build fake BUILD, VERTEX, and WERAMI executables in temporary directories.

Run from this directory:

```bash
python3 -m pytest
```

The tests cover successful fake execution plus missing `.dat`, missing executable, missing `.tab`, log warning, bad-number sentinel, and zero-alpha failures.
