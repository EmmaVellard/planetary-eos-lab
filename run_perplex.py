from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from validate_tab import column_indices, read_tab, validate_project_output


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG = BASE_DIR / "configs" / "models.json"

PERPLEX_OPTION_TEXT = """\
warn_interactive F
pause_on_error F
spreadsheet T
sample_on_grid T
seismic_data_file T
bad_number NaN
grid_levels 1 1
x_nodes 20 40
y_nodes 20 40
"""

WERAMI_INPUT_TEMPLATE = "{project}\n2\n38\n1\n2\n13\n14\n3\n4\n10\n11\n0\nn\n1\n0\n"

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
OMITTED_OXIDE_THRESHOLD = 1.0e-12


class PipelineError(RuntimeError):
    pass


@dataclass(frozen=True)
class ModelConfig:
    project: str
    composition_file: Path
    build_input_file: Path
    output_dir: Path
    work_dir: Path


@dataclass(frozen=True)
class PipelineConfig:
    perplex_dir: Path
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


def load_config(config_path: Path) -> PipelineConfig:
    base_dir = config_base_dir(config_path)
    data = json.loads(config_path.read_text())
    models: list[ModelConfig] = []

    for model in data["models"]:
        project = model["project"]
        output_dir = resolve_path(model.get("output_dir", f"outputs/{project}"), base_dir)
        work_dir = (
            resolve_path(model["work_dir"], base_dir)
            if "work_dir" in model
            else output_dir / "work"
        )
        models.append(
            ModelConfig(
                project=project,
                composition_file=resolve_path(model["composition_file"], base_dir),
                build_input_file=resolve_path(model["build_input_file"], base_dir),
                output_dir=output_dir,
                work_dir=work_dir,
            )
        )

    return PipelineConfig(
        perplex_dir=resolve_path(data["perplex_dir"], base_dir),
        models=models,
    )


def executable_path(perplex_dir: Path, name: str) -> Path:
    bin_path = perplex_dir / "bin" / name
    if bin_path.exists():
        return bin_path
    return perplex_dir / name


def ensure_executable(path: Path, label: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"Missing {label} executable: {path}")
    if not path.is_file():
        raise FileNotFoundError(f"{label} executable is not a file: {path}")
    if not os.access(path, os.X_OK):
        raise PermissionError(f"{label} executable is not executable: {path}")


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
        [str(executable)],
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


def write_options(work_dir: Path) -> Path:
    work_dir.mkdir(parents=True, exist_ok=True)
    option_path = work_dir / "perplex_option.dat"
    option_path.write_text(PERPLEX_OPTION_TEXT)
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


def omitted_composition_oxides(composition_file: Path) -> list[tuple[str, float]]:
    data, composition = load_normalized_composition(composition_file)
    omitted: list[tuple[str, float]] = []
    for oxide in composition_oxide_order(data, composition):
        value = composition[oxide]
        if oxide not in ACTIVE_COMPOSITION_OXIDES and abs(value) > OMITTED_OXIDE_THRESHOLD:
            omitted.append((oxide, value))
    return omitted


def omitted_oxide_warning(composition_file: Path) -> str | None:
    omitted = omitted_composition_oxides(composition_file)
    if not omitted:
        return None

    active_components = ", ".join(component for _, component in PERPLEX_COMPONENTS)
    omitted_text = ", ".join(f"{oxide}={value:.8f} wt%" for oxide, value in omitted)
    return (
        f"WARNING: {composition_file.name} contains oxide(s) omitted from Perple_X BUILD "
        f"because the active component list is {active_components}: {omitted_text}"
    )


def warn_omitted_oxides(model: ModelConfig) -> None:
    try:
        warning = omitted_oxide_warning(model.composition_file)
    except PipelineError as exc:
        print(f"WARNING: Could not inspect omitted oxides for {model.project}: {exc}", file=sys.stderr)
        return

    if not warning:
        return

    print(warning, file=sys.stderr)
    warning_path = model.output_dir / "oxide_omissions.txt"
    warning_path.write_text(warning + "\n")


def composition_bulk_values(composition_file: Path) -> str:
    _, composition = load_normalized_composition(composition_file)
    missing = [oxide for oxide, _ in PERPLEX_COMPONENTS if oxide not in composition]
    if missing:
        raise PipelineError(
            f"Composition file is missing oxide(s) needed for BUILD: {', '.join(missing)}"
        )

    values: list[str] = []
    for oxide, _ in PERPLEX_COMPONENTS:
        values.append(f"{composition[oxide]:.8f}")
    return " ".join(values)


def render_build_input(perplex_dir: Path, model: ModelConfig) -> str:
    text = model.build_input_file.read_text()
    replacements = {
        "${PERPLEX_DIR}": str(perplex_dir),
        "${PROJECT}": model.project,
        "${COMPOSITION_FILE}": str(model.composition_file),
        "${OUTPUT_DIR}": str(model.output_dir),
        "${WORK_DIR}": str(model.work_dir),
    }
    if "${PERPLEX_BULK_VALUES}" in text:
        replacements["${PERPLEX_BULK_VALUES}"] = composition_bulk_values(model.composition_file)
    for placeholder, value in replacements.items():
        text = text.replace(placeholder, value)
    return text


def run_build_if_input_exists(perplex_dir: Path, model: ModelConfig) -> None:
    log_path = model.output_dir / "build.log"
    dat_file = project_dat_file(model.work_dir, model.project)

    if not model.build_input_file.exists():
        log_path.write_text(
            "BUILD skipped.\n"
            f"Build input file not found: {model.build_input_file}\n"
            f"Existing .dat required: {dat_file}\n"
        )
        print(f"BUILD skipped for {model.project}; no build input file at {model.build_input_file}")
        return

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
            "Create it with BUILD or provide build_input_file in the config."
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
        stdin_text=WERAMI_INPUT_TEMPLATE.format(project=model.project),
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


def run_model(perplex_dir: Path, model: ModelConfig) -> None:
    model.output_dir.mkdir(parents=True, exist_ok=True)
    model.work_dir.mkdir(parents=True, exist_ok=True)
    if not model.composition_file.exists():
        print(f"WARNING: composition file not found for {model.project}: {model.composition_file}")
    else:
        warn_omitted_oxides(model)

    option_path = write_options(model.work_dir)
    print(f"Wrote {option_path}")
    run_build_if_input_exists(perplex_dir, model)
    require_dat_file(model.work_dir, model.project)
    run_vertex(perplex_dir, model)
    tab_path = run_werami(perplex_dir, model)

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
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config_path = resolve_path(args.config, BASE_DIR)

    try:
        config = load_config(config_path)
        require_perplex_dir(config.perplex_dir)

        selected = [model for model in config.models if not args.project or model.project == args.project]
        if args.project and not selected:
            raise PipelineError(f"Project not found in config: {args.project}")

        for model in selected:
            run_model(config.perplex_dir, model)
    except (FileNotFoundError, PermissionError, PipelineError, subprocess.SubprocessError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
