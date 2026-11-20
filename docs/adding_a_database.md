# Adding a thermodynamic database

Planetary EOS Lab ships with stx21, stx24, hp633, hp636 and four icy-world setups. Any other
Perple_X database can be added from `configs/models.json`, without editing the code.

## How a database works here

A database is four things: a Perple_X thermodynamic data file (`*ver.dat`), the solution models
chosen in it, a BUILD template that answers BUILD's questions (data file, components, P–T range,
excluded phases, solution models), and the answers given to WERAMI to tabulate the properties. The
pipeline fills the template with your composition, runs BUILD, VERTEX and WERAMI, and validates the
table. Built-in databases are defined in `planetary_eos_lab/core/config.py`; yours are declared in the
config, either with the GUI form (*Composition > Thermodynamic Models > Add or edit a database*) or by
hand as below.

## 1. Write a BUILD template

Copy the closest template in `build_inputs/` (for example `lunar_hp633_template.build.in`) and
edit it to answer BUILD's prompts for your database: data file, component list (in the order
BUILD will read the bulk values), P–T range, excluded phases, solution model file and models.
Placeholders filled by the pipeline:

| Placeholder | Value |
| --- | --- |
| `${PROJECT}` | project name |
| `${PERPLEX_DIR}` | Perple_X folder (use `${PERPLEX_DIR}/datafiles/<file>`) |
| `${PERPLEX_BULK_VALUES}` | bulk composition, in the order of `components` below |
| `${BUILD_TITLE}` | composition description |
| `${P_RANGE_BAR}`, `${T_RANGE_K}` | P and T range from `pt_range` (database or model) |
| `${THERMODYNAMIC_DATABASE_FILE}`, `${SOLUTION_MODEL_FILE}` | full paths to the data files |

The fastest way to get the prompt order right is to run BUILD once by hand with your database
and copy your answers line by line.

## 2. Declare the database in the config

```json
{
  "perplex_dir": "/path/to/perplex",
  "custom_databases": [
    {
      "name": "hp62_mantle",
      "database_file": "hp62ver.dat",
      "solution_model_file": "solution_model.dat",
      "components": [["Na2O", "NA2O"], ["MgO", "MGO"], ["Al2O3", "AL2O3"],
                     ["SiO2", "SIO2"], ["CaO", "CAO"], ["FeO", "FEO"]],
      "build_template": "build_inputs/my_hp62_template.build.in",
      "solution_models": ["O(JH)", "Opx(JH)", "Cpx(JH)", "Gt(JH)", "Sp(JH)", "Pl(JH)"],
      "excluded_phases": [],
      "pt_range": {"pressure_bar": {"min": 1000, "max": 50000},
                   "temperature_k": {"min": 800, "max": 2200}},
      "werami_input_sequence": ["2", "38", "1", "2", "13", "14", "3", "4", "10", "11", "0", "n", "1", "0"],
      "description": "Holland & Powell ds62 with the Jennings & Holland (2015) models"
    }
  ],
  "models": [{"project": "my_mantle", "database": "hp62_mantle"}]
}
```

- `components`: `[source oxide, Perple_X component]` pairs, in BUILD order. Source oxides not
  listed are kept in the composition file as source-only and reported as omitted.
  An oxide may feed two components: `["FeO", "Fe"], ["FeO", "O"]` splits FeO by the Fe and O
  molar weights (iron taken as ferrous), as stx24 does.
- `werami_input_sequence` (optional): WERAMI's answers after the project name. Without it, the
  stx21 sequence is used (properties 2, 13, 14, 3, 4, 10, 11: ρ, Vp, Vs, Cp, α, Ks, Gs). Some
  databases ask one more question (hp633 answers `n` to a prompt); check by running WERAMI by hand.
- `name` must not be the name of a built-in database.

The database then appears in the GUI (Thermodynamic Setup), in every command-line tool
(`--database hp62_mantle`) and in Python (`run_perplex.load_config`).

## 3. Check it

```bash
planetary-eos-run --config configs/models.json --project my_mantle
planetary-eos-check-table quality outputs/my_mantle/my_mantle_planetprofile_native.tab
```

Look at `outputs/my_mantle/build.log` and `werami.log` the first time. If the template or the WERAMI
answers do not match the prompts, Perple_X waits for an answer that never comes: the pipeline stops
it (after 300 s for BUILD, 1800 s for WERAMI; `PLANETARY_EOS_PERPLEX_TIMEOUT` sets another limit in
seconds) and the error message shows the last question it asked. A WERAMI table with a single node
along an axis is also rejected. Check the result with `planetary-eos-check-table quality`, and
compare it with a table you trust with `planetary-eos-check-table compare`.
