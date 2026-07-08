from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from planetary_eos_lab.core.config import DATABASES
from planetary_eos_lab.core.database_utils import get_database_components, get_source_only_oxides
from planetprofile_tables import write_planetprofile_native_table
from validate_tab import column_indices, read_tab, validate_project_output


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG = BASE_DIR / "configs" / "models.json"
DEFAULT_DATABASE = "stx21"
DEFAULT_BUILD_TEMPLATE = BASE_DIR / "build_inputs" / "lunar_stx21_template.build.in"
DEFAULT_BUILD_TEMPLATES = {
    "stx21": DEFAULT_BUILD_TEMPLATE,
    "hp633": BASE_DIR / "build_inputs" / "lunar_hp633_template.build.in",
    "dew17_hhph": BASE_DIR / "build_inputs" / "icy_dew17_hhph_template.build.in",
    "hpha02_hydrous": BASE_DIR / "build_inputs" / "icy_hpha02_hydrous_simple_template.build.in",
    "dew13_hydrous": BASE_DIR / "build_inputs" / "icy_dew13_hydrous_template.build.in",
    "dew17_comet": BASE_DIR / "build_inputs" / "icy_dew17_comet_template.build.in",
}
COMPONENT_COMPOSITION_BASIS = "perplex_components"
COMPONENT_COMPOSITION_ALIASES = {"perplex_components", "components", "elements", "element_components"}

@dataclass(frozen=True)
class PerplexOptions:
    sample_on_grid: bool = False
    x_nodes: tuple[int, int] = (40, 300)
    y_nodes: tuple[int, int] = (40, 300)
    grid_levels: tuple[int, int] = (1, 4)
    auto_refine: str = "auto"
    final_resolution: tuple[str, str] = ("2.5e-4", "2.5e-4")


DEFAULT_PERPLEX_OPTIONS = PerplexOptions()


def effective_perplex_options(options: PerplexOptions = DEFAULT_PERPLEX_OPTIONS) -> PerplexOptions:
    if not options.sample_on_grid:
        return options
    return PerplexOptions(
        sample_on_grid=options.sample_on_grid,
        x_nodes=options.x_nodes,
        y_nodes=options.y_nodes,
        grid_levels=(1, 1),
        auto_refine=options.auto_refine,
        final_resolution=options.final_resolution,
    )


def render_perplex_option_text(options: PerplexOptions = DEFAULT_PERPLEX_OPTIONS) -> str:
    options = effective_perplex_options(options)
    sample_on_grid = "T" if options.sample_on_grid else "F"
    return f"""\
warn_interactive F
pause_on_error F
spreadsheet T
sample_on_grid {sample_on_grid}
seismic_data_file T
bad_number NaN
grid_levels {options.grid_levels[0]} {options.grid_levels[1]}
x_nodes {options.x_nodes[0]} {options.x_nodes[1]}
y_nodes {options.y_nodes[0]} {options.y_nodes[1]}
auto_refine {options.auto_refine}
final_resolution {options.final_resolution[0]} {options.final_resolution[1]}
"""


PERPLEX_OPTION_TEXT = render_perplex_option_text(DEFAULT_PERPLEX_OPTIONS)

DEFAULT_WERAMI_INPUT_SEQUENCE = (
    "2",
    "38",
    "1",
    "2",
    "13",
    "14",
    "3",
    "4",
    "10",
    "11",
    "0",
    "n",
    "1",
    "0",
)
HP633_WERAMI_INPUT_SEQUENCE = (
    "2",
    "38",
    "1",
    "n",
    "2",
    "13",
    "14",
    "3",
    "4",
    "10",
    "11",
    "0",
    "n",
    "1",
    "0",
)
DEFAULT_WERAMI_INPUT_SEQUENCES = {
    "stx21": DEFAULT_WERAMI_INPUT_SEQUENCE,
    "hp633": HP633_WERAMI_INPUT_SEQUENCE,
    "dew17_hhph": HP633_WERAMI_INPUT_SEQUENCE,
    "hpha02_hydrous": HP633_WERAMI_INPUT_SEQUENCE,
    "dew13_hydrous": HP633_WERAMI_INPUT_SEQUENCE,
    "dew17_comet": HP633_WERAMI_INPUT_SEQUENCE,
}
WERAMI_INPUT_DESCRIPTION = {
    "mode": "2D grid table",
    "property": "38 system properties",
    "requested_columns": ["P(bar)", "T(K)", "rho", "Vp", "Vs", "Cp", "alpha", "Ks", "Gs"],
    "note": (
        "Default prompt sequences are database-specific when Perple_X asks extra prompts. "
        "They can be overridden per model with werami_input_sequence."
    ),
}

PLANETPROFILE_COLUMNS = (
    ("t_k", "T(K)"),
    ("p_bar", "P(bar)"),
    ("rho_kgm3", "rho_kgm3"),
    ("vp_kms", "VP_kms"),
    ("vs_kms", "VS_kms"),
    ("cp_jm3k", "Cp_Jm3K"),
    ("alpha_pk", "alpha_pK"),
    ("ks_bar", "KS_bar"),
    ("gs_bar", "GS_bar"),
)

PERPLEX_COMPONENTS = (
    ("Na2O", "NA2O"),
    ("MgO", "MGO"),
    ("Al2O3", "AL2O3"),
    ("SiO2", "SIO2"),
    ("CaO", "CAO"),
    ("FeO", "FEO"),
)
ACTIVE_COMPOSITION_OXIDES = {oxide for oxide, _ in PERPLEX_COMPONENTS}
OXIDE_COMPONENT_NAMES = {
    "Na2O": "NA2O",
    "MgO": "MGO",
    "Al2O3": "AL2O3",
    "SiO2": "SIO2",
    "CaO": "CAO",
    "FeO": "FEO",
    "TiO2": "TIO2",
    "K2O": "K2O",
    "P2O5": "P2O5",
}
OMITTED_OXIDE_THRESHOLD = 1.0e-12
DEFAULT_BUILD_DATABASE_FILE = "stx21ver.dat"
DEFAULT_BUILD_SOLUTION_MODEL_FILE = "stx21_solution_model.dat"
DEFAULT_BUILD_PT_RANGE = {
    "pressure_bar": {"min": 1000.0, "max": 50000.0},
    "temperature_k": {"min": 800.0, "max": 2200.0},
}
DEFAULT_BUILD_EXCLUDED_PHASES = ("qtz",)
DEFAULT_BUILD_SOLUTION_MODELS = ("O", "Opx", "Cpx", "Gt", "Sp", "Pl", "C2/c", "NaAl")


class PipelineError(RuntimeError):
    pass


def resolve_database_name(database: str | None) -> str:
    name = database or DEFAULT_DATABASE
    if name not in DATABASES:
        available = ", ".join(sorted(DATABASES))
        raise ValueError(f"Unknown thermodynamic database '{name}'. Available: {available}")
    return name


def default_build_template_for_database(database: str) -> Path:
    name = resolve_database_name(database)
    try:
        return DEFAULT_BUILD_TEMPLATES[name]
    except KeyError as exc:
        raise ValueError(f"No default BUILD template is configured for database '{name}'.") from exc


def is_stx21_default_template(path: Path) -> bool:
    try:
        return path.resolve() == DEFAULT_BUILD_TEMPLATE.resolve()
    except FileNotFoundError:
        return path == DEFAULT_BUILD_TEMPLATE


@dataclass(frozen=True)
class ModelConfig:
    project: str
    composition_file: Path
    build_input_file: Path
    output_dir: Path
    work_dir: Path
    database: str = DEFAULT_DATABASE
    planetprofile_first_axis: str = "T"
    planetprofile_filename: str | None = None
    scientific_status: str | None = None
    model_scope: str | None = None
    planetprofile_readiness: str | None = None
    composition_interpretation: str | None = None
    werami_input_sequence: tuple[str, ...] = DEFAULT_WERAMI_INPUT_SEQUENCE
    perplex_options: PerplexOptions = DEFAULT_PERPLEX_OPTIONS


@dataclass(frozen=True)
class PipelineConfig:
    perplex_dir: Path
    database: str
    models: list[ModelConfig]


def config_base_dir(config_path: Path) -> Path:
    if config_path.parent.name == "configs":
        return config_path.parent.parent
    return config_path.parent


def resolve_path(value: str | Path, base_dir: Path) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute():
        return path
    return (base_dir / path).resolve()


def planetprofile_first_axis_from_config(model: dict) -> str:
    value = str(model.get("planetprofile_first_axis", "T")).strip().upper()
    if value in {"TEMPERATURE", "T(K)"}:
        value = "T"
    elif value in {"PRESSURE", "P(BAR)"}:
        value = "P"
    if value not in {"T", "P"}:
        raise ValueError("planetprofile_first_axis must be 'T' or 'P'.")
    return value


def is_component_composition_data(data: dict) -> bool:
    basis = str(data.get("composition_basis", "")).strip().lower().replace("-", "_")
    return basis in COMPONENT_COMPOSITION_ALIASES or "component_order" in data


def default_werami_sequence_for_database(database: str) -> tuple[str, ...]:
    return DEFAULT_WERAMI_INPUT_SEQUENCES.get(
        resolve_database_name(database),
        DEFAULT_WERAMI_INPUT_SEQUENCE,
    )


def werami_sequence_from_config(model: dict, database: str = DEFAULT_DATABASE) -> tuple[str, ...]:
    sequence = model.get("werami_input_sequence")
    if sequence is None:
        return default_werami_sequence_for_database(database)
    if not isinstance(sequence, list):
        raise ValueError("werami_input_sequence must be a JSON list of prompt responses.")
    return tuple(str(item) for item in sequence)


def boolean_option_from_config(value: object, *, field_name: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().upper()
        if normalized in {"T", "TRUE", "Y", "YES", "1"}:
            return True
        if normalized in {"F", "FALSE", "N", "NO", "0"}:
            return False
    raise ValueError(f"{field_name} must be True or False; legacy T/F values are also accepted.")


def integer_pair_from_config(value: object, *, field_name: str, minimum: int = 2) -> tuple[int, int]:
    if isinstance(value, str):
        parts = value.replace(",", " ").split()
    elif isinstance(value, (list, tuple)):
        parts = list(value)
    else:
        raise ValueError(f"{field_name} must be a two-item list or string.")
    if len(parts) != 2:
        raise ValueError(f"{field_name} must contain exactly two values.")
    try:
        first, second = int(parts[0]), int(parts[1])
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} values must be integers.") from exc
    if first < minimum or second < minimum:
        raise ValueError(f"{field_name} values must be at least {minimum}.")
    if first > second:
        raise ValueError(f"{field_name} minimum cannot exceed maximum.")
    return first, second


def string_pair_from_config(value: object, *, field_name: str) -> tuple[str, str]:
    if isinstance(value, str):
        parts = value.replace(",", " ").split()
    elif isinstance(value, (list, tuple)):
        parts = [str(item) for item in value]
    else:
        raise ValueError(f"{field_name} must be a two-item list or string.")
    if len(parts) != 2:
        raise ValueError(f"{field_name} must contain exactly two values.")
    return str(parts[0]), str(parts[1])


def perplex_options_from_config(
    value: object,
    fallback: PerplexOptions = DEFAULT_PERPLEX_OPTIONS,
) -> PerplexOptions:
    if value is None:
        return fallback
    if not isinstance(value, dict):
        raise ValueError("perplex_options must be a JSON object.")

    sample_on_grid = fallback.sample_on_grid
    if "sample_on_grid" in value:
        sample_on_grid = boolean_option_from_config(value["sample_on_grid"], field_name="sample_on_grid")

    return PerplexOptions(
        sample_on_grid=sample_on_grid,
        x_nodes=integer_pair_from_config(value.get("x_nodes", list(fallback.x_nodes)), field_name="x_nodes"),
        y_nodes=integer_pair_from_config(value.get("y_nodes", list(fallback.y_nodes)), field_name="y_nodes"),
        grid_levels=integer_pair_from_config(
            value.get("grid_levels", list(fallback.grid_levels)),
            field_name="grid_levels",
            minimum=1,
        ),
        auto_refine=str(value.get("auto_refine", fallback.auto_refine)).strip() or fallback.auto_refine,
        final_resolution=string_pair_from_config(
            value.get("final_resolution", list(fallback.final_resolution)),
            field_name="final_resolution",
        ),
    )


def load_config(
    config_path: Path,
    *,
    database_override: str | None = None,
    perplex_dir_override: str | Path | None = None,
) -> PipelineConfig:
    base_dir = config_base_dir(config_path)
    if not config_path.exists():
        raise FileNotFoundError(
            f"Missing config file: {config_path}. Copy configs/models.example.json to configs/models.json "
            "and set perplex_dir to your local Perple_X install."
        )
    data = json.loads(config_path.read_text(encoding="utf-8"))
    pipeline_database = resolve_database_name(database_override or data.get("database", DEFAULT_DATABASE))
    pipeline_perplex_options = perplex_options_from_config(data.get("perplex_options"))
    configured_build_template = data.get("build_template_file")
    models: list[ModelConfig] = []

    for model in data["models"]:
        project = model["project"]
        model_database = resolve_database_name(model.get("database", pipeline_database))
        planetprofile_first_axis = planetprofile_first_axis_from_config(model)
        model_perplex_options = perplex_options_from_config(
            model.get("perplex_options"),
            fallback=pipeline_perplex_options,
        )
        model_build_template = model.get("build_input_file") or model.get("build_template_file")
        if model_build_template:
            build_input_file = resolve_path(model_build_template, base_dir)
        elif configured_build_template:
            configured_template = resolve_path(configured_build_template, base_dir)
            if model_database != "stx21" and is_stx21_default_template(configured_template):
                build_input_file = default_build_template_for_database(model_database)
            else:
                build_input_file = configured_template
        else:
            build_input_file = default_build_template_for_database(model_database)
        output_dir = resolve_path(model.get("output_dir", f"outputs/{project}"), base_dir)
        work_dir = (
            resolve_path(model["work_dir"], base_dir)
            if "work_dir" in model
            else output_dir / "work"
        )
        models.append(
            ModelConfig(
                project=project,
                composition_file=resolve_path(
                    model.get("composition_file", f"compositions/{project}.json"),
                    base_dir,
                ),
                build_input_file=build_input_file,
                output_dir=output_dir,
                work_dir=work_dir,
                database=model_database,
                planetprofile_first_axis=planetprofile_first_axis,
                planetprofile_filename=model.get("planetprofile_filename"),
                scientific_status=model.get("scientific_status"),
                model_scope=model.get("model_scope"),
                planetprofile_readiness=model.get("planetprofile_readiness"),
                composition_interpretation=model.get("composition_interpretation"),
                werami_input_sequence=werami_sequence_from_config(model, model_database),
                perplex_options=model_perplex_options,
            )
        )

    return PipelineConfig(
        perplex_dir=resolve_path(perplex_dir_override or data["perplex_dir"], base_dir),
        database=pipeline_database,
        models=models,
    )


def executable_path(perplex_dir: Path, name: str) -> Path:
    candidates = [
        perplex_dir / "bin" / name,
        perplex_dir / "bin" / f"{name}.exe",
        perplex_dir / name,
        perplex_dir / f"{name}.exe",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def ensure_executable(path: Path, label: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"Missing {label} executable: {path}")
    if not path.is_file():
        raise FileNotFoundError(f"{label} executable is not a file: {path}")
    if is_python_script(path):
        return
    if os.name != "nt" and not os.access(path, os.X_OK):
        raise PermissionError(f"{label} executable is not executable: {path}")


def is_python_script(path: Path) -> bool:
    try:
        with path.open("rb") as handle:
            first_line = handle.readline(200).decode("utf-8", errors="ignore")
    except OSError:
        return False
    return first_line.startswith("#!") and "python" in first_line.lower()


def executable_command(path: Path) -> list[str]:
    if is_python_script(path):
        return [sys.executable, str(path)]
    return [str(path)]


def write_log(log_path: Path, stdout: str, stderr: str, returncode: int, stdin_text: str) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text(
        "STDIN:\n"
        + stdin_text
        + "\n\nSTDOUT:\n"
        + stdout
        + "\n\nSTDERR:\n"
        + stderr
        + f"\n\nRETURN CODE: {returncode}\n"
    )


def run_command(executable: Path, stdin_text: str, cwd: Path, log_path: Path, label: str) -> None:
    ensure_executable(executable, label)
    result = subprocess.run(
        executable_command(executable),
        input=stdin_text,
        text=True,
        cwd=str(cwd),
        capture_output=True,
    )
    write_log(log_path, result.stdout, result.stderr, result.returncode, stdin_text)

    if result.returncode != 0:
        raise PipelineError(f"{label} failed with return code {result.returncode}. See {log_path}")


def require_perplex_dir(perplex_dir: Path) -> None:
    if not perplex_dir.exists():
        raise FileNotFoundError(f"Perple_X directory does not exist: {perplex_dir}")
    if not perplex_dir.is_dir():
        raise FileNotFoundError(f"Perple_X path is not a directory: {perplex_dir}")


def write_options(work_dir: Path, options: PerplexOptions = DEFAULT_PERPLEX_OPTIONS) -> Path:
    work_dir.mkdir(parents=True, exist_ok=True)
    option_path = work_dir / "perplex_option.dat"
    option_path.write_text(render_perplex_option_text(options))
    return option_path


def project_dat_file(work_dir: Path, project: str) -> Path:
    return work_dir / f"{project}.dat"


def clean_project_work_files(work_dir: Path, project: str) -> None:
    for path in work_dir.glob(f"{project}*"):
        if path.is_file():
            path.unlink()


def load_normalized_composition(composition_file: Path) -> tuple[dict, dict[str, float]]:
    data = json.loads(composition_file.read_text())
    composition = data.get("composition_normalized")
    if not isinstance(composition, dict):
        raise PipelineError(f"Composition file lacks composition_normalized: {composition_file}")

    normalized: dict[str, float] = {}
    for oxide, value in composition.items():
        try:
            normalized[oxide] = float(value)
        except (TypeError, ValueError) as exc:
            raise PipelineError(
                f"Composition value for {oxide} is not numeric in {composition_file}"
            ) from exc
    return data, normalized


def composition_oxide_order(data: dict, composition: dict[str, float]) -> list[str]:
    configured_order = data.get("oxide_order")
    if isinstance(configured_order, list) and all(isinstance(oxide, str) for oxide in configured_order):
        ordered = [oxide for oxide in configured_order if oxide in composition]
    else:
        ordered = []
    ordered.extend(sorted(oxide for oxide in composition if oxide not in ordered))
    return ordered


def active_components_for_database(database: str = DEFAULT_DATABASE) -> tuple[tuple[str, str], ...]:
    return get_database_components(resolve_database_name(database))


def active_component_oxides(database: str = DEFAULT_DATABASE) -> set[str]:
    return {oxide for oxide, _ in active_components_for_database(database)}


def omitted_composition_oxides(
    composition_file: Path,
    database: str = DEFAULT_DATABASE,
) -> list[tuple[str, float]]:
    data, composition = load_normalized_composition(composition_file)
    if is_component_composition_data(data):
        return []
    active_oxides = active_component_oxides(database)
    omitted: list[tuple[str, float]] = []
    for oxide in composition_oxide_order(data, composition):
        value = composition[oxide]
        if oxide not in active_oxides and abs(value) > OMITTED_OXIDE_THRESHOLD:
            omitted.append((oxide, value))
    return omitted


def omitted_oxide_records(
    composition_file: Path,
    database: str = DEFAULT_DATABASE,
) -> list[dict[str, float | str]]:
    data, composition = load_normalized_composition(composition_file)
    if is_component_composition_data(data):
        return []
    active_oxides = active_component_oxides(database)
    records: list[dict[str, float | str]] = []
    raw = data.get("composition_raw", {})
    for oxide in composition_oxide_order(data, composition):
        value = composition[oxide]
        if oxide not in active_oxides and abs(value) > OMITTED_OXIDE_THRESHOLD:
            record: dict[str, float | str] = {
                "oxide": oxide,
                "normalized_wt_percent": value,
                "reason": f"not_in_{resolve_database_name(database)}_active_component_list",
            }
            if isinstance(raw, dict) and oxide in raw:
                try:
                    record["raw_wt_percent"] = float(raw[oxide])
                except (TypeError, ValueError):
                    pass
            records.append(record)
    return records


def omitted_oxide_warning(
    composition_file: Path,
    database: str = DEFAULT_DATABASE,
) -> str | None:
    omitted = omitted_composition_oxides(composition_file, database=database)
    if not omitted:
        return None

    active_components = ", ".join(component for _, component in active_components_for_database(database))
    omitted_text = ", ".join(f"{oxide}={value:.8f} wt%" for oxide, value in omitted)
    return (
        f"WARNING: {composition_file.name} contains oxide(s) omitted from Perple_X BUILD "
        f"because the {resolve_database_name(database)} active component list is {active_components}: "
        f"{omitted_text}"
    )


def warn_omitted_oxides(model: ModelConfig) -> None:
    try:
        warning = omitted_oxide_warning(model.composition_file, database=model.database)
    except PipelineError as exc:
        print(f"WARNING: Could not inspect omitted oxides for {model.project}: {exc}", file=sys.stderr)
        return

    if not warning:
        return

    print(warning, file=sys.stderr)
    warning_path = model.output_dir / "oxide_omissions.txt"
    warning_path.write_text(warning + "\n")


def composition_bulk_values(
    composition_file: Path,
    database: str = DEFAULT_DATABASE,
) -> str:
    data, composition = load_normalized_composition(composition_file)
    components = active_components_for_database(database)
    missing: list[str] = []
    values: list[str] = []
    for source_name, component in components:
        value = aliased_component_value(composition, source_name, component)
        if value is None:
            missing.append(source_name)
            continue
        values.append(f"{value:.8f}")
    if missing:
        noun = "component(s)" if is_component_composition_data(data) else "oxide(s)"
        all_required = [comp for _, comp in components]
        basis = data.get("composition_basis", "oxides" if not is_component_composition_data(data) else "components")
        available_databases = ", ".join(sorted(DATABASES.keys()))

        error_msg = (
            f"Composition file is missing {noun} needed for BUILD: {', '.join(missing)}\n\n"
            f"Composition file: {composition_file}\n"
            f"Composition basis: {basis}\n"
            f"Database: {database}\n"
            f"Required {noun}: {', '.join(all_required)}\n\n"
            f"Solutions:\n"
            f"  1. Regenerate the composition file with all required {noun}\n"
            f"  2. Switch to a database that matches your composition\n"
            f"  3. Available databases: {available_databases}\n"
            f"  See docs/icy_worlds_guide.md for guidance."
        )
        raise PipelineError(error_msg)
    return " ".join(values)


def aliased_component_value(
    composition: dict[str, float],
    source_name: str,
    component: str,
) -> float | None:
    """Return a bulk value from either the source name or Perple_X component alias."""
    if source_name == component:
        return composition.get(source_name)
    source_present = source_name in composition
    component_present = component in composition
    if not source_present and not component_present:
        return None
    if source_present and not component_present:
        return composition[source_name]
    if component_present and not source_present:
        return composition[component]

    source_value = composition[source_name]
    component_value = composition[component]
    if abs(source_value) <= OMITTED_OXIDE_THRESHOLD and abs(component_value) > OMITTED_OXIDE_THRESHOLD:
        return component_value
    return source_value


def active_component_records(database: str = DEFAULT_DATABASE) -> list[dict[str, str]]:
    return [
        {"oxide": oxide, "component": component}
        for oxide, component in active_components_for_database(database)
    ]


def database_path(perplex_dir: Path, database: str = DEFAULT_DATABASE) -> Path:
    db = DATABASES[resolve_database_name(database)]
    return perplex_dir / "datafiles" / db.database_file


def solution_model_path(perplex_dir: Path, database: str = DEFAULT_DATABASE) -> Path:
    db = DATABASES[resolve_database_name(database)]
    return perplex_dir / "datafiles" / db.solution_model_file


def default_database_path(perplex_dir: Path) -> Path:
    return database_path(perplex_dir, DEFAULT_DATABASE)


def default_solution_model_path(perplex_dir: Path) -> Path:
    return solution_model_path(perplex_dir, DEFAULT_DATABASE)


def parse_perplex_components(database_text: str) -> list[str]:
    lower = database_text.lower()
    start = lower.find("begin_components")
    end = lower.find("end_components", start)
    if start < 0 or end < 0:
        raise PipelineError("Thermodynamic data file does not contain a begin_components/end_components block.")

    block = database_text[start + len("begin_components"):end]
    tokens = block.replace("|", " ").replace(",", " ").split()
    components: list[str] = []
    index = 0
    while index < len(tokens) - 1:
        name = tokens[index]
        value = tokens[index + 1].replace("D", "E").replace("d", "e")
        try:
            float(value)
        except ValueError:
            index += 1
            continue
        if any(character.isalpha() for character in name):
            components.append(name)
        index += 2
    if not components:
        raise PipelineError("No components were parsed from the thermodynamic data file.")
    return components


def read_perplex_database_components(database_file: Path) -> list[str]:
    if not database_file.exists():
        raise FileNotFoundError(f"Missing Perple_X thermodynamic data file: {database_file}")
    return parse_perplex_components(database_file.read_text(encoding="utf-8", errors="replace"))


def default_template_database(path: Path) -> str | None:
    for database, template in DEFAULT_BUILD_TEMPLATES.items():
        try:
            if path.resolve() == template.resolve():
                return database
        except FileNotFoundError:
            if path == template:
                return database
    return None


def is_default_build_template(model: ModelConfig) -> bool:
    try:
        return model.build_input_file.resolve() == default_build_template_for_database(model.database).resolve()
    except FileNotFoundError:
        return model.build_input_file == default_build_template_for_database(model.database)


def default_component_status(
    perplex_dir: Path,
    database: str = DEFAULT_DATABASE,
) -> list[dict[str, bool | str]]:
    database = resolve_database_name(database)
    declared_components = {
        component.upper()
        for component in read_perplex_database_components(database_path(perplex_dir, database))
    }
    active_components = {component.upper() for _, component in active_components_for_database(database)}
    return [
        {
            "oxide": oxide,
            "component": component,
            "declared_in_database": component.upper() in declared_components,
            "declared_in_default_database": component.upper() in declared_components,
            "passed_by_build": component.upper() in active_components,
            "passed_by_default_build": component.upper() in active_components,
        }
        for oxide, component in OXIDE_COMPONENT_NAMES.items()
    ]


def extract_pt_range_from_template(template_path: Path) -> tuple[tuple[float, float], tuple[float, float]] | None:
    """Extract P and T ranges from BUILD template file.

    Returns:
        ((p_min, p_max), (t_min, t_max)) in bar and K, or None if not found
    """
    try:
        lines = template_path.read_text().splitlines()
        # Look for lines matching "<pmin> <pmax>" and "<tmin> <tmax>"
        # These appear after the "1" (grid option) and before "y" (thermodynamic components)
        # Typical sequence: ...component list...empty line...n...1...<P range>...<T range>...y...
        p_range = None
        t_range = None
        for i, line in enumerate(lines):
            tokens = line.strip().split()
            if len(tokens) == 2:
                try:
                    val1, val2 = float(tokens[0]), float(tokens[1])
                    # Check if this looks like a PT range (ascending order, reasonable values)
                    if val1 < val2:
                        # Pressure range: typically 1-200000 bar (favor larger numbers)
                        if val2 >= 1000 and p_range is None:
                            p_range = (val1, val2)
                        # Temperature range: typically 200-4000 K (smaller than pressure)
                        elif 200 <= val1 and val2 <= 4000 and t_range is None:
                            t_range = (val1, val2)
                except (ValueError, IndexError):
                    continue
        if p_range and t_range:
            return (p_range, t_range)
    except Exception:
        pass
    return None


def validate_thermodynamic_setup(perplex_dir: Path, model: ModelConfig) -> None:
    template_database = default_template_database(model.build_input_file)
    if template_database and template_database != model.database:
        correct_template = DEFAULT_BUILD_TEMPLATES.get(model.database)
        template_suggestion = f"\n  Correct template: {correct_template}" if correct_template else ""
        raise PipelineError(
            f"BUILD template mismatch for model '{model.project}':\n"
            f"  Template: {model.build_input_file.name} (designed for '{template_database}')\n"
            f"  Model database: {model.database}{template_suggestion}\n\n"
            f"Solutions:\n"
            f"  1. Change model database to '{template_database}' in your config\n"
            f"  2. Use the correct BUILD template for '{model.database}'\n"
            f"  3. Remove 'build_input_file' from model to use default template\n\n"
            f"See docs/icy_worlds_guide.md for database-template compatibility."
        )

    if not is_default_build_template(model):
        return

    database_file = database_path(perplex_dir, model.database)
    solution_model_file = solution_model_path(perplex_dir, model.database)
    if not database_file.exists():
        raise FileNotFoundError(f"Missing Perple_X thermodynamic data file: {database_file}")
    if not solution_model_file.exists():
        raise FileNotFoundError(f"Missing Perple_X solution model file: {solution_model_file}")
    declared_components = {
        component.upper()
        for component in read_perplex_database_components(database_file)
    }
    required_components = [component for _, component in active_components_for_database(model.database)]
    missing_components = [
        component
        for component in required_components
        if component.upper() not in declared_components
    ]
    if missing_components:
        raise PipelineError(
            f"{model.database} BUILD template requires component(s) not declared in {database_file.name}: "
            f"{', '.join(missing_components)}"
        )

    # Validate PT range consistency (warning only, not fatal)
    db_config = DATABASES[model.database]
    template_pt = extract_pt_range_from_template(model.build_input_file)
    if template_pt:
        (template_p_min, template_p_max), (template_t_min, template_t_max) = template_pt
        config_p_min = db_config.pt_range["pressure_bar"]["min"]
        config_p_max = db_config.pt_range["pressure_bar"]["max"]
        config_t_min = db_config.pt_range["temperature_k"]["min"]
        config_t_max = db_config.pt_range["temperature_k"]["max"]

        # Check if template PT significantly exceeds database calibration (>10% beyond)
        if template_p_max > config_p_max * 1.1 or template_p_min < config_p_min * 0.9:
            print(
                f"WARNING: BUILD template pressure range ({template_p_min:.0f}-{template_p_max:.0f} bar) "
                f"extends beyond {model.database} database calibration ({config_p_min:.0f}-{config_p_max:.0f} bar). "
                f"Results may be unreliable.",
                file=sys.stderr,
            )
        if template_t_max > config_t_max * 1.1 or template_t_min < config_t_min * 0.9:
            print(
                f"WARNING: BUILD template temperature range ({template_t_min:.0f}-{template_t_max:.0f} K) "
                f"extends beyond {model.database} database calibration ({config_t_min:.0f}-{config_t_max:.0f} K). "
                f"Results may be unreliable.",
                file=sys.stderr,
            )


def validate_default_thermodynamic_setup(perplex_dir: Path, model: ModelConfig) -> None:
    validate_thermodynamic_setup(perplex_dir, model)


def build_template_provenance(perplex_dir: Path, model: ModelConfig) -> dict:
    try:
        database_components = read_perplex_database_components(database_path(perplex_dir, model.database))
    except (FileNotFoundError, PipelineError):
        database_components = []

    db = DATABASES[model.database]
    source_only = get_source_only_oxides(model.database)
    return {
        "database_name": model.database,
        "build_template": str(model.build_input_file),
        "active_perplex_components": active_component_records(model.database),
        "source_only_oxides": list(source_only),
        "database_file": str(database_path(perplex_dir, model.database)),
        "solution_model_file": str(solution_model_path(perplex_dir, model.database)),
        "database_declared_components": database_components,
        "p_t_range": db.pt_range,
        "excluded_phases": list(db.excluded_phases),
        "solution_models": list(db.solution_models),
        "perplex_options": {
            "sample_on_grid": model.perplex_options.sample_on_grid,
            "x_nodes": list(model.perplex_options.x_nodes),
            "y_nodes": list(model.perplex_options.y_nodes),
            "grid_levels": list(model.perplex_options.grid_levels),
            "auto_refine": model.perplex_options.auto_refine,
            "final_resolution": list(model.perplex_options.final_resolution),
        },
        "provenance_note": (
            f"These fields describe the '{model.database}' thermodynamic profile used by this model. "
            f"Source-only oxides for this profile: {', '.join(source_only) if source_only else 'none'}. "
            "If a custom build_input_file is supplied, verify that the template, bulk-value order, "
            "database, solution model file, and phase choices agree."
        ),
    }


def werami_input_text(model: ModelConfig) -> str:
    return f"{model.project}\n" + "\n".join(model.werami_input_sequence) + "\n"


def template_path(path: Path) -> str:
    return path.as_posix()


def render_build_input(perplex_dir: Path, model: ModelConfig) -> str:
    text = model.build_input_file.read_text()
    build_title = model.project
    if model.composition_file.exists():
        try:
            composition_data = json.loads(model.composition_file.read_text())
            build_title = str(composition_data.get("description") or model.project)
        except json.JSONDecodeError:
            build_title = model.project
    replacements = {
        "${PERPLEX_DIR}": template_path(perplex_dir),
        "${PROJECT}": model.project,
        "${COMPOSITION_FILE}": template_path(model.composition_file),
        "${OUTPUT_DIR}": template_path(model.output_dir),
        "${WORK_DIR}": template_path(model.work_dir),
        "${BUILD_TITLE}": build_title,
        "${THERMODYNAMIC_DATABASE_FILE}": template_path(database_path(perplex_dir, model.database)),
        "${SOLUTION_MODEL_FILE}": template_path(solution_model_path(perplex_dir, model.database)),
    }
    if "${PERPLEX_BULK_VALUES}" in text:
        replacements["${PERPLEX_BULK_VALUES}"] = composition_bulk_values(
            model.composition_file,
            database=model.database,
        )
    for placeholder, value in replacements.items():
        text = text.replace(placeholder, value)
    return text


def run_build(perplex_dir: Path, model: ModelConfig) -> None:
    log_path = model.output_dir / "build.log"
    dat_file = project_dat_file(model.work_dir, model.project)

    if not model.build_input_file.exists():
        raise FileNotFoundError(
            f"Missing BUILD input file for {model.project}: {model.build_input_file}. "
            "This pipeline always runs Perple_X BUILD before VERTEX/WERAMI; provide a valid "
            "build_input_file or configure a database with a bundled BUILD template."
        )

    print(f"Running BUILD for {model.project}")
    clean_project_work_files(model.work_dir, model.project)
    run_command(
        executable=executable_path(perplex_dir, "build"),
        stdin_text=render_build_input(perplex_dir, model),
        cwd=model.work_dir,
        log_path=log_path,
        label="BUILD",
    )

    if not dat_file.exists():
        raise FileNotFoundError(f"BUILD completed but did not create expected .dat file: {dat_file}")


def require_dat_file(work_dir: Path, project: str) -> None:
    dat_file = project_dat_file(work_dir, project)
    if not dat_file.exists():
        raise FileNotFoundError(
            f"Missing Perple_X .dat file for {project}: {dat_file}. "
            "BUILD must create this file before VERTEX can run."
        )


def run_vertex(perplex_dir: Path, model: ModelConfig) -> None:
    print(f"Running VERTEX for {model.project}")
    run_command(
        executable=executable_path(perplex_dir, "vertex"),
        stdin_text=f"{model.project}\n",
        cwd=model.work_dir,
        log_path=model.output_dir / "vertex.log",
        label="VERTEX",
    )


def run_werami(perplex_dir: Path, model: ModelConfig) -> Path:
    print(f"Running WERAMI for {model.project}")
    run_command(
        executable=executable_path(perplex_dir, "werami"),
        stdin_text=werami_input_text(model),
        cwd=model.work_dir,
        log_path=model.output_dir / "werami.log",
        label="WERAMI",
    )

    raw_tab = model.work_dir / f"{model.project}_1.tab"
    if not raw_tab.exists():
        raise FileNotFoundError(f"WERAMI completed but expected table was not found: {raw_tab}")

    raw_copy = model.output_dir / f"{model.project}_raw_werami.tab"
    shutil.copy2(raw_tab, raw_copy)

    planetprofile_tab = model.output_dir / f"{model.project}_planetprofile.tab"
    write_planetprofile_tab(raw_tab, planetprofile_tab)

    native_tab = model.output_dir / f"{model.project}_planetprofile_native.tab"
    write_planetprofile_native_table(
        raw_tab,
        native_tab,
        source_name=raw_tab.name,
        first_axis=model.planetprofile_first_axis,
    )
    return planetprofile_tab


def format_tab_value(value: float) -> str:
    if value != value:
        return "NaN"
    return f"{value:.10g}"


def write_planetprofile_tab(source_tab: Path, destination_tab: Path) -> None:
    tab = read_tab(source_tab)
    indices = column_indices(tab.headers)
    missing = [display for canonical, display in PLANETPROFILE_COLUMNS if canonical not in indices]
    if missing:
        raise PipelineError(f"Cannot write PlanetProfile table; missing column(s): {', '.join(missing)}")

    destination_tab.parent.mkdir(parents=True, exist_ok=True)
    with destination_tab.open("w", encoding="utf-8") as handle:
        handle.write("\t".join(display for _, display in PLANETPROFILE_COLUMNS) + "\n")
        for row in tab.rows:
            handle.write(
                "\t".join(format_tab_value(row[indices[canonical]]) for canonical, _ in PLANETPROFILE_COLUMNS)
                + "\n"
            )


def run_model(perplex_dir: Path, model: ModelConfig, *, skip_validation: bool = False) -> None:
    model.output_dir.mkdir(parents=True, exist_ok=True)
    model.work_dir.mkdir(parents=True, exist_ok=True)
    validate_thermodynamic_setup(perplex_dir, model)
    if not model.composition_file.exists():
        print(f"WARNING: composition file not found for {model.project}: {model.composition_file}")
    else:
        warn_omitted_oxides(model)

    option_path = write_options(model.work_dir, model.perplex_options)
    print(f"Wrote {option_path}")
    run_build(perplex_dir, model)
    require_dat_file(model.work_dir, model.project)

    try: 
        run_vertex(perplex_dir, model)
        tab_path = run_werami(perplex_dir, model)
    except Exception as e:
        # Write a failed validation report before re-raising
        validation_report_path = model.output_dir / "validation_report.txt"
        validation_report_path.parent.mkdir(parents=True, exist_ok=True)
        validation_report_path.write_text(f"STATUS: FAIL\nError: {str(e)}\n")
        raise

    if skip_validation:
        print(f"Validation skipped for {model.project}; technical output exists at {tab_path}")
        return

    result = validate_project_output(model.project, model.output_dir, tab_path=tab_path)
    print(result.report_path.read_text())
    if not result.passed:
        raise PipelineError(
            f"Validation failed for {model.project}. "
            f"Technical output exists at {tab_path}, but readiness checks failed. "
            f"See {result.report_path}"
        )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run local Perple_X BUILD/VERTEX/WERAMI pipeline.")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG), help="Path to configs/models.json.")
    parser.add_argument("--project", help="Run only one project from the config.")
    parser.add_argument(
        "--database",
        choices=sorted(DATABASES),
        help="Thermodynamic database profile to use instead of the config value.",
    )
    parser.add_argument(
        "--perplex-dir",
        help="Path to a Perple_X installation, overriding configs/models.json.",
    )
    parser.add_argument(
        "--skip-validation",
        action="store_true",
        help="Run BUILD/VERTEX/WERAMI but skip output validation.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config_path = resolve_path(args.config, BASE_DIR)

    try:
        config = load_config(
            config_path,
            database_override=args.database,
            perplex_dir_override=args.perplex_dir,
        )
        require_perplex_dir(config.perplex_dir)

        selected = [model for model in config.models if not args.project or model.project == args.project]
        if args.project and not selected:
            raise PipelineError(f"Project not found in config: {args.project}")

        for model in selected:
            run_model(config.perplex_dir, model, skip_validation=args.skip_validation)
    except (
        FileNotFoundError,
        PermissionError,
        ValueError,
        json.JSONDecodeError,
        PipelineError,
        subprocess.SubprocessError,
    ) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
