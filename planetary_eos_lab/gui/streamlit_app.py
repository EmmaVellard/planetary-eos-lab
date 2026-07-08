from __future__ import annotations

import json
import math
import os
import signal
import subprocess
import sys
import time
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots

import plot_comparisons
import run_perplex
from planetary_eos_lab.core.config import DATABASES
from planetary_eos_lab.core.config_io import (
    DEFAULT_CONFIG_PATH,
    EXAMPLE_CONFIG_PATH,
    copy_example_config,
    delete_model_entry,
    delete_model_entries,
    list_model_entries,
    load_config_json,
    replace_model_entry,
    resolve_path,
    save_config_json,
    update_perplex_dir,
)
from planetary_eos_lab.gui.autosave import show_autosave_controls
from planetary_eos_lab.gui.batch_processor import show_batch_workspace
from planetary_eos_lab.gui.comparison_tools import show_comparison_workspace
from planetary_eos_lab.gui.database_selector import (
    BUILD_TEMPLATE_CUSTOM_CHOICE,
    BUILD_TEMPLATE_DEFAULT_CHOICE,
    DEFAULT_BUILD_TEMPLATES,
    available_build_templates,
    build_template_database,
    build_template_label,
    build_template_matches_database_default,
    get_current_database,
    model_uses_database_default_template,
    normalize_build_template_path,
    show_database_selector,
)
from planetary_eos_lab.gui.import_export import (
    export_model_definitions_to_json,
    model_definitions_export_filename,
    show_import_export_panel,
)
from planetary_eos_lab.gui.phase_diagram import show_phase_diagram_panel
from planetary_eos_lab.core.database_utils import (
    describe_database,
    get_active_oxides,
    get_database_components,
    get_source_only_oxides,
)
from planetary_eos_lab.core.model_schema import (
    OXIDE_ORDER,
    component_composition_from_model,
    composition_plot_rows,
    new_model_template,
    omitted_oxides_for_model,
    oxide_table_rows,
    raw_total,
    scientific_guardrail_text,
    use_as_final_moon_mantle_eos,
    validate_model_entry,
)
from planetary_eos_lab.core.pipeline_runner import (
    PipelineCommand,
    export_planetprofile_command,
    full_pipeline_command,
    generate_compositions_command,
)
from planetary_eos_lab.core.validation_summary import (
    export_manifest_path,
    export_manifest_table_rows,
    model_output_paths,
    read_export_manifest,
    read_text_if_exists,
    validation_status,
)


st.set_page_config(page_title="Planetary EOS Lab", layout="wide", page_icon="🪐")

DEFAULT_PLANETPROFILE_EXPORT_DIR = REPO_ROOT / "outputs" / "planetprofile_export"
HOME_MODE = "Home"
LEGACY_COMPOSITION_BUILDER_MODE = "Build Composition"
COMPOSITION_BUILDER_MODE = "Composition"
PIPELINE_MODE = "Run Pipeline"
BATCH_PROCESSING_MODE = "Batch Processing"
COMPARISON_MODE = "Compare Models"
PIPELINE_STEP_CONTROL_KEY = "pipeline_step_radio"
COMPOSITION_PAGE_CONTROL_KEY = "composition_page_radio"
PIPELINE_SELECTION_KEY = "pipeline_selected_projects"
PIPELINE_MODEL_SELECTOR_KEYS = [
    PIPELINE_SELECTION_KEY,
    "generate_model_projects",
    "run_model_projects",
    "step5_plot_projects",
    "export_model_projects",
]
RUNNING_COMMAND_JOB_KEY = "streamlit_running_command_job"

PIPELINE_STEPS = [
    "1. Setup & Select Models",
    "2. Generate Files",
    "3. Run Perple_X",
    "4. Validate / Export",
]

COMPOSITION_BUILD_PAGE = "Build"
COMPOSITION_CATALOG_PAGE = "Catalog"
COMPOSITION_BATCH_PAGE = "Batch Processing"
COMPOSITION_THERMO_PAGE = "Thermodynamic Models"
COMPOSITION_PAGES = [
    COMPOSITION_BUILD_PAGE,
    COMPOSITION_BATCH_PAGE,
    COMPOSITION_CATALOG_PAGE,
    COMPOSITION_THERMO_PAGE,
]


def unique_project_name(base_project: str, existing_projects: set[str]) -> str:
    safe_base = base_project.strip() or "copied_surface_proxy"
    candidate = f"{safe_base}_copy"
    suffix = 2
    while candidate in existing_projects:
        candidate = f"{safe_base}_copy_{suffix}"
        suffix += 1
    return candidate


def inject_styles() -> None:
    st.markdown(
        """
        <style>
        /* Lilac purple color scheme */
        :root {
            --primary-color: #b19cd9;
            --primary-hover: #a28dca;
            --primary-light: #c5b5e3;
            --primary-dark: #8877b8;
        }
        section[data-testid="stSidebar"] div.stButton > button {
            justify-content: flex-start;
            border-radius: 7px;
            min-height: 2.35rem;
            transition: background-color 120ms ease, border-color 120ms ease, color 120ms ease;
        }
        section[data-testid="stSidebar"] div.stButton > button:hover {
            border-color: #b19cd9;
            background: rgba(177, 156, 217, 0.12);
            color: #30283a;
        }
        section[data-testid="stSidebar"] div.stButton > button[kind="primary"]:hover {
            background: #a28dca;
            border-color: #a28dca;
            color: #ffffff;
        }
        section[data-testid="stSidebar"] div[data-testid="stRadio"] [role="radiogroup"] {
            display: flex;
            flex-direction: column;
            gap: 0.1rem;
        }
        section[data-testid="stSidebar"] div[data-testid="stRadio"] [role="radiogroup"] label {
            width: 100%;
            padding: 0.38rem 0.15rem 0.32rem 0;
            border-bottom: 2px solid transparent;
            border-radius: 0;
            color: #31333f;
            font-weight: 600;
            transition: border-color 120ms ease, color 120ms ease;
        }
        section[data-testid="stSidebar"] div[data-testid="stRadio"] [role="radiogroup"] label:hover {
            background: transparent;
            border-bottom-color: #b19cd9;
            color: #8877b8;
            font-weight: 700;
        }
        section[data-testid="stSidebar"] div[data-testid="stRadio"] [role="radiogroup"] label:hover * {
            color: #8877b8;
            font-weight: 700;
        }
        section[data-testid="stSidebar"] div[data-testid="stRadio"] [role="radiogroup"] label:has(input:checked) {
            border-bottom-color: #b19cd9;
            color: #8877b8;
            font-weight: 700;
        }
        section[data-testid="stSidebar"] div[data-testid="stRadio"] [role="radiogroup"] label:has(input:checked) * {
            color: #8877b8;
            font-weight: 700;
        }
        section[data-testid="stSidebar"] div[data-testid="stRadio"] [role="radiogroup"] label > div:first-child {
            display: none;
        }
        /* Primary buttons */
        button[kind="primary"] {
            background-color: #b19cd9 !important;
            border-color: #b19cd9 !important;
        }
        button[kind="primary"]:hover {
            background-color: #a28dca !important;
            border-color: #a28dca !important;
        }
        /* Links and accents */
        a {
            color: #8877b8 !important;
        }
        a:hover {
            color: #b19cd9 !important;
        }
        /* Home button special styling */
        div[data-testid="stSidebar"] button[data-testid*="workspace_mode_Home"] {
            background: linear-gradient(135deg, #b19cd9 0%, #8877b8 100%) !important;
            border: 2px solid #8877b8 !important;
            color: white !important;
            font-weight: 700 !important;
            box-shadow: 0 2px 6px rgba(136, 119, 184, 0.25);
        }
        div[data-testid="stSidebar"] button[data-testid*="workspace_mode_Home"]:hover {
            background: linear-gradient(135deg, #a28dca 0%, #7766a9 100%) !important;
            border-color: #7766a9 !important;
            box-shadow: 0 3px 8px rgba(136, 119, 184, 0.35);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def load_config_or_none(config_path: Path) -> dict[str, Any] | None:
    try:
        return load_config_json(config_path)
    except FileNotFoundError:
        return None
    except json.JSONDecodeError as exc:
        st.error(f"Config JSON is invalid: {exc}")
        return None


def write_config(config_path: Path, config: dict[str, Any]) -> None:
    save_config_json(config_path, config)
    st.success(f"Saved {config_path}")


def model_label(model: dict[str, Any]) -> str:
    project = model.get("project", "<missing project>")
    status = model.get("scientific_status", "unknown")
    return f"{project} ({status})"


def project_options(models: list[dict[str, Any]]) -> list[str]:
    return [str(model.get("project", "")) for model in models if model.get("project")]


def valid_project_selection(projects: Any, available_projects: list[str]) -> list[str]:
    if isinstance(projects, str):
        candidates = [projects]
    elif isinstance(projects, (list, tuple, set)):
        candidates = [str(project) for project in projects]
    else:
        candidates = []
    available = set(available_projects)
    return [project for project in candidates if project in available]


def sync_model_selection(source_key: str, available_projects: list[str]) -> None:
    selected_projects = valid_project_selection(st.session_state.get(source_key), available_projects)
    for key in PIPELINE_MODEL_SELECTOR_KEYS:
        if key != source_key:
            st.session_state[key] = selected_projects


def seed_model_selector_state(widget_key: str, available_projects: list[str]) -> None:
    shared_selection = valid_project_selection(st.session_state.get(PIPELINE_SELECTION_KEY), available_projects)
    if widget_key in st.session_state:
        widget_selection = valid_project_selection(st.session_state[widget_key], available_projects)
        if widget_key != PIPELINE_SELECTION_KEY and shared_selection and widget_selection != shared_selection:
            st.session_state[widget_key] = shared_selection
        else:
            st.session_state[widget_key] = widget_selection
        return
    st.session_state[widget_key] = shared_selection


def current_pipeline_selection(available_projects: list[str]) -> list[str]:
    return valid_project_selection(st.session_state.get(PIPELINE_SELECTION_KEY), available_projects)


def models_for_projects(models: list[dict[str, Any]], selected_projects: list[str]) -> list[dict[str, Any]]:
    if not selected_projects:
        return models
    selected = set(selected_projects)
    return [model for model in models if str(model.get("project", "")) in selected]


def model_by_project(models: list[dict[str, Any]], project: str) -> dict[str, Any] | None:
    return next((model for model in models if model.get("project") == project), None)


def selected_project_names(selected_project: str | list[str] | tuple[str, ...] | set[str] | None) -> set[str]:
    if selected_project is None:
        return set()
    if isinstance(selected_project, str):
        return {selected_project} if selected_project else set()
    return {str(project) for project in selected_project if project}


def relabel_command(command: PipelineCommand, label: str) -> PipelineCommand:
    return PipelineCommand(label=label, command=command.command, cwd=command.cwd)


def active_component_text(database: str) -> str:
    return " ".join(component for _, component in get_database_components(database))


THERMODYNAMIC_MODEL_USE_CASES = {
    "stx21": "Default silicate mantle work and quick lunar-style oxide smoke tests.",
    "hp633": "Silicate compositions that need TiO2, K2O, H2O, or broader common oxide coverage.",
    "dew17_hhph": "Element-based chondritic or undifferentiated icy-world interiors over a broad P-T range.",
    "hpha02_hydrous": "Cold, shallow hydrous rock plus water tests near icy-moon surface conditions.",
    "dew13_hydrous": "Cool differentiated icy-world silicates with a compact hydrous element setup.",
    "dew17_comet": "Volatile-rich comet or ice-rock bulk compositions with H/C/N/O/S components.",
}


def database_uses_component_inputs(database: str) -> bool:
    active = get_active_oxides(database)
    return not any(oxide in active for oxide in OXIDE_ORDER)


def safe_component_composition(model: dict[str, Any]) -> dict[str, float] | None:
    try:
        return component_composition_from_model(model)
    except (TypeError, ValueError):
        return None


def model_input_total(model: dict[str, Any]) -> float:
    components = safe_component_composition(model)
    if components is not None:
        return sum(components.values())
    return raw_total(model)


def component_table_rows(model: dict[str, Any], database: str) -> list[dict[str, Any]]:
    components = safe_component_composition(model) or {}
    build_components = get_database_components(database)
    order = [component for _, component in build_components]
    order.extend(sorted(component for component in components if component not in order))
    total = sum(float(components.get(component, 0.0)) for component in order)
    rows: list[dict[str, Any]] = []
    active = {component for _, component in build_components}
    for component in order:
        value = float(components.get(component, 0.0))
        normalized = value * 100.0 / total if total > 0 else 0.0
        rows.append(
            {
                "component": component,
                "your input wt%": value,
                "normalized to 100 wt%": normalized,
                f"{database} role": f"passed to {database} BUILD" if component in active else "saved only",
            }
        )
    return rows


def show_component_table(rows: list[dict[str, Any]]) -> None:
    st.dataframe(
        rows,
        width="stretch",
        hide_index=True,
        column_config={
            "your input wt%": st.column_config.NumberColumn(format="%.2f"),
            "normalized to 100 wt%": st.column_config.NumberColumn(format="%.2f"),
        },
    )


def compact_model_overview_rows(
    models: list[dict[str, Any]],
    selected_project: str | list[str] | tuple[str, ...] | set[str] | None = None,
    database: str = "stx21",
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    selected_projects = selected_project_names(selected_project)
    for model in models:
        project = str(model.get("project", ""))
        model_database = str(model.get("database") or database)
        validation = validate_model_entry(model)
        try:
            total = round(model_input_total(model), 2)
        except (TypeError, ValueError):
            total = None
        if safe_component_composition(model) is not None:
            omitted = "not applicable"
        else:
            try:
                omitted = ", ".join(str(item["oxide"]) for item in omitted_oxides_for_model(model, database=model_database)) or "none"
            except (TypeError, ValueError):
                omitted = "unknown"
        composition_basis = "components" if safe_component_composition(model) is not None else "oxides"
        rows.append(
            {
                "selected": "yes" if project in selected_projects else "",
                "project": project,
                "description": str(model.get("description", "")),
                "thermodynamic model": model_database,
                "composition basis": composition_basis,
                "status": str(model.get("scientific_status", "")),
                "readiness": str(model.get("planetprofile_readiness", "")),
                "input total wt%": total,
                "omitted from BUILD": omitted,
                "PlanetProfile table": str(model.get("planetprofile_filename", "")),
                "validation": "ok" if validation.ok else "; ".join(validation.errors),
            }
        )
    return rows


def detailed_model_overview_rows(
    models: list[dict[str, Any]],
    selected_project: str | list[str] | tuple[str, ...] | set[str] | None = None,
    database: str = "stx21",
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    selected_projects = selected_project_names(selected_project)
    for model in models:
        project = str(model.get("project", ""))
        model_database = str(model.get("database") or database)
        validation = validate_model_entry(model)
        try:
            total = round(model_input_total(model), 2)
        except (TypeError, ValueError):
            total = None
        component_composition = safe_component_composition(model)
        if component_composition is not None:
            omitted = "not applicable"
        else:
            try:
                omitted = ", ".join(str(item["oxide"]) for item in omitted_oxides_for_model(model, database=model_database)) or "none"
            except (TypeError, ValueError):
                omitted = "unknown"
        source_composition = (
            model.get("oxides_wt_percent")
            or model.get("raw_wt_percent")
            or model.get("composition_raw")
            or {}
        )
        if not isinstance(source_composition, dict):
            source_composition = {}
        row: dict[str, Any] = {
            "selected for run": "yes" if project in selected_projects else "",
            "project": project,
            "description": str(model.get("description", "")),
            "thermodynamic model": model_database,
            "scientific status": str(model.get("scientific_status", "")),
            "model scope": str(model.get("model_scope", "")),
            "PlanetProfile readiness": str(model.get("planetprofile_readiness", "")),
            "input total wt%": total,
            "composition basis": "components" if component_composition is not None else "oxides",
            "omitted from BUILD": omitted,
            "PlanetProfile filename": str(model.get("planetprofile_filename", "")),
            "based on literature values": "yes" if model.get("literature_proxy") else "no",
            "use as final scientific EOS": "yes" if use_as_final_moon_mantle_eos(model) else "no",
            "validation": "ok" if validation.ok else "; ".join(validation.errors),
            "composition interpretation": str(model.get("composition_interpretation", "")),
            "source note": str(model.get("source_note", "")),
        }
        for oxide in OXIDE_ORDER:
            try:
                row[f"{oxide} wt%"] = round(float(source_composition.get(oxide, 0.0)), 2)
            except (TypeError, ValueError):
                row[f"{oxide} wt%"] = None
        rows.append(row)
    return rows


def show_scientific_guardrail(model: dict[str, Any], database: str = "stx21") -> None:
    st.code(scientific_guardrail_text(model, database=database), language="text")
    if model.get("scientific_status") == "surface_proxy_smoke_test":
        st.warning("This is a surface-proxy smoke test, not a final EOS model.")
    if not use_as_final_moon_mantle_eos(model):
        st.info("Use as final scientific EOS: no")


def rounded_oxide_rows(rows: list[dict[str, Any]], database: str = "stx21") -> list[dict[str, Any]]:
    return [
        {
            "oxide": row["oxide"],
            "your input wt%": round(float(row["raw_wt_percent"]), 2),
            "normalized to 100 wt%": round(float(row["normalized_wt_percent"]), 2),
            f"{database} role": row["build_role"],
            "omitted from BUILD": row["omitted_from_default_build"],
        }
        for row in rows
    ]


def show_oxide_table(rows: list[dict[str, Any]], database: str = "stx21") -> None:
    st.dataframe(
        rounded_oxide_rows(rows, database=database),
        width="stretch",
        hide_index=True,
        column_config={
            "your input wt%": st.column_config.NumberColumn(format="%.2f"),
            "normalized to 100 wt%": st.column_config.NumberColumn(format="%.2f"),
        },
    )


@dataclass(frozen=True)
class GuiPerplexOptions:
    sample_on_grid: bool = False
    x_nodes: tuple[int, int] = (40, 300)
    y_nodes: tuple[int, int] = (40, 300)
    grid_levels: tuple[int, int] = (1, 4)
    auto_refine: str = "auto"
    final_resolution: tuple[str, str] = ("2.5e-4", "2.5e-4")


GUI_DEFAULT_PERPLEX_OPTIONS = GuiPerplexOptions()


def gui_boolean_option_from_config(value: object, *, field_name: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().upper()
        if normalized in {"T", "TRUE", "Y", "YES", "1"}:
            return True
        if normalized in {"F", "FALSE", "N", "NO", "0"}:
            return False
    raise ValueError(f"{field_name} must be True or False; legacy T/F values are also accepted.")


def gui_integer_pair_from_config(value: object, *, field_name: str, minimum: int = 2) -> tuple[int, int]:
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


def gui_string_pair_from_config(value: object, *, field_name: str) -> tuple[str, str]:
    if isinstance(value, str):
        parts = value.replace(",", " ").split()
    elif isinstance(value, (list, tuple)):
        parts = [str(item) for item in value]
    else:
        raise ValueError(f"{field_name} must be a two-item list or string.")
    if len(parts) != 2:
        raise ValueError(f"{field_name} must contain exactly two values.")
    return str(parts[0]), str(parts[1])


def gui_perplex_options_from_config(
    value: object,
    fallback: GuiPerplexOptions = GUI_DEFAULT_PERPLEX_OPTIONS,
) -> GuiPerplexOptions:
    if value is None:
        return fallback
    if not isinstance(value, dict):
        raise ValueError("perplex_options must be a JSON object.")

    sample_on_grid = fallback.sample_on_grid
    if "sample_on_grid" in value:
        sample_on_grid = gui_boolean_option_from_config(value["sample_on_grid"], field_name="sample_on_grid")

    return GuiPerplexOptions(
        sample_on_grid=sample_on_grid,
        x_nodes=gui_integer_pair_from_config(value.get("x_nodes", list(fallback.x_nodes)), field_name="x_nodes"),
        y_nodes=gui_integer_pair_from_config(value.get("y_nodes", list(fallback.y_nodes)), field_name="y_nodes"),
        grid_levels=gui_integer_pair_from_config(
            value.get("grid_levels", list(fallback.grid_levels)),
            field_name="grid_levels",
            minimum=1,
        ),
        auto_refine=str(value.get("auto_refine", fallback.auto_refine)).strip() or fallback.auto_refine,
        final_resolution=gui_string_pair_from_config(
            value.get("final_resolution", list(fallback.final_resolution)),
            field_name="final_resolution",
        ),
    )


def model_perplex_options(model: dict[str, Any], config: dict[str, Any]) -> GuiPerplexOptions:
    default_options = gui_perplex_options_from_config(config.get("perplex_options"))
    return gui_perplex_options_from_config(
        model.get("perplex_options"),
        fallback=default_options,
    )


def perplex_options_config(options: GuiPerplexOptions) -> dict[str, Any]:
    return {
        "sample_on_grid": options.sample_on_grid,
        "x_nodes": list(options.x_nodes),
        "y_nodes": list(options.y_nodes),
        "grid_levels": list(options.grid_levels),
        "auto_refine": options.auto_refine,
        "final_resolution": list(options.final_resolution),
    }


def show_model_database_configuration(
    config_path: Path,
    config: dict[str, Any],
    models: list[dict[str, Any]],
    selected_projects: list[str],
) -> None:
    """Show per-model database and template configuration."""
    from planetary_eos_lab.core.config_io import save_config_json
    from planetary_eos_lab.core.database_utils import list_available_databases

    st.caption(
        "Configure database, BUILD template, and Perple_X grid options for each selected model. "
        "Changes are saved to configs/models.json and persist across all pipeline steps and future sessions."
    )

    databases = list_available_databases()
    config_changed = False

    for project in selected_projects:
        model = model_by_project(models, project)
        if model is None:
            continue

        model_db = model.get("database", config.get("database", "stx21"))
        model_template = model.get("build_template_file", "")
        current_options = model_perplex_options(model, config)
        has_explicit_config = (
            "database" in model
            and ("build_template_file" in model or model_db in DEFAULT_BUILD_TEMPLATES)
            and "perplex_options" in model
        )
        config_status = "Configured" if has_explicit_config else "Using defaults"

        with st.container(border=True):
            st.markdown(f"**{project}**")
            st.caption(config_status)
            feedback_key = f"model_setup_feedback_{project}"
            saved_feedback = st.session_state.pop(feedback_key, None)
            if saved_feedback:
                st.success(str(saved_feedback))

            col1, col2 = st.columns([1, 1])

            with col1:
                new_db = st.selectbox(
                    "Database",
                    options=databases,
                    index=databases.index(model_db) if model_db in databases else 0,
                    key=f"model_db_{project}",
                    help=f"Thermodynamic database for {project}",
                )

                if new_db != model_db:
                    st.info(f"Database will change from `{model_db}` to `{new_db}`")

            template_error = None
            selected_template = ""
            with col2:
                default_template = DEFAULT_BUILD_TEMPLATES.get(new_db, "")
                bundled_templates = [
                    template
                    for template in available_build_templates()
                    if not build_template_matches_database_default(template, new_db)
                ]
                template_options = []
                if default_template:
                    template_options.append(BUILD_TEMPLATE_DEFAULT_CHOICE)
                template_options.extend(bundled_templates)
                template_options.append(BUILD_TEMPLATE_CUSTOM_CHOICE)

                normalized_model_template = normalize_build_template_path(model_template)
                using_database_default = model_uses_database_default_template(
                    normalized_model_template,
                    model_db,
                    new_db,
                )
                if using_database_default and default_template:
                    current_template_choice = BUILD_TEMPLATE_DEFAULT_CHOICE
                elif normalized_model_template in bundled_templates:
                    current_template_choice = normalized_model_template
                else:
                    current_template_choice = BUILD_TEMPLATE_CUSTOM_CHOICE
                if current_template_choice not in template_options:
                    current_template_choice = BUILD_TEMPLATE_CUSTOM_CHOICE

                def template_choice_label(choice: str) -> str:
                    if choice == BUILD_TEMPLATE_DEFAULT_CHOICE:
                        return f"Use database default: {Path(default_template).name}"
                    if choice == BUILD_TEMPLATE_CUSTOM_CHOICE:
                        return "Custom template path..."
                    return build_template_label(choice, selected_database=new_db)

                new_template_choice = st.selectbox(
                    "BUILD Template",
                    options=template_options,
                    index=template_options.index(current_template_choice),
                    key=f"model_template_choice_{project}_{new_db}",
                    help=(
                        "Choose the BUILD input template for this model. "
                        "Use database default keeps the template matched to the selected thermodynamic database."
                    ),
                    format_func=template_choice_label,
                )

                if new_template_choice == BUILD_TEMPLATE_DEFAULT_CHOICE:
                    selected_template = ""
                    if default_template:
                        st.caption(f"Matched to `{new_db}`: `{default_template}`")
                    else:
                        template_error = f"No default BUILD template is configured for `{new_db}`."
                        st.error(template_error)
                elif new_template_choice == BUILD_TEMPLATE_CUSTOM_CHOICE:
                    custom_default = "" if using_database_default else normalized_model_template
                    selected_template = normalize_build_template_path(
                        st.text_input(
                            "Custom BUILD template path",
                            value=custom_default,
                            key=f"model_template_custom_{project}_{new_db}",
                            help="Use a repo-relative path or an absolute path to a custom BUILD input file.",
                            placeholder=default_template,
                        )
                    )
                    if not selected_template:
                        template_error = "Custom BUILD template path cannot be empty."
                        st.error(template_error)
                else:
                    selected_template = new_template_choice
                    template_database = build_template_database(selected_template)
                    if template_database and template_database != new_db:
                        st.warning(
                            f"`{selected_template}` is the default template for `{template_database}`, "
                            f"not `{new_db}`."
                        )
                    else:
                        st.caption(f"Explicit template override: `{selected_template}`")

                previous_effective_template = "" if using_database_default else normalized_model_template
                if selected_template != previous_effective_template:
                    if selected_template:
                        st.info(f"Template will change to `{selected_template}`")
                    else:
                        st.info(f"Template will follow the `{new_db}` database default.")

            st.divider()
            st.markdown("**Perple_X grid options**")
            st.caption(
                "`sample_on_grid` controls whether Perple_X samples exactly on the requested grid. "
                "The final `perplex_option.dat` still uses Perple_X's required T/F syntax."
            )
            grid_col1, grid_col2, grid_col3 = st.columns([0.85, 1, 1])
            with grid_col1:
                sample_on_grid_value = st.radio(
                    "sample_on_grid",
                    options=["False", "True"],
                    index=1 if current_options.sample_on_grid else 0,
                    horizontal=True,
                    key=f"model_sample_on_grid_{project}",
                    help=(
                        "False allows Perple_X adaptive refinement. "
                        "True samples directly on the fixed grid you request."
                    ),
                )
                if sample_on_grid_value == "False":
                    st.caption("False: allow Perple_X adaptive refinement.")
                else:
                    st.caption("True: sample only on the requested grid.")
            with grid_col2:
                x_min = st.number_input(
                    "x nodes min",
                    min_value=2,
                    value=int(current_options.x_nodes[0]),
                    step=1,
                    key=f"model_x_nodes_min_{project}",
                )
                x_max = st.number_input(
                    "x nodes max",
                    min_value=2,
                    value=int(current_options.x_nodes[1]),
                    step=1,
                    key=f"model_x_nodes_max_{project}",
                )
            with grid_col3:
                y_min = st.number_input(
                    "y nodes min",
                    min_value=2,
                    value=int(current_options.y_nodes[0]),
                    step=1,
                    key=f"model_y_nodes_min_{project}",
                )
                y_max = st.number_input(
                    "y nodes max",
                    min_value=2,
                    value=int(current_options.y_nodes[1]),
                    step=1,
                    key=f"model_y_nodes_max_{project}",
                )

            grid_error = None
            if x_min > x_max:
                grid_error = "x nodes min cannot be larger than x nodes max."
            elif y_min > y_max:
                grid_error = "y nodes min cannot be larger than y nodes max."
            if grid_error:
                st.error(grid_error)
            else:
                st.caption(f"Requested grid upper bound: {int(x_max) * int(y_max):,} points")
                if sample_on_grid_value == "False":
                    st.warning(
                        "This is an adaptive Perple_X run. Even with 40 x 40 nodes, Perple_X may refine beyond "
                        "that grid because `sample_on_grid` is False and grid levels remain adaptive. "
                        "Choose True for a strict fixed-grid test."
                    )
                else:
                    st.success("Strict fixed-grid test: Perple_X will write `sample_on_grid T` and `grid_levels 1 1`.")

            new_perplex_options = GuiPerplexOptions(
                sample_on_grid=sample_on_grid_value == "True",
                x_nodes=(int(x_min), int(x_max)),
                y_nodes=(int(y_min), int(y_max)),
                grid_levels=(1, 1) if sample_on_grid_value == "True" else current_options.grid_levels,
                auto_refine=current_options.auto_refine,
                final_resolution=current_options.final_resolution,
            )

            has_setup_error = grid_error is not None or template_error is not None
            if st.button(f"Apply setup to {project}", key=f"save_model_config_{project}", disabled=has_setup_error):
                # Update the model in config
                for i, m in enumerate(config["models"]):
                    if m.get("project") == project:
                        config["models"][i]["database"] = new_db
                        if selected_template and not build_template_matches_database_default(selected_template, new_db):
                            config["models"][i]["build_template_file"] = selected_template
                        elif "build_template_file" in config["models"][i]:
                            del config["models"][i]["build_template_file"]
                        config["models"][i]["perplex_options"] = perplex_options_config(new_perplex_options)
                        config_changed = True
                        break

                if config_changed:
                    st.session_state[feedback_key] = f"Setup saved for {project}."
                    save_config_json(config_path, config)
                    st.rerun()


def show_selected_model_reviews(
    models: list[dict[str, Any]],
    selected_projects: list[str],
    database: str,
) -> None:
    if not selected_projects:
        st.info("Select one or more saved models to review their composition before generating files.")
        return

    for project in selected_projects:
        model = model_by_project(models, project)
        if model is None:
            continue
        model_has_database = bool(model.get("database"))
        model_database = model.get("database", database)
        with st.expander(f"{project}: composition review", expanded=len(selected_projects) == 1):
            if model_has_database:
                st.caption(f"Thermodynamic model for this file: `{model_database}`")
            else:
                st.warning(
                    f"No per-file thermodynamic model is saved for this file yet. "
                    f"Set one in Thermodynamic Setup; using `{model_database}` only as a temporary review fallback."
                )
            show_scientific_guardrail(model, database=model_database)
            if safe_component_composition(model) is not None:
                st.metric("Input component total, wt%", f"{model_input_total(model):.2f}")
                show_component_table(component_table_rows(model, model_database))
            else:
                st.metric("Input oxide total, wt%", f"{raw_total(model):.2f}")
                show_oxide_table(oxide_table_rows(model, database=model_database), database=model_database)
                omitted = omitted_oxides_for_model(model, database=model_database)
                if omitted:
                    st.warning(
                        f"These oxides are present in the composition record but omitted from {model_database} BUILD: "
                        + ", ".join(str(item["oxide"]) for item in omitted)
                    )
            st.caption(f"Active {model_database} BUILD components")
            st.code(active_component_text(model_database), language="text")


def readable_catalog_value(value: Any, fallback: str = "Not specified", *, humanize: bool = True) -> str:
    text = str(value or "").strip()
    if not text:
        return fallback
    return text.replace("_", " ") if humanize else text


def model_catalog_basis(model: dict[str, Any]) -> str:
    return "components" if safe_component_composition(model) is not None else "oxides"


def model_catalog_database(model: dict[str, Any], fallback_database: str) -> str:
    return str(model.get("database") or fallback_database)


def model_catalog_build_template(model: dict[str, Any], database: str) -> str:
    return str(model.get("build_template_file") or DEFAULT_BUILD_TEMPLATES.get(database, "database default"))


def model_catalog_composition_rows(model: dict[str, Any], database: str) -> list[dict[str, Any]]:
    try:
        if safe_component_composition(model) is not None:
            rows = []
            for row in component_table_rows(model, database):
                input_value = float(row["your input wt%"])
                normalized_value = float(row["normalized to 100 wt%"])
                if abs(input_value) <= 1.0e-12 and abs(normalized_value) <= 1.0e-12:
                    continue
                rows.append(
                    {
                        "input": row["component"],
                        "input wt%": input_value,
                        "normalized wt%": normalized_value,
                        "role": row[f"{database} role"],
                    }
                )
            return rows

        rows = []
        for row in oxide_table_rows(model, database=database):
            input_value = float(row["raw_wt_percent"])
            normalized_value = float(row["normalized_wt_percent"])
            if abs(input_value) <= 1.0e-12 and abs(normalized_value) <= 1.0e-12:
                continue
            rows.append(
                {
                    "input": row["oxide"],
                    "input wt%": input_value,
                    "normalized wt%": normalized_value,
                    "role": row["build_role"],
                }
            )
        return rows
    except (TypeError, ValueError):
        return []


def model_catalog_main_inputs(model: dict[str, Any], database: str, *, limit: int = 5) -> str:
    rows = sorted(
        model_catalog_composition_rows(model, database),
        key=lambda row: abs(float(row["normalized wt%"])),
        reverse=True,
    )
    if not rows:
        return "No nonzero inputs"
    parts = [f"{row['input']} {float(row['normalized wt%']):.1f} wt%" for row in rows[:limit]]
    if len(rows) > limit:
        parts.append(f"{len(rows) - limit} more")
    return ", ".join(parts)


def model_catalog_validation_text(model: dict[str, Any]) -> str:
    validation = validate_model_entry(model)
    if validation.ok:
        return "OK"
    return "; ".join(validation.errors)


def model_catalog_at_a_glance_rows(
    models: list[dict[str, Any]],
    selected_project: str | list[str] | tuple[str, ...] | set[str] | None = None,
    database: str = "stx21",
) -> list[dict[str, Any]]:
    selected_projects = selected_project_names(selected_project)
    rows: list[dict[str, Any]] = []
    for model in models:
        project = str(model.get("project", ""))
        model_database = model_catalog_database(model, database)
        try:
            input_total = round(model_input_total(model), 2)
        except (TypeError, ValueError):
            input_total = None
        rows.append(
            {
                "selected": "yes" if project in selected_projects else "",
                "project": project,
                "what it represents": readable_catalog_value(
                    model.get("description") or model.get("composition_interpretation")
                ),
                "thermodynamic model": model_database,
                "basis": model_catalog_basis(model),
                "input total wt%": input_total,
                "main inputs": model_catalog_main_inputs(model, model_database),
                "readiness": readable_catalog_value(model.get("planetprofile_readiness")),
                "final EOS": "yes" if use_as_final_moon_mantle_eos(model) else "no",
                "validation": model_catalog_validation_text(model),
            }
        )
    return rows


def show_model_catalog_summary_card(
    model: dict[str, Any],
    *,
    database: str,
    expanded: bool,
) -> None:
    project = str(model.get("project", ""))
    model_database = model_catalog_database(model, database)
    description = readable_catalog_value(model.get("description"), fallback="Saved composition")
    validation = validate_model_entry(model)
    validation_label = "OK" if validation.ok else "Needs fixes"
    heading = f"{project} - {description}"
    try:
        input_total = f"{model_input_total(model):.2f} wt%"
    except (TypeError, ValueError):
        input_total = "unknown"

    with st.expander(heading, expanded=expanded):
        interpretation = readable_catalog_value(
            model.get("composition_interpretation") or model.get("description")
        )
        st.markdown("**What this model represents**")
        st.write(interpretation)

        fact_col1, fact_col2, fact_col3, fact_col4 = st.columns(4)
        fact_col1.metric("Thermodynamic model", model_database)
        fact_col2.metric("Composition basis", model_catalog_basis(model))
        fact_col3.metric("Input total", input_total)
        fact_col4.metric("Validation", validation_label)

        setup_col, readiness_col = st.columns([1, 1])
        with setup_col:
            st.markdown("**Modeling setup**")
            st.write(f"BUILD template: `{model_catalog_build_template(model, model_database)}`")
            st.caption("Inputs passed to BUILD")
            st.code(active_component_text(model_database), language="text")
            source_only = get_source_only_oxides(model_database)
            if source_only:
                st.caption("Tracked but source-only for this thermodynamic model")
                st.write(", ".join(source_only))
        with readiness_col:
            st.markdown("**Readiness and provenance**")
            st.write(f"Scientific status: {readable_catalog_value(model.get('scientific_status'))}")
            st.write(f"Model scope: {readable_catalog_value(model.get('model_scope'))}")
            st.write(f"PlanetProfile readiness: {readable_catalog_value(model.get('planetprofile_readiness'))}")
            st.write(f"Literature proxy: {'yes' if model.get('literature_proxy') else 'no'}")
            st.write(f"Use as final scientific EOS: {'yes' if use_as_final_moon_mantle_eos(model) else 'no'}")
            planetprofile_filename = readable_catalog_value(
                model.get("planetprofile_filename"),
                humanize=False,
            )
            st.write(f"PlanetProfile table: `{planetprofile_filename}`")

        if not validation.ok:
            st.error("Validation errors: " + "; ".join(validation.errors))
        for warning in validation.warnings:
            st.warning(warning)

        try:
            omitted = [] if safe_component_composition(model) is not None else omitted_oxides_for_model(model, database=model_database)
        except (TypeError, ValueError):
            omitted = []
        if omitted:
            st.warning(
                f"Source-only for {model_database}: "
                + ", ".join(f"{item['oxide']}={item['normalized_wt_percent']:.2f} wt%" for item in omitted)
            )

        st.markdown("**Nonzero composition inputs**")
        st.dataframe(
            model_catalog_composition_rows(model, model_database),
            width="stretch",
            hide_index=True,
            column_config={
                "input wt%": st.column_config.NumberColumn(format="%.2f"),
                "normalized wt%": st.column_config.NumberColumn(format="%.2f"),
            },
        )

        source_note = readable_catalog_value(model.get("source_note"))
        if source_note != "Not specified":
            st.markdown("**Source note**")
            st.write(source_note)


def show_model_catalog(
    models: list[dict[str, Any]],
    selected_project: str | list[str] | tuple[str, ...] | set[str] | None = None,
    database: str = "stx21",
) -> None:
    st.caption("At a glance")
    st.dataframe(
        model_catalog_at_a_glance_rows(models, selected_project, database=database),
        width="stretch",
        hide_index=True,
        column_config={
            "input total wt%": st.column_config.NumberColumn(format="%.2f"),
        },
    )

    selected_projects = selected_project_names(selected_project)
    st.caption("Model details")
    for index, model in enumerate(models):
        project = str(model.get("project", ""))
        expanded = project in selected_projects or (not selected_projects and index == 0)
        show_model_catalog_summary_card(model, database=database, expanded=expanded)

    with st.expander("Spreadsheet view: metadata and raw values"):
        st.dataframe(
            compact_model_overview_rows(models, selected_project, database=database),
            width="stretch",
            hide_index=True,
            column_config={
                "input total wt%": st.column_config.NumberColumn(format="%.2f"),
            },
        )
        st.dataframe(
            detailed_model_overview_rows(models, selected_project, database=database),
            width="stretch",
            hide_index=True,
            column_config={
                "input total wt%": st.column_config.NumberColumn(format="%.2f"),
                **{
                    f"{oxide} wt%": st.column_config.NumberColumn(format="%.2f")
                    for oxide in OXIDE_ORDER
                },
            },
        )


def format_pressure_range(pt_range: dict[str, dict[str, float]]) -> str:
    pressure = pt_range.get("pressure_bar", {})
    p_min = float(pressure.get("min", 0.0))
    p_max = float(pressure.get("max", 0.0))
    return f"{p_min:g}-{p_max:g} bar ({p_min / 10000:g}-{p_max / 10000:g} GPa)"


def format_temperature_range(pt_range: dict[str, dict[str, float]]) -> str:
    temperature = pt_range.get("temperature_k", {})
    t_min = float(temperature.get("min", 0.0))
    t_max = float(temperature.get("max", 0.0))
    return f"{t_min:g}-{t_max:g} K"


def thermodynamic_model_catalog_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for database, db in DATABASES.items():
        components = get_database_components(database)
        source_only = get_source_only_oxides(database)
        input_basis = "components" if database_uses_component_inputs(database) else "oxides"
        rows.append(
            {
                "thermodynamic model": database,
                "best for": THERMODYNAMIC_MODEL_USE_CASES.get(database, db.description),
                "input basis": input_basis,
                "modeled inputs": ", ".join(component for _, component in components),
                "source-only oxides": ", ".join(source_only) if source_only else "none",
                "P range": format_pressure_range(db.pt_range),
                "T range": format_temperature_range(db.pt_range),
                "database file": db.database_file,
                "solution model file": db.solution_model_file,
            }
        )
    return rows


def show_thermodynamic_model_catalog() -> None:
    st.subheader("Thermodynamic Model Catalog")
    st.caption(
        "Use this as a quick guide for choosing the database/template setup before building or running a composition."
    )
    st.dataframe(
        thermodynamic_model_catalog_rows(),
        width="stretch",
        hide_index=True,
    )

    database_names = list(DATABASES)
    selected_database = st.selectbox(
        "Detailed setup",
        options=database_names,
        format_func=lambda database: f"{database}: {DATABASES[database].description}",
    )
    st.code(describe_database(selected_database), language="text")


def single_composition_figure(values: dict[str, float], *, x_title: str) -> go.Figure:
    labels = [label for label, value in values.items() if math.isfinite(float(value)) and abs(float(value)) > 1.0e-12]
    if not labels:
        labels = list(values)
    y_values = [float(values.get(label, 0.0)) for label in labels]
    fig = go.Figure(
        data=[
            go.Bar(
                x=labels,
                y=y_values,
                marker_color="#1f6f8b",
                hovertemplate="%{x}: %{y:.2f} wt%<extra></extra>",
            )
        ]
    )
    fig.update_layout(
        title="Normalized composition",
        xaxis_title=x_title,
        yaxis_title="wt%",
        yaxis=dict(range=[0, 100]),
        height=420,
        margin=dict(l=56, r=20, t=64, b=86),
    )
    return fig


@st.dialog("Confirm Model Deletion")
def confirm_delete_model_dialog(config_path: Path, config: dict[str, Any], project_to_delete: str) -> None:
    st.warning(f"Delete `{project_to_delete}` from `configs/models.json`?")
    st.caption(
        "Generated composition files, Perple_X work folders, and exported PlanetProfile tables will not be removed."
    )
    cancel_col, delete_col = st.columns(2)
    with cancel_col:
        if st.button("Cancel", width="stretch"):
            st.session_state.pop("delete_model_dialog_project", None)
            st.rerun()
    with delete_col:
        if st.button("Delete model", type="primary", width="stretch"):
            updated_config = delete_model_entry(config, project_to_delete)
            save_config_json(config_path, updated_config)
            st.session_state.pop("delete_model_dialog_project", None)
            st.session_state["delete_model_notice"] = (
                f"Deleted `{project_to_delete}` from config. Generated output files were not removed."
            )
            st.rerun()


@st.dialog("Confirm Model Deletion")
def confirm_delete_models_dialog(config_path: Path, config: dict[str, Any], projects_to_delete: list[str]) -> None:
    projects = [project for project in projects_to_delete if project]
    st.warning(f"Delete {len(projects)} saved model(s) from `configs/models.json`?")
    for project in projects:
        st.write(f"- `{project}`")
    st.caption(
        "Generated composition files, Perple_X work folders, and exported PlanetProfile tables will not be removed."
    )
    cancel_col, delete_col = st.columns(2)
    with cancel_col:
        if st.button("Cancel", width="stretch", key="cancel_multi_delete"):
            st.session_state.pop("delete_model_dialog_projects", None)
            st.rerun()
    with delete_col:
        if st.button("Delete models", type="primary", width="stretch", key="confirm_multi_delete"):
            updated_config = delete_model_entries(config, projects)
            save_config_json(config_path, updated_config)
            st.session_state.pop("delete_model_dialog_projects", None)
            st.session_state["delete_model_notice"] = (
                f"Deleted {len(projects)} saved model(s) from config. Generated output files were not removed."
            )
            st.rerun()


def delete_model_panel(
    config_path: Path,
    config: dict[str, Any],
    models: list[dict[str, Any]],
    selected_project: str | None = None,
) -> None:
    st.subheader("Delete Saved Model(s)")
    st.caption(
        "This removes a model block from `configs/models.json` only. "
        "Generated composition files, Perple_X work folders, and exported tables are left untouched."
    )
    if len(models) <= 1:
        st.warning("At least one saved model must remain in the config.")
        return

    available_projects = project_options(models)
    projects_to_delete = st.multiselect(
        "Saved models to delete",
        options=available_projects,
        default=[],
        key="delete_model_projects",
        format_func=lambda project: model_label(next(model for model in models if model.get("project") == project)),
    )
    if not projects_to_delete:
        st.info("Select one or more saved models to delete.")
    too_many = len(projects_to_delete) >= len(models)
    if too_many:
        st.error("At least one saved model must remain in the config.")
    if st.button("Delete selected model(s)", type="secondary", disabled=not projects_to_delete or too_many):
        st.session_state["delete_model_dialog_projects"] = projects_to_delete

    pending_delete = st.session_state.get("delete_model_dialog_project")
    if isinstance(pending_delete, str) and pending_delete:
        confirm_delete_model_dialog(config_path, config, pending_delete)
    pending_delete_projects = st.session_state.get("delete_model_dialog_projects")
    if isinstance(pending_delete_projects, list) and pending_delete_projects:
        confirm_delete_models_dialog(config_path, config, pending_delete_projects)


def set_workflow_step(index: int) -> None:
    bounded = max(0, min(index, len(PIPELINE_STEPS) - 1))
    st.session_state["workflow_step_index"] = bounded
    st.session_state["workflow_step_choice"] = PIPELINE_STEPS[bounded]
    st.session_state[PIPELINE_STEP_CONTROL_KEY] = PIPELINE_STEPS[bounded]


def set_workflow_step_from_control() -> None:
    selected_step = st.session_state.get(PIPELINE_STEP_CONTROL_KEY)
    if selected_step in PIPELINE_STEPS:
        set_workflow_step(PIPELINE_STEPS.index(str(selected_step)))


def set_composition_page(index: int) -> None:
    bounded = max(0, min(index, len(COMPOSITION_PAGES) - 1))
    st.session_state["composition_page_index"] = bounded
    st.session_state["composition_page_choice"] = COMPOSITION_PAGES[bounded]
    st.session_state[COMPOSITION_PAGE_CONTROL_KEY] = COMPOSITION_PAGES[bounded]


def set_composition_page_from_control() -> None:
    selected_page = st.session_state.get(COMPOSITION_PAGE_CONTROL_KEY)
    if selected_page in COMPOSITION_PAGES:
        set_composition_page(COMPOSITION_PAGES.index(str(selected_page)))


def set_workspace_mode(mode: str) -> None:
    st.session_state["workspace_mode"] = mode


def open_composition_page(index: int) -> None:
    st.session_state["workspace_mode"] = COMPOSITION_BUILDER_MODE
    set_composition_page(index)


def open_pipeline_step(index: int) -> None:
    st.session_state["workspace_mode"] = PIPELINE_MODE
    set_workflow_step(index)


def command_progress_label(command: PipelineCommand, index: int, total: int) -> str:
    remaining = total - index
    suffix = f"{remaining} left" if remaining else "last run"
    return f"{index}/{total} {command.label} ({suffix})"


def append_command_log(log_path: Path, text: str) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as log_file:
        log_file.write(text)


def command_log_tail(log_path: Path, max_bytes: int = 24000) -> str:
    if not log_path.exists():
        return ""
    with log_path.open("rb") as log_file:
        log_file.seek(0, os.SEEK_END)
        size = log_file.tell()
        log_file.seek(max(0, size - max_bytes))
        return log_file.read().decode("utf-8", errors="replace")


def command_log_current_section(log_text: str) -> str:
    sections = log_text.split("\n\n=== ")
    return sections[-1] if sections else log_text


def streamlit_job_is_running() -> bool:
    job = st.session_state.get(RUNNING_COMMAND_JOB_KEY)
    return isinstance(job, dict) and job.get("status") == "running"


def launch_current_streamlit_command() -> None:
    job = st.session_state.get(RUNNING_COMMAND_JOB_KEY)
    if not isinstance(job, dict):
        return
    commands = job.get("commands", [])
    index = int(job.get("index", 0))
    if index >= len(commands):
        job["status"] = "complete"
        job["message"] = f"Finished {job.get('completed', 0)}/{len(commands)} run(s)."
        return

    command = commands[index]
    total = len(commands)
    label = command_progress_label(command, index + 1, total)
    log_path = Path(str(job["log_path"]))
    append_command_log(
        log_path,
        f"\n\n=== {label} ===\n$ {command.display}\n",
    )
    try:
        with log_path.open("a", encoding="utf-8") as log_file:
            process = subprocess.Popen(
                command.command,
                cwd=str(command.cwd),
                stdout=log_file,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                start_new_session=True,
            )
    except OSError as exc:
        job["status"] = "failed"
        job["message"] = f"Could not start {label}: {exc}"
        append_command_log(log_path, f"Could not start command: {exc}\n")
        return

    job["process"] = process
    job["current_label"] = label
    job["message"] = f"Running {label}"


def start_streamlit_command_job(commands: list[PipelineCommand], *, job_label: str) -> None:
    if not commands:
        return
    if streamlit_job_is_running():
        st.warning("A command is already running. Kill or finish it before starting another one.")
        return

    timestamp = time.strftime("%Y%m%d-%H%M%S")
    log_path = REPO_ROOT / "outputs" / "streamlit_runs" / f"{job_label.lower().replace(' ', '_')}_{timestamp}.log"
    job = {
        "job_label": job_label,
        "commands": commands,
        "index": 0,
        "completed": 0,
        "status": "running",
        "message": "",
        "current_label": "",
        "log_path": str(log_path),
        "process": None,
    }
    st.session_state[RUNNING_COMMAND_JOB_KEY] = job
    launch_current_streamlit_command()
    st.rerun()


def poll_streamlit_command_job() -> dict[str, Any] | None:
    job = st.session_state.get(RUNNING_COMMAND_JOB_KEY)
    if not isinstance(job, dict):
        return None
    if job.get("status") != "running":
        return job

    process = job.get("process")
    if process is None:
        launch_current_streamlit_command()
        return job

    returncode = process.poll()
    if returncode is None:
        return job

    log_path = Path(str(job["log_path"]))
    append_command_log(log_path, f"\nCommand exited with return code {returncode}.\n")
    job["process"] = None
    if returncode == 0:
        job["completed"] = int(job.get("completed", 0)) + 1
        job["index"] = int(job.get("index", 0)) + 1
        commands = job.get("commands", [])
        if int(job["index"]) >= len(commands):
            job["status"] = "complete"
            job["message"] = f"Finished {job['completed']}/{len(commands)} run(s)."
        else:
            launch_current_streamlit_command()
        return job

    job["status"] = "failed"
    job["message"] = f"Stopped after {job.get('completed', 0)}/{len(job.get('commands', []))} completed run(s)."
    return job


def terminate_streamlit_command_job() -> None:
    job = st.session_state.get(RUNNING_COMMAND_JOB_KEY)
    if not isinstance(job, dict) or job.get("status") != "running":
        return
    process = job.get("process")
    if process is not None and process.poll() is None:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except (AttributeError, ProcessLookupError, OSError):
            process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except (AttributeError, ProcessLookupError, OSError):
                process.kill()
            process.wait(timeout=5)

    job["status"] = "killed"
    job["message"] = "Run killed by user."
    job["process"] = None
    append_command_log(Path(str(job["log_path"])), "\nRun killed by user.\n")


def command_stage_plan(command: PipelineCommand | None) -> list[tuple[str, tuple[str, ...]]]:
    if command is None:
        return [("Starting", ())]

    label = command.label
    command_text = " ".join(command.command)
    if "run_full_pipeline.py" in command_text or label.startswith("Run pipeline:"):
        stages = [
            ("Generate composition files", ("Generating compositions",)),
            ("Prepare Perple_X input", ("Running Perple_X pipeline", "perplex_option.dat")),
            ("BUILD", ("Running BUILD for",)),
            ("VERTEX", ("Running VERTEX for",)),
            ("WERAMI", ("Running WERAMI for",)),
            ("Validate output", ("STATUS: PASS", "STATUS: FAIL", "Validation skipped")),
            ("Generate comparison plots", ("Generating comparison plots",)),
        ]
        if "--export-planetprofile" in command.command:
            stages.append(("Export PlanetProfile tables", ("Exporting PlanetProfile tables", "Exported ")))
        return stages

    if "make_compositions.py" in command_text or label.startswith("Generate files:"):
        return [("Generate composition files", ("Wrote ", "No inline compositions to generate"))]

    if "export_planetprofile.py" in command_text or label.startswith("Export "):
        return [("Export PlanetProfile tables", ("Exported ", "Wrote "))]

    return [(label, ())]


def detected_command_stage(
    log_text: str,
    stages: list[tuple[str, tuple[str, ...]]],
) -> tuple[int, str]:
    if not stages:
        return 0, "Starting"

    section = command_log_current_section(log_text)
    detected_index = -1
    for stage_index, (_stage_label, markers) in enumerate(stages):
        if any(marker and marker in section for marker in markers):
            detected_index = stage_index

    if detected_index < 0:
        return 0, "Starting command"
    return detected_index, stages[detected_index][0]


def current_job_command(job: dict[str, Any]) -> PipelineCommand | None:
    commands = job.get("commands", [])
    index = int(job.get("index", 0))
    if not isinstance(commands, list) or not commands or index >= len(commands):
        return None
    command = commands[index]
    return command if isinstance(command, PipelineCommand) else None


def command_job_progress(job: dict[str, Any], log_text: str = "") -> tuple[float, str]:
    commands = job.get("commands", [])
    total = max(len(commands), 1)
    completed = max(0, min(int(job.get("completed", 0)), total))
    status = str(job.get("status", "running"))

    if status == "complete":
        return 1.0, f"Completed {completed}/{total} run(s)."

    progress = completed / total
    if status == "running":
        current = min(max(int(job.get("index", 0)) + 1, 1), total)
        command = current_job_command(job)
        stages = command_stage_plan(command)
        stage_index, stage_label = detected_command_stage(log_text, stages)
        stage_count = max(len(stages), 1)
        progress = (completed + ((stage_index + 1) / stage_count)) / total
        project = command.label.split(":", 1)[1].strip() if command and ":" in command.label else ""
        project_text = f"{project}: " if project else ""
        return (
            progress,
            f"{project_text}{stage_label} (stage {stage_index + 1}/{stage_count}); "
            f"file {current}/{total}, completed {completed}/{total}.",
        )

    return progress, f"Stopped after {completed}/{total} completed run(s)."


def show_indeterminate_running_bar() -> None:
    st.markdown(
        '<style>'
        '@keyframes pelRunBar{0%{left:-42%;}100%{left:100%;}}'
        '.pel-running-bar{position:relative;height:0.55rem;overflow:hidden;'
        'border-radius:999px;background:rgba(31,119,180,0.14);'
        'border:1px solid rgba(31,119,180,0.22);margin:0.25rem 0 0.65rem 0;}'
        '.pel-running-bar::before{content:"";position:absolute;top:0;bottom:0;left:-42%;'
        'width:42%;border-radius:999px;background:#1f77b4;'
        'animation:pelRunBar 1.15s linear infinite;}'
        '</style>'
        '<div class="pel-running-bar" role="progressbar" aria-label="Run in progress"></div>',
        unsafe_allow_html=True,
    )


def show_command_progress_bar(job: dict[str, Any], log_text: str = "") -> None:
    status = str(job.get("status", "running"))
    progress, progress_text = command_job_progress(job, log_text)
    st.progress(progress, text=progress_text)
    if status == "running":
        show_indeterminate_running_bar()


def show_streamlit_command_job() -> None:
    job = poll_streamlit_command_job()
    if not isinstance(job, dict):
        return

    status = str(job.get("status", "running"))
    state = "running" if status == "running" else "complete" if status == "complete" else "error"
    label = str(job.get("message") or job.get("current_label") or job.get("job_label", "Command"))
    with st.status(label, state=state, expanded=status != "complete"):
        log_path = Path(str(job["log_path"]))
        log_text = command_log_tail(log_path)
        show_command_progress_bar(job, log_text)
        if status == "running":
            if st.button("Kill run", type="secondary", key="kill_streamlit_running_job"):
                terminate_streamlit_command_job()
                st.rerun()
        st.caption(f"Log file: `{log_path}`")
        if log_text:
            st.code(log_text, language="text")
        else:
            st.caption("Waiting for command output...")
        if status != "running" and st.button("Clear run status", key="clear_streamlit_command_job"):
            del st.session_state[RUNNING_COMMAND_JOB_KEY]
            st.rerun()

    if status == "running":
        time.sleep(1)
        st.rerun()


def run_streamlit_commands(commands: list[PipelineCommand], *, job_label: str = "Pipeline run") -> None:
    start_streamlit_command_job(commands, job_label=job_label)


def editable_model_form(config_path: Path, config: dict[str, Any], model: dict[str, Any]) -> None:
    database = get_current_database(config)
    validation = validate_model_entry(model)
    if validation.errors:
        st.error("Current model has validation errors: " + "; ".join(validation.errors))
    for warning in validation.warnings:
        st.warning(warning)

    rows = oxide_table_rows(model, database=database)
    show_oxide_table(rows, database=database)
    omitted = omitted_oxides_for_model(model, database=database)
    if omitted:
        st.warning(
            f"Omitted from {database} BUILD: "
            + ", ".join(f"{item['oxide']}={item['normalized_wt_percent']:.2f} wt%" for item in omitted)
        )

    st.caption(f"Active {database} BUILD components")
    st.code(active_component_text(database), language="text")

    with st.form("model_editor"):
        edited = deepcopy(model)
        edited["project"] = st.text_input("Project", value=str(model.get("project", "")))
        edited["description"] = st.text_input("Description", value=str(model.get("description", "")))
        edited["planetprofile_filename"] = st.text_input(
            "PlanetProfile filename",
            value=str(model.get("planetprofile_filename", "")),
        )
        edited["scientific_status"] = st.text_input(
            "Scientific status",
            value=str(model.get("scientific_status", "")),
        )
        edited["model_scope"] = st.text_input("Model scope", value=str(model.get("model_scope", "")))
        edited["planetprofile_readiness"] = st.text_input(
            "PlanetProfile readiness",
            value=str(model.get("planetprofile_readiness", "")),
        )
        edited["composition_interpretation"] = st.text_area(
            "Composition interpretation",
            value=str(model.get("composition_interpretation", "")),
        )
        edited["source_note"] = st.text_area("Source note", value=str(model.get("source_note", "")))
        edited["literature_proxy"] = st.checkbox(
            "Based on literature values",
            value=bool(model.get("literature_proxy", False)),
            help="Use this when the composition comes from a publication or tabulated literature average.",
        )

        st.subheader("Oxides, wt%")
        current_oxides = {row["oxide"]: row["raw_wt_percent"] for row in rows}
        edited["oxides_wt_percent"] = {
            oxide: st.number_input(
                oxide,
                value=float(current_oxides.get(oxide, 0.0)),
                step=0.01,
                format="%.2f",
            )
            for oxide in OXIDE_ORDER
        }
        submitted = st.form_submit_button("Save model to config")

    if submitted:
        result = validate_model_entry(edited)
        if result.errors:
            st.error("Cannot save: " + "; ".join(result.errors))
            return
        updated_config = replace_model_entry(config, str(model.get("project", "")), edited)
        write_config(config_path, updated_config)


def composition_workspace(config_path: Path, config: dict[str, Any], models: list[dict[str, Any]]) -> dict[str, Any]:
    database = get_current_database(config)
    st.subheader("Build Composition")
    st.caption(
        "Create or revise source compositions stored in `configs/models.json`. "
        "The thermodynamic database controls which composition fields are shown here."
    )

    st.markdown("**Thermodynamic database for composition fields**")
    database = show_database_selector(config, config_path)

    action_col, source_col = st.columns([1.35, 1])
    with action_col:
        builder_action = st.radio(
            "Builder action",
            options=["Create a new composition", "Copy a saved composition", "Edit a saved composition"],
            horizontal=True,
        )
    existing_projects = {str(model.get("project", "")) for model in models if model.get("project")}
    creating_new = builder_action == "Create a new composition"
    copying_existing = builder_action == "Copy a saved composition"
    if creating_new:
        base_model = new_model_template("my_surface_proxy")
        choice_key = "new_composition"
        with source_col:
            input_basis = "component" if database_uses_component_inputs(database) else "oxide"
            st.caption(f"Active setup: `{database}` with {input_basis} inputs.")
    elif copying_existing:
        with source_col:
            selected_source_project = st.selectbox(
                "Saved composition to copy",
                options=[str(model.get("project", "")) for model in models],
                format_func=lambda project: model_label(next(model for model in models if model.get("project") == project)),
            )
        source_model = deepcopy(next(model for model in models if model.get("project") == selected_source_project))
        copied_project = unique_project_name(selected_source_project, existing_projects)
        source_model["project"] = copied_project
        source_model["description"] = f"Copy of {selected_source_project}"
        source_model["planetprofile_filename"] = f"{copied_project}_PerpleX.tab"
        source_model["source_note"] = (
            f"Copied from `{selected_source_project}` in the Streamlit GUI. "
            + str(source_model.get("source_note", ""))
        ).strip()
        base_model = source_model
        choice_key = f"copy_{selected_source_project}"
        with source_col:
            st.caption("This creates a new saved model. The original is unchanged.")
    else:
        with source_col:
            selected_builder_project = st.selectbox(
                "Saved composition to edit",
                options=[str(model.get("project", "")) for model in models],
                format_func=lambda project: model_label(next(model for model in models if model.get("project") == project)),
            )
        base_model = deepcopy(next(model for model in models if model.get("project") == selected_builder_project))
        choice_key = f"edit_{selected_builder_project}"

    reset_key = f"composition_editor_reset_{choice_key}"
    st.session_state.setdefault(reset_key, 0)
    widget_scope = f"{choice_key}_{st.session_state[reset_key]}"

    edited = deepcopy(base_model)
    edited["database"] = database
    component_mode = database_uses_component_inputs(database)
    total_limit = 100.0

    def capped_default(value: float, max_value: float) -> float:
        return min(max(float(value), 0.0), max_value)

    st.markdown("**Model**")
    project_col, description_col = st.columns([0.85, 1.4])
    with project_col:
        edited["project"] = st.text_input(
            "Project name",
            value="" if creating_new else str(base_model.get("project", "")),
            placeholder=str(base_model.get("project", "my_surface_proxy")),
            key=f"workspace_project_{widget_scope}",
            help="Required. This becomes the Perple_X project name and output folder name.",
        )
    with description_col:
        edited["description"] = st.text_input(
            "Description",
            value="" if creating_new else str(base_model.get("description", "")),
            placeholder=str(base_model.get("description", "User-defined composition")),
            key=f"workspace_description_{widget_scope}",
            help="Optional but useful for remembering what this composition represents.",
        )
    if not edited["description"].strip():
        edited["description"] = str(base_model.get("description", "User-defined composition"))

    with st.expander("Optional metadata"):
        filename_default = (
            f"{edited['project'].strip()}_PerpleX.tab"
            if edited["project"].strip()
            else str(base_model.get("planetprofile_filename", "my_surface_proxy_PerpleX.tab"))
        )
        planetprofile_filename = st.text_input(
            "PlanetProfile filename",
            value="" if creating_new else str(base_model.get("planetprofile_filename", "")),
            placeholder=filename_default,
            key=f"workspace_pp_filename_{widget_scope}",
        )
        edited["planetprofile_filename"] = planetprofile_filename.strip() or filename_default
        edited["scientific_status"] = (
            st.text_input(
                "Scientific status",
                value="" if creating_new else str(base_model.get("scientific_status", "")),
                placeholder=str(base_model.get("scientific_status", "")),
                key=f"workspace_status_{widget_scope}",
            ).strip()
            or str(base_model.get("scientific_status", "surface_proxy_smoke_test"))
        )
        edited["model_scope"] = (
            st.text_input(
                "Model scope",
                value="" if creating_new else str(base_model.get("model_scope", "")),
                placeholder=str(base_model.get("model_scope", "")),
                key=f"workspace_scope_{widget_scope}",
            ).strip()
            or str(base_model.get("model_scope", "surface_terrane_proxy"))
        )
        edited["planetprofile_readiness"] = (
            st.text_input(
                "PlanetProfile readiness",
                value="" if creating_new else str(base_model.get("planetprofile_readiness", "")),
                placeholder=str(base_model.get("planetprofile_readiness", "")),
                key=f"workspace_readiness_{widget_scope}",
            ).strip()
            or str(base_model.get("planetprofile_readiness", "mechanically_exportable_not_scientifically_final"))
        )
        edited["composition_interpretation"] = (
            st.text_area(
                "Composition interpretation",
                value="" if creating_new else str(base_model.get("composition_interpretation", "")),
                placeholder=str(base_model.get("composition_interpretation", "")),
                key=f"workspace_interpretation_{widget_scope}",
            ).strip()
            or str(base_model.get("composition_interpretation", "User-defined composition."))
        )
        edited["source_note"] = (
            st.text_area(
                "Source note",
                value="" if creating_new else str(base_model.get("source_note", "")),
                placeholder=str(base_model.get("source_note", "")),
                key=f"workspace_source_{widget_scope}",
            ).strip()
            or str(base_model.get("source_note", "Entered through the Streamlit GUI."))
        )
        edited["literature_proxy"] = st.checkbox(
            "Based on literature values",
            value=bool(base_model.get("literature_proxy", False)),
            key=f"workspace_literature_values_{widget_scope}",
            help="Use this when the composition comes from a publication or tabulated literature average.",
        )

    save_status_slot = st.empty()

    with st.container():
        if component_mode:
            base_components = safe_component_composition(base_model) or {}
            edited.pop("oxides_wt_percent", None)
            edited.pop("raw_wt_percent", None)
            edited.pop("composition_raw", None)
            edited["components_wt_percent"] = {}
            build_components = get_database_components(database)
            st.markdown(f"**Modeled Components for {database}, wt%**")
            st.caption("Total input is capped at 100 wt%. Lower earlier values to free room for later fields.")
            component_columns = st.columns(4)
            entered_total = 0.0
            for index, (_, component) in enumerate(build_components):
                with component_columns[index % 4]:
                    max_value = max(0.0, total_limit - entered_total)
                    edited["components_wt_percent"][component] = st.number_input(
                        component,
                        value=capped_default(float(base_components.get(component, 0.0)), max_value),
                        min_value=0.0,
                        max_value=max_value,
                        step=0.01,
                        format="%.2f",
                        key=f"workspace_component_{widget_scope}_{component}",
                    )
                    entered_total += float(edited["components_wt_percent"][component])
            with st.expander("Component names"):
                st.write(
                    "These names must match the active Perple_X datafile. For element-style DEW databases, "
                    "hydrogen, oxygen, sulfur, and nitrogen are represented with component names such as "
                    "H2, O2, S2, and N2."
                )
        else:
            base_oxides = base_model.get("oxides_wt_percent", {})
            if not isinstance(base_oxides, dict):
                base_oxides = {}
            edited.pop("components_wt_percent", None)
            edited["oxides_wt_percent"] = {}
            active_oxides = get_active_oxides(database)
            source_only_oxides = get_source_only_oxides(database)
            modeled_oxides = [oxide for oxide in OXIDE_ORDER if oxide in active_oxides]

            st.markdown(f"**Modeled Oxides for {database}, wt%**")
            st.caption("Total input is capped at 100 wt%. Lower earlier values to free room for later fields.")
            modeled_columns = st.columns(4)
            entered_total = 0.0
            for index, oxide in enumerate(modeled_oxides):
                with modeled_columns[index % 4]:
                    max_value = max(0.0, total_limit - entered_total)
                    edited["oxides_wt_percent"][oxide] = st.number_input(
                        oxide,
                        value=capped_default(float(base_oxides.get(oxide, 0.0)), max_value),
                        min_value=0.0,
                        max_value=max_value,
                        step=0.01,
                        format="%.2f",
                        key=f"workspace_oxide_{widget_scope}_{oxide}",
                    )
                    entered_total += float(edited["oxides_wt_percent"][oxide])
            st.markdown(f"**Source-Only Oxides for {database}, wt%**")
            st.caption("Saved in the record and plots, but not passed to this BUILD template.")
            source_columns = st.columns(4)
            for index, oxide in enumerate(source_only_oxides):
                with source_columns[index % 4]:
                    max_value = max(0.0, total_limit - entered_total)
                    edited["oxides_wt_percent"][oxide] = st.number_input(
                        oxide,
                        value=capped_default(float(base_oxides.get(oxide, 0.0)), max_value),
                        min_value=0.0,
                        max_value=max_value,
                        step=0.01,
                        format="%.2f",
                        key=f"workspace_source_oxide_{widget_scope}_{oxide}",
                    )
                    entered_total += float(edited["oxides_wt_percent"][oxide])
            if source_only_oxides:
                st.caption(
                    f"{database} models {', '.join(modeled_oxides)}. "
                    f"{', '.join(source_only_oxides)} are source-only."
                )
            with st.expander("Why other elements are not shown"):
                st.write(
                    "The GUI is tied to the current Perple_X BUILD component list and composition schema. "
                    "Adding a new element is not just adding another text box: the BUILD template, active "
                    "components, thermodynamic database, solution models, validation, and PlanetProfile "
                    "provenance all need to agree."
                )

    validation = validate_model_entry(edited)
    source_project = "" if creating_new or copying_existing else str(base_model.get("project", ""))
    edited_project = str(edited.get("project", "")).strip()
    duplicate_project = edited_project in existing_projects and edited_project != source_project
    cannot_save_messages = list(validation.errors)
    if duplicate_project:
        cannot_save_messages.append(f"another saved model already uses project `{edited_project}`")
    for warning in validation.warnings:
        st.warning(warning)

    with save_status_slot.container():
        try:
            current_total = model_input_total(edited)
        except (TypeError, ValueError):
            current_total = 0.0
        remaining_total = max(0.0, total_limit - current_total)
        total_col1, total_col2, total_col3, save_col, undo_col = st.columns([0.9, 0.9, 0.8, 1.1, 0.8])
        total_col1.metric("Current input total", f"{current_total:.2f} wt%")
        total_col2.metric("Remaining to 100 wt%", f"{remaining_total:.2f}")
        total_col3.metric("Input basis", "components" if component_mode else "oxides")
        with save_col:
            save_clicked = st.button(
                "Save composition",
                type="primary",
                disabled=bool(cannot_save_messages),
                width="stretch",
                key=f"save_composition_{widget_scope}",
            )
        with undo_col:
            undo_clicked = st.button(
                "Undo edits",
                disabled=creating_new or copying_existing,
                width="stretch",
                key=f"undo_composition_{widget_scope}",
            )
        if cannot_save_messages:
            st.error("Cannot save: " + "; ".join(cannot_save_messages))
        if undo_clicked:
            st.session_state[reset_key] += 1
            st.rerun()

    if save_clicked:
        updated_config = replace_model_entry(config, source_project, edited)
        write_config(config_path, updated_config)
        st.info("After saving, switch to Run Pipeline and select this saved model in the sidebar.")

    preview_col, guardrail_col = st.columns([1.3, 1])
    with preview_col:
        if component_mode:
            rows = component_table_rows(edited, database) if validation.ok else []
            if rows:
                st.caption(
                    "Input values are exactly what you type. The normalized column is the same "
                    "composition scaled to total 100 wt%; that is the component record used by the pipeline."
                )
                show_component_table(rows)
                st.subheader("Composition Plot")
                st.caption("Single plot of the normalized component composition.")
                st.plotly_chart(
                    single_composition_figure(
                        {row["component"]: round(row["normalized to 100 wt%"], 2) for row in rows},
                        x_title="Component",
                    ),
                    use_container_width=True,
                )
        else:
            rows = oxide_table_rows(edited, database=database) if validation.ok else []
            if rows:
                st.caption(
                    "Input values are exactly what you type. The normalized column is the same "
                    "composition scaled to total 100 wt%; that is the composition record used by the pipeline."
                )
                show_oxide_table(rows, database=database)
                plot_rows = composition_plot_rows(edited)
                st.subheader("Composition Plot")
                st.caption("Single plot of the normalized composition. Raw and normalized are not separate models.")
                st.plotly_chart(
                    single_composition_figure(
                        {row["oxide"]: round(row["normalized_wt_percent"], 2) for row in plot_rows},
                        x_title="Oxide",
                    ),
                    use_container_width=True,
                )
    with guardrail_col:
        if validation.ok:
            show_scientific_guardrail(edited, database=database)
            if not component_mode:
                omitted = omitted_oxides_for_model(edited, database=database)
                if omitted:
                    st.warning(
                        f"Omitted from {database} BUILD: "
                        + ", ".join(f"{item['oxide']}={item['normalized_wt_percent']:.2f} wt%" for item in omitted)
                    )
    return edited if validation.ok else base_model


def show_composition_page(
    config_path: Path,
    config: dict[str, Any],
    models: list[dict[str, Any]],
    current_database: str,
    page: str,
) -> None:
    st.header("Composition")
    st.caption("Build, batch-generate, review, import, export, and manage saved source compositions.")

    if page == COMPOSITION_BUILD_PAGE:
        composition_workspace(config_path, config, models)
        return

    if page == COMPOSITION_CATALOG_PAGE:
        st.subheader("Saved Composition Catalog")
        st.caption(
            "Review existing saved compositions, including their thermodynamic model, basis, totals, and metadata."
        )

        st.markdown("**Catalog actions**")
        action_col1, action_col2 = st.columns([1, 1])
        with action_col1:
            with st.expander("Import or export compositions", expanded=True):
                show_import_export_panel(config_path, config)
        with action_col2:
            with st.expander("Delete saved composition(s)", expanded=True):
                delete_model_panel(config_path, config, models)

        st.divider()
        show_model_catalog(models, database=current_database)
        return

    if page == COMPOSITION_BATCH_PAGE:
        show_batch_workspace(config_path, config, models)
        return

    if page == COMPOSITION_THERMO_PAGE:
        show_thermodynamic_model_catalog()
        return

    st.warning(f"Unknown composition page `{page}`. Showing Build instead.")
    composition_workspace(config_path, config, models)


def show_sidebar_local_configuration(config_path: Path, config: dict[str, Any], workspace_mode: str) -> None:
    perplex_dir = st.text_input(
        "Perple_X directory",
        value=str(config.get("perplex_dir", "")),
        key="sidebar_perplex_dir",
        help="Folder containing BUILD, VERTEX, WERAMI executables and Perple_X datafiles.",
    )
    st.caption("Saved as `perplex_dir` in the active config.")
    if st.button("Save Perple_X path", key="save_sidebar_perplex_dir", width="stretch"):
        write_config(config_path, update_perplex_dir(config, perplex_dir))


def show_home_page(config_path: Path, config: dict[str, Any], models: list[dict[str, Any]]) -> None:
    st.header("Home")
    st.caption("Start from the task you want to do next.")

    perplex_dir = str(config.get("perplex_dir", "")).strip()
    metric_col1, metric_col2, metric_col3 = st.columns(3)
    metric_col1.metric("Saved compositions", len(models))
    metric_col2.metric("Perple_X path", "Set" if perplex_dir else "Missing")
    metric_col3.metric("Config", config_path.name)

    if not perplex_dir:
        st.warning("Set the Perple_X directory in the left Local configuration panel before running Perple_X.")

    build_col, run_col, compare_col = st.columns(3)
    with build_col:
        with st.container(border=True):
            st.subheader("Composition")
            st.write("Build, copy, batch-generate, import, or review saved source compositions.")
            st.button(
                "Build composition",
                type="primary",
                width="stretch",
                on_click=open_composition_page,
                args=(COMPOSITION_PAGES.index(COMPOSITION_BUILD_PAGE),),
            )
            st.button(
                "Open catalog",
                width="stretch",
                on_click=open_composition_page,
                args=(COMPOSITION_PAGES.index(COMPOSITION_CATALOG_PAGE),),
            )
    with run_col:
        with st.container(border=True):
            st.subheader("Pipeline")
            st.write("Configure thermodynamic setup per file, generate inputs, run Perple_X, and validate outputs.")
            st.button(
                "Setup selected models",
                type="primary",
                width="stretch",
                on_click=open_pipeline_step,
                args=(0,),
            )
            st.button(
                "Run Perple_X",
                width="stretch",
                on_click=open_pipeline_step,
                args=(2,),
            )
    with compare_col:
        with st.container(border=True):
            st.subheader("Compare")
            st.write("Inspect model compositions, density/velocity plots, and generated output ranges.")
            st.button(
                "Compare models",
                type="primary",
                width="stretch",
                on_click=set_workspace_mode,
                args=(COMPARISON_MODE,),
            )


def show_selected_comparison_plots(config_path: Path, models: list[dict[str, Any]]) -> None:
    available_projects = project_options(models)
    seed_model_selector_state("step5_plot_projects", available_projects)
    projects_to_plot = st.multiselect(
        "Compositions to display in plots",
        options=available_projects,
        key="step5_plot_projects",
        on_change=sync_model_selection,
        args=("step5_plot_projects", available_projects),
        format_func=lambda project: model_label(next(model for model in models if model.get("project") == project)),
        help="Choose which saved compositions/models are drawn in the comparison plots below.",
    )
    if not projects_to_plot:
        st.info("Select at least one composition to display in the plots.")
        return

    try:
        config = run_perplex.load_config(config_path)
        plot_models = plot_comparisons.selected_plot_models(config, projects_to_plot)
        st.plotly_chart(composition_comparison_figure(plot_models), use_container_width=True)
        try:
            st.plotly_chart(property_comparison_figure(plot_models), use_container_width=True)
        except (FileNotFoundError, ValueError) as exc:
            st.info(f"Property comparison plot is unavailable for this selection: {exc}")
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        st.warning(f"Could not render selected comparison plots: {exc}")


def composition_comparison_figure(models: list[plot_comparisons.PlotModel]) -> go.Figure:
    compositions = [plot_comparisons.load_normalized_composition(model.composition_file) for model in models]
    is_component = any(plot_comparisons.is_component_composition(model.composition_file) for model in models)
    keys = plot_comparisons.composition_keys(compositions, use_oxide_order=not is_component)
    if not keys:
        raise ValueError("Selected composition files do not contain nonzero normalized composition values.")

    fig = go.Figure()
    for index, (model, composition) in enumerate(zip(models, compositions, strict=True)):
        fig.add_trace(
            go.Bar(
                name=model.label,
                x=keys,
                y=[composition.get(key, 0.0) for key in keys],
                marker_color=plot_comparisons.COLORS[index % len(plot_comparisons.COLORS)],
                hovertemplate="<b>%{fullData.name}</b><br>%{x}: %{y:.2f} wt%<extra></extra>",
            )
        )

    composition_type = "component" if is_component else "oxide"
    fig.update_layout(
        title=f"Normalized {composition_type} composition",
        xaxis_title=composition_type.title(),
        yaxis_title="wt%",
        yaxis=dict(range=[0, 100]),
        barmode="group",
        hovermode="x unified",
        height=560,
        margin=dict(l=60, r=24, t=72, b=90),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1.0),
    )
    return fig


def property_comparison_figure(models: list[plot_comparisons.PlotModel]) -> go.Figure:
    profiles: dict[tuple[str, str], list[tuple[float, float]]] = {}
    pressure_values: list[float] = []
    y_values_by_property: dict[str, list[float]] = {name: [] for name, _, _, _ in plot_comparisons.PROPERTY_PLOTS}

    for model in models:
        if not model.tab_file.exists():
            raise FileNotFoundError(f"Missing output table for plotting: {model.tab_file}")
        for property_name, _title, _unit, scale in plot_comparisons.PROPERTY_PLOTS:
            profile = plot_comparisons.pressure_profile(model.tab_file, property_name, scale)
            profiles[(model.project, property_name)] = profile
            pressure_values.extend(point[0] for point in profile if math.isfinite(point[0]))
            y_values_by_property[property_name].extend(point[1] for point in profile if math.isfinite(point[1]))

    if not pressure_values:
        raise ValueError("No finite pressure values were found in selected output tables.")

    fig = make_subplots(
        rows=3,
        cols=2,
        subplot_titles=[f"{title} ({unit})" for _name, title, unit, _scale in plot_comparisons.PROPERTY_PLOTS],
        vertical_spacing=0.1,
        horizontal_spacing=0.09,
    )
    x_min, x_max = plot_comparisons.axis_range(pressure_values)
    x_range = [max(0.0, x_min), x_max]

    for plot_index, (property_name, title, unit, _scale) in enumerate(plot_comparisons.PROPERTY_PLOTS):
        row = plot_index // 2 + 1
        col = plot_index % 2 + 1
        for model_index, model in enumerate(models):
            series = profiles[(model.project, property_name)]
            if len(series) < 2:
                continue
            fig.add_trace(
                go.Scatter(
                    x=[point[0] for point in series],
                    y=[point[1] for point in series],
                    name=model.label,
                    mode="lines",
                    line=dict(color=plot_comparisons.COLORS[model_index % len(plot_comparisons.COLORS)], width=2.4),
                    legendgroup=model.project,
                    showlegend=plot_index == 0,
                    hovertemplate="<b>%{fullData.name}</b><br>"
                    + "P: %{x:.3g} GPa<br>"
                    + f"{title}: %{{y:.3g}} {unit}<extra></extra>",
                ),
                row=row,
                col=col,
            )
        y_values = y_values_by_property[property_name]
        if y_values:
            y_min, y_max = plot_comparisons.axis_range(y_values)
            fig.update_yaxes(range=[y_min, y_max], row=row, col=col)
        fig.update_xaxes(range=x_range, title_text="Pressure (GPa)" if row == 3 else None, row=row, col=col)

    fig.update_layout(
        title="Property comparison",
        height=980,
        hovermode="x unified",
        margin=dict(l=72, r=28, t=92, b=64),
        legend=dict(orientation="h", yanchor="bottom", y=1.03, xanchor="right", x=1.0),
    )
    return fig


def validation_display(status: str) -> tuple[str, str]:
    if status == "pass":
        return "✅", "PASS"
    if status == "fail":
        return "❌", "FAIL"
    if status == "missing":
        return "🕓", "NOT RUN"
    return "⚠️", "UNKNOWN"


def artifact_display(path: Path) -> tuple[str, str]:
    return ("✅", "found") if path.exists() else ("❌", "missing")


def show_outputs(
    config_path: Path,
    models: list[dict[str, Any]],
    export_dir: str,
    selected_projects: list[str],
) -> None:
    detail_rows: list[tuple[str, str, str | None, str | None, list[tuple[str, Path]]]] = []
    display_models = models_for_projects(models, selected_projects)
    if selected_projects:
        st.caption(f"Showing validation and outputs for {len(display_models)} selected model(s).")
    else:
        st.info("No models are selected in the pipeline yet, so validation details show all saved models.")

    for model in display_models:
        project = str(model.get("project", ""))
        if not project:
            continue
        paths = model_output_paths(model, config_path)
        report = read_text_if_exists(paths.validation_report)
        status = validation_status(report)
        output_rows = [
            ("raw WERAMI table", paths.raw_werami_table),
            ("PlanetProfile table", paths.planetprofile_table),
            ("native PlanetProfile table", paths.native_planetprofile_table),
            ("build log", paths.build_log),
            ("vertex log", paths.vertex_log),
            ("werami log", paths.werami_log),
        ]
        detail_rows.append((project, status, report, read_text_if_exists(paths.oxide_omissions), output_rows))

    status_counts = {"pass": 0, "fail": 0, "missing": 0, "unknown": 0}
    for _, status, _, _, _ in detail_rows:
        status_counts[status if status in status_counts else "unknown"] += 1
    count_cols = st.columns(4)
    count_cols[0].metric("✅ Passed", status_counts["pass"])
    count_cols[1].metric("❌ Failed", status_counts["fail"])
    count_cols[2].metric("🕓 Not run", status_counts["missing"])
    count_cols[3].metric("⚠️ Unknown", status_counts["unknown"])

    st.subheader("Plots")
    show_selected_comparison_plots(config_path, models)

    st.subheader("Validation Details")
    for project, status, report, omissions, output_rows in detail_rows:
        status_icon, status_label = validation_display(status)
        with st.expander(f"{status_icon} {project} — {status_label}", expanded=status != "pass"):
            if status == "pass":
                st.success("Validation status: PASS")
            elif status == "fail":
                st.error("Validation status: FAIL")
            else:
                st.info("Validation report is not available yet.")
            if omissions:
                st.warning(omissions)
            st.caption("Artifacts")
            for label, path in output_rows:
                artifact_icon, artifact_status = artifact_display(path)
                st.write(f"{artifact_icon} **{label}** ({artifact_status})")
                st.code(str(path), language="text")
            if report:
                st.caption("Validation report text")
                st.code(report, language="text")

    manifest_path = export_manifest_path(config_path, export_dir)
    with st.expander("Export manifest (optional provenance)", expanded=False):
        st.write(f"`{manifest_path}`")
        manifest = read_export_manifest(manifest_path)
        if not manifest:
            st.info("No export manifest has been written yet.")
            return
        st.warning("Export success does not imply scientific readiness.")
        st.caption(
            "PlanetProfile does not need this manifest to read a table. It is a provenance receipt "
            "for humans and scripts, so exported smoke-test tables are not confused with final EOS models."
        )
        rows = export_manifest_table_rows(manifest)
        if rows:
            st.dataframe(rows, width="stretch", hide_index=True)
        st.caption("Raw JSON manifest")
        st.json(manifest)


def main() -> None:
    inject_styles()
    st.title("🪐 Planetary EOS Lab")
    st.caption("A laboratory for planetary equation-of-state modeling with Perple_X")
    st.warning(
        "Included example models are smoke tests or first-pass candidates, "
        "not final publication-ready EOS models."
    )

    if "workspace_mode" not in st.session_state:
        st.session_state["workspace_mode"] = HOME_MODE
    if st.session_state.get("workspace_mode") == LEGACY_COMPOSITION_BUILDER_MODE:
        st.session_state["workspace_mode"] = COMPOSITION_BUILDER_MODE
    if "composition_page_index" not in st.session_state:
        set_composition_page(0)
    else:
        set_composition_page(int(st.session_state.get("composition_page_index", 0)))
    if st.session_state.get("workspace_mode") == BATCH_PROCESSING_MODE:
        st.session_state["workspace_mode"] = COMPOSITION_BUILDER_MODE
        set_composition_page(COMPOSITION_PAGES.index(COMPOSITION_BATCH_PAGE))
    if "workflow_step_index" not in st.session_state:
        set_workflow_step(0)
    else:
        set_workflow_step(int(st.session_state.get("workflow_step_index", 0)))

    with st.sidebar:
        st.header("Workspace")
        st.caption("Main task")
        for mode in [HOME_MODE, COMPOSITION_BUILDER_MODE, PIPELINE_MODE, COMPARISON_MODE]:
            st.button(
                mode,
                key=f"workspace_mode_{mode}",
                type="primary" if st.session_state["workspace_mode"] == mode else "secondary",
                on_click=set_workspace_mode,
                args=(mode,),
                width="stretch",
            )
        workspace_mode = str(st.session_state["workspace_mode"])
        step = st.session_state.get("workflow_step_choice", PIPELINE_STEPS[0])
        composition_page = st.session_state.get("composition_page_choice", COMPOSITION_PAGES[0])
        if workspace_mode == COMPOSITION_BUILDER_MODE:
            composition_page_index = int(st.session_state.get("composition_page_index", 0))
            if COMPOSITION_PAGE_CONTROL_KEY not in st.session_state:
                st.session_state[COMPOSITION_PAGE_CONTROL_KEY] = COMPOSITION_PAGES[composition_page_index]
            st.radio(
                "Composition pages",
                options=COMPOSITION_PAGES,
                key=COMPOSITION_PAGE_CONTROL_KEY,
                on_change=set_composition_page_from_control,
                width="stretch",
            )
            composition_page_index = int(st.session_state.get("composition_page_index", 0))
            nav_col1, nav_col2 = st.columns(2)
            with nav_col1:
                st.button(
                    "Previous",
                    disabled=composition_page_index == 0,
                    on_click=set_composition_page,
                    args=(composition_page_index - 1,),
                    width="stretch",
                    key="composition_previous",
                )
            with nav_col2:
                st.button(
                    "Next",
                    disabled=composition_page_index == len(COMPOSITION_PAGES) - 1,
                    on_click=set_composition_page,
                    args=(composition_page_index + 1,),
                    width="stretch",
                    key="composition_next",
                )
            composition_page = str(st.session_state.get("composition_page_choice", COMPOSITION_PAGES[0]))
        elif workspace_mode == PIPELINE_MODE:
            step_index = int(st.session_state.get("workflow_step_index", 0))
            if PIPELINE_STEP_CONTROL_KEY not in st.session_state:
                st.session_state[PIPELINE_STEP_CONTROL_KEY] = PIPELINE_STEPS[step_index]
            st.radio(
                "Pipeline steps",
                options=PIPELINE_STEPS,
                key=PIPELINE_STEP_CONTROL_KEY,
                on_change=set_workflow_step_from_control,
                width="stretch",
            )
            step_index = int(st.session_state.get("workflow_step_index", 0))
            nav_col1, nav_col2 = st.columns(2)
            with nav_col1:
                st.button(
                    "Previous",
                    disabled=step_index == 0,
                    on_click=set_workflow_step,
                    args=(step_index - 1,),
                    width="stretch",
                )
            with nav_col2:
                st.button(
                    "Next",
                    disabled=step_index == len(PIPELINE_STEPS) - 1,
                    on_click=set_workflow_step,
                    args=(step_index + 1,),
                    width="stretch",
                )
            step = str(st.session_state.get("workflow_step_choice", PIPELINE_STEPS[0]))
        elif workspace_mode == HOME_MODE:
            st.caption("Choose a task from the home dashboard.")
        else:
            st.caption("Select saved models, compare outputs, or switch to Composition to build inputs.")
        st.divider()

        # Auto-save controls
        show_autosave_controls()

        st.divider()
        st.caption("Local configuration")
        config_input = st.text_input("Config path", value=str(DEFAULT_CONFIG_PATH.relative_to(REPO_ROOT)))

    config_path = resolve_path(config_input, REPO_ROOT)

    if not config_path.exists():
        st.header("Create Local Config" if workspace_mode in {HOME_MODE, COMPOSITION_BUILDER_MODE} else "Step 1. Setup & Select Models")
        st.write(f"Current working directory: `{Path.cwd()}`")
        st.write(f"Repository root: `{REPO_ROOT}`")
        st.write(f"Resolved config path: `{config_path}`")
        st.warning(
            f"`{config_path}` does not exist. Copy `{EXAMPLE_CONFIG_PATH}` to create a local config."
        )
        if st.button("Create configs/models.json from example"):
            copy_example_config(config_path)
            st.success(f"Created {config_path}")
        return

    config = load_config_or_none(config_path)
    if config is None:
        return

    models = list_model_entries(config)
    if not models:
        st.error("No models are configured.")
        return
    current_database = get_current_database(config)
    available_projects = project_options(models)
    for selector_key in PIPELINE_MODEL_SELECTOR_KEYS:
        seed_model_selector_state(selector_key, available_projects)
    with st.sidebar:
        show_sidebar_local_configuration(config_path, config, workspace_mode)
    if not st.session_state.get("planetprofile_export_dir"):
        st.session_state["planetprofile_export_dir"] = str(DEFAULT_PLANETPROFILE_EXPORT_DIR)

    export_dir = str(st.session_state.get("planetprofile_export_dir", REPO_ROOT / "outputs" / "planetprofile_export"))

    if workspace_mode == HOME_MODE:
        show_home_page(config_path, config, models)
        return

    if workspace_mode == COMPOSITION_BUILDER_MODE:
        show_composition_page(config_path, config, models, current_database, str(composition_page))
        return

    if workspace_mode == COMPARISON_MODE:
        show_comparison_workspace(models, config_path)
        return

    if step == "1. Setup & Select Models":
        st.header("Step 1. Setup & Select Models")
        st.subheader("Models for this pipeline session")
        selected_projects = st.multiselect(
            "Saved models to review",
            options=available_projects,
            key=PIPELINE_SELECTION_KEY,
            on_change=sync_model_selection,
            args=(PIPELINE_SELECTION_KEY, available_projects),
            format_func=lambda project: model_label(next(model for model in models if model.get("project") == project)),
            help="Choose one or more saved model entries from configs/models.json.",
        )
        if selected_projects:
            st.success(f"Selected {len(selected_projects)} model(s) for review.")
        with st.container(border=True):
            st.subheader("Thermodynamic Setup")
            if selected_projects:
                show_model_database_configuration(config_path, config, models, selected_projects)
            else:
                st.info("Select one or more saved models to configure database, BUILD template, and grid options.")

        with st.container(border=True):
            st.subheader("Composition Review")
            show_selected_model_reviews(models, selected_projects, database=current_database)

    elif step == "2. Generate Files":
        st.header("Step 2. Generate Files")
        st.write("This step runs `make_compositions.py` and writes generated files under `compositions/`.")
        projects_to_generate = st.multiselect(
            "Saved models to generate",
            options=available_projects,
            key="generate_model_projects",
            on_change=sync_model_selection,
            args=("generate_model_projects", available_projects),
            format_func=lambda project: model_label(next(model for model in models if model.get("project") == project)),
            help="Choose one or more saved model entries from configs/models.json.",
        )
        st.caption(
            "Generated composition JSON, bulk-value, and summary files are written under `compositions/`."
        )
        show_streamlit_command_job()
        command_running = streamlit_job_is_running()
        if not projects_to_generate:
            st.info("Select at least one saved model to generate.")
        if st.button("Generate selected file(s)", disabled=not projects_to_generate or command_running):
            commands = [
                relabel_command(
                    generate_compositions_command(config_path, project),
                    f"Generate files: {project}",
                )
                for project in projects_to_generate
            ]
            run_streamlit_commands(commands, job_label="Generate files")

    elif step == "3. Run Perple_X":
        st.header("Step 3. Run Perple_X")
        st.warning("Perple_X must be installed locally. Included example models still require scientific review before final use.")
        projects_to_run = st.multiselect(
            "Saved models to run",
            options=available_projects,
            key="run_model_projects",
            on_change=sync_model_selection,
            args=("run_model_projects", available_projects),
            format_func=lambda project: model_label(next(model for model in models if model.get("project") == project)),
            help="Choose one or more saved model entries from configs/models.json.",
        )
        export_after_run = st.checkbox(
            "Export PlanetProfile tables after run",
            value=False,
            help="After validation succeeds, copy native PlanetProfile-format tables to the export directory.",
        )
        if export_after_run:
            st.caption(f"Export directory: `{export_dir}`")
        show_streamlit_command_job()
        command_running = streamlit_job_is_running()
        if not projects_to_run:
            st.info("Select at least one saved model to run.")
        if st.button("Run selected model(s)", disabled=not projects_to_run or command_running):
            commands = [
                relabel_command(
                    full_pipeline_command(
                        config_path,
                        project=project,
                        export_planetprofile=export_after_run,
                        export_dir=export_dir if export_after_run else None,
                    ),
                    f"Run pipeline: {project}",
                )
                for project in projects_to_run
            ]
            run_streamlit_commands(commands, job_label="Run Perple_X")

    elif step == "4. Validate / Export":
        st.header("Step 4. Validate / Export")

        tab1, tab2, tab3 = st.tabs(["Validation & Output", "Phase Diagram", "Export"])

        with tab1:
            selected_projects = current_pipeline_selection(available_projects)
            show_outputs(config_path, models, export_dir, selected_projects)

        with tab2:
            selected_projects = current_pipeline_selection(available_projects)
            phase_default = selected_projects[0] if selected_projects else None
            show_phase_diagram_panel(models, phase_default, config_path)

        with tab3:
            st.subheader("Export")
            st.caption("Download saved model definitions, export generated PlanetProfile tables, or both.")
            projects_to_export = st.multiselect(
                "Saved models",
                options=available_projects,
                key="export_model_projects",
                on_change=sync_model_selection,
                args=("export_model_projects", available_projects),
                format_func=lambda project: model_label(next(model for model in models if model.get("project") == project)),
                help="Choose one or more saved model entries for the export actions below.",
            )
            if not projects_to_export:
                st.info("Select at least one saved model.")

            st.divider()
            st.subheader("Model Definition Export")
            st.caption(
                "Download the selected entries from `configs/models.json`. "
                "This includes composition and metadata, and does not require Perple_X or PlanetProfile output."
            )
            selected_export_json = export_model_definitions_to_json(models, projects_to_export) if projects_to_export else ""
            st.download_button(
                "Download selected model definition(s)",
                data=selected_export_json,
                file_name=model_definitions_export_filename(projects_to_export) if projects_to_export else "model_definitions.json",
                mime="application/json",
                disabled=not projects_to_export,
                use_container_width=True,
            )

            st.divider()
            st.subheader("PlanetProfile Table Export")
            st.warning("PlanetProfile export success does not imply scientific readiness.")
            st.caption(
                "Copy generated native PlanetProfile-format `.tab` files to a PlanetProfile-ready folder. "
                "PlanetProfile reads the `.tab` files directly; the manifest is optional provenance."
            )
            planetprofile_export = st.checkbox(
                "Export generated PlanetProfile `.tab` files",
                value=True,
                help=(
                    "Copy each native PlanetProfile-format table to a PlanetProfile-ready export folder "
                    "using the filename configured for that model."
                ),
            )
            if planetprofile_export:
                export_dir = st.text_input(
                    "PlanetProfile export directory",
                    key="planetprofile_export_dir",
                    help="Destination folder for the `.tab` files that can be copied into PlanetProfile.",
                )
            else:
                st.info("PlanetProfile table export is disabled. Model-definition download above is still available.")

            if st.button("Export selected PlanetProfile table(s)", disabled=not projects_to_export or not planetprofile_export):
                commands = [
                    relabel_command(
                        export_planetprofile_command(
                            config_path,
                            project=project,
                            export_dir=export_dir,
                        ),
                        f"Export PlanetProfile table: {project}",
                    )
                    for project in projects_to_export
                ]
                run_streamlit_commands(commands)



if __name__ == "__main__":
    main()
