from __future__ import annotations

import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import streamlit as st
import streamlit.components.v1 as components

import plot_comparisons
import run_perplex
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
    get_current_database,
    show_database_selector,
)
from planetary_eos_lab.gui.import_export import (
    export_model_definitions_to_json,
    model_definitions_export_filename,
    show_import_export_panel,
)
from planetary_eos_lab.gui.phase_diagram import show_phase_diagram_panel
from planetary_eos_lab.core.database_utils import get_database_components
from planetary_eos_lab.core.model_schema import (
    OXIDE_ORDER,
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
COMPOSITION_BUILDER_MODE = "Build Composition"
PIPELINE_MODE = "Run Pipeline"
BATCH_PROCESSING_MODE = "Batch Processing"
COMPARISON_MODE = "Compare Models"
PIPELINE_STEP_CONTROL_KEY = "pipeline_step_radio"
PIPELINE_SELECTION_KEY = "pipeline_selected_projects"
PIPELINE_MODEL_SELECTOR_KEYS = [
    PIPELINE_SELECTION_KEY,
    "generate_model_projects",
    "run_model_projects",
    "step5_plot_projects",
    "export_model_projects",
]

PIPELINE_STEPS = [
    "1. Setup & Select Models",
    "2. Generate Files",
    "3. Run Perple_X",
    "4. Validate / Export",
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


def compact_model_overview_rows(
    models: list[dict[str, Any]],
    selected_project: str | list[str] | tuple[str, ...] | set[str] | None = None,
    database: str = "stx21",
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    selected_projects = selected_project_names(selected_project)
    for model in models:
        project = str(model.get("project", ""))
        validation = validate_model_entry(model)
        try:
            total = round(raw_total(model), 2)
        except (TypeError, ValueError):
            total = None
        try:
            omitted = ", ".join(str(item["oxide"]) for item in omitted_oxides_for_model(model, database=database)) or "none"
        except (TypeError, ValueError):
            omitted = "unknown"
        rows.append(
            {
                "selected": "yes" if project in selected_projects else "",
                "project": project,
                "description": str(model.get("description", "")),
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
        validation = validate_model_entry(model)
        try:
            total = round(raw_total(model), 2)
        except (TypeError, ValueError):
            total = None
        try:
            omitted = ", ".join(str(item["oxide"]) for item in omitted_oxides_for_model(model, database=database)) or "none"
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
            "scientific status": str(model.get("scientific_status", "")),
            "model scope": str(model.get("model_scope", "")),
            "PlanetProfile readiness": str(model.get("planetprofile_readiness", "")),
            "input total wt%": total,
            "omitted from BUILD": omitted,
            "PlanetProfile filename": str(model.get("planetprofile_filename", "")),
            "based on literature values": "yes" if model.get("literature_proxy") else "no",
            "use as final Moon mantle EOS": "yes" if use_as_final_moon_mantle_eos(model) else "no",
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
        st.warning("This is a surface-proxy smoke test, not a final lunar mantle EOS model.")
    if not use_as_final_moon_mantle_eos(model):
        st.info("Use as final Moon mantle EOS: no")


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
        with st.expander(f"{project}: composition review", expanded=len(selected_projects) == 1):
            show_scientific_guardrail(model, database=database)
            st.metric("Input oxide total, wt%", f"{raw_total(model):.2f}")
            show_oxide_table(oxide_table_rows(model, database=database), database=database)
            st.caption(f"Active {database} BUILD components")
            st.code(active_component_text(database), language="text")
            omitted = omitted_oxides_for_model(model, database=database)
            if omitted:
                st.warning(
                    f"These oxides are present in the composition record but omitted from {database} BUILD: "
                    + ", ".join(str(item["oxide"]) for item in omitted)
                )


def show_model_catalog(
    models: list[dict[str, Any]],
    selected_project: str | list[str] | tuple[str, ...] | set[str] | None = None,
    database: str = "stx21",
) -> None:
    st.dataframe(
        compact_model_overview_rows(models, selected_project, database=database),
        width="stretch",
        hide_index=True,
        column_config={
            "input total wt%": st.column_config.NumberColumn(format="%.2f"),
        },
    )
    with st.expander("Detailed metadata and oxide values"):
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


def set_workspace_mode(mode: str) -> None:
    st.session_state["workspace_mode"] = mode


def run_streamlit_command(command: PipelineCommand, *, progress_label: str | None = None) -> bool:
    label = progress_label or command.label
    status = st.status(f"... {label}", state="running", expanded=True)
    with status:
        st.caption("Command")
        st.code(command.display, language="bash")
        output_box = st.empty()
    output_lines: list[str] = []
    try:
        process = subprocess.Popen(
            command.command,
            cwd=str(command.cwd),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
    except OSError as exc:
        status.update(label=f"Could not start: {label}", state="error", expanded=True)
        with status:
            st.error(f"Could not start command: {exc}")
        return False

    assert process.stdout is not None
    for line in process.stdout:
        output_lines.append(line)
        output_box.code("".join(output_lines), language="text")
    returncode = process.wait()
    output_box.code("".join(output_lines), language="text")
    if returncode == 0:
        status.update(label=f"Complete: {label}", state="complete", expanded=False)
        return True

    status.update(label=f"Failed: {label}", state="error", expanded=True)
    with status:
        st.error(f"Command failed with return code {returncode}.")
    return False


def run_streamlit_commands(commands: list[PipelineCommand]) -> None:
    total = len(commands)
    completed = 0
    for index, command in enumerate(commands, start=1):
        remaining = total - index
        suffix = f"{remaining} left" if remaining else "last run"
        ok = run_streamlit_command(
            command,
            progress_label=f"{index}/{total} {command.label} ({suffix})",
        )
        if not ok:
            st.error(f"Stopped after {completed}/{total} completed run(s).")
            return
        completed += 1
    st.success(f"Finished {completed}/{total} run(s).")


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
    st.header("Composition Builder")
    st.caption(
        "Create or revise source compositions stored in `configs/models.json`. "
        "After saving, the composition becomes a saved model that can be selected and run through the pipeline."
    )

    st.subheader("Thermodynamic Setup")
    st.caption(
        "This choice controls which oxides are modeled by the default BUILD template and which are saved "
        "as source-only metadata. Changing it changes the oxide fields and warnings shown below."
    )
    database = show_database_selector(config, config_path)
    st.info(
        f"Build Composition is currently using `{database}`. Saved compositions keep all oxide values, "
        "but the modeled/source-only split follows the active thermodynamic setup."
    )
    st.divider()

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
    elif copying_existing:
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
        st.info("This creates a new saved model. The original composition is not changed.")
    else:
        selected_builder_project = st.selectbox(
            "Saved composition to edit",
            options=[str(model.get("project", "")) for model in models],
            format_func=lambda project: model_label(next(model for model in models if model.get("project") == project)),
        )
        base_model = deepcopy(next(model for model in models if model.get("project") == selected_builder_project))
        choice_key = f"edit_{selected_builder_project}"

    edited = deepcopy(base_model)
    meta_col, oxide_col = st.columns([1, 1.25])
    with meta_col:
        st.subheader("Model")
        st.caption("Only the project name and oxide values are required for a new saved composition. The other metadata has safe defaults.")
        edited["project"] = st.text_input(
            "Project name",
            value="" if creating_new else str(base_model.get("project", "")),
            placeholder=str(base_model.get("project", "my_surface_proxy")),
            key=f"workspace_project_{choice_key}",
            help="Required. This becomes the Perple_X project name and output folder name.",
        )
        edited["description"] = st.text_input(
            "Description",
            value="" if creating_new else str(base_model.get("description", "")),
            placeholder=str(base_model.get("description", "User-defined composition")),
            key=f"workspace_description_{choice_key}",
            help="Optional but useful for remembering what this composition represents.",
        )
        if not edited["description"].strip():
            edited["description"] = str(base_model.get("description", "User-defined composition"))

        with st.expander("Optional provenance and PlanetProfile metadata"):
            filename_default = (
                f"{edited['project'].strip()}_PerpleX.tab"
                if edited["project"].strip()
                else str(base_model.get("planetprofile_filename", "my_surface_proxy_PerpleX.tab"))
            )
            planetprofile_filename = st.text_input(
                "PlanetProfile filename",
                value="" if creating_new else str(base_model.get("planetprofile_filename", "")),
                placeholder=filename_default,
                key=f"workspace_pp_filename_{choice_key}",
            )
            edited["planetprofile_filename"] = planetprofile_filename.strip() or filename_default
            edited["scientific_status"] = (
                st.text_input(
                    "Scientific status",
                    value="" if creating_new else str(base_model.get("scientific_status", "")),
                    placeholder=str(base_model.get("scientific_status", "")),
                    key=f"workspace_status_{choice_key}",
                ).strip()
                or str(base_model.get("scientific_status", "surface_proxy_smoke_test"))
            )
            edited["model_scope"] = (
                st.text_input(
                    "Model scope",
                    value="" if creating_new else str(base_model.get("model_scope", "")),
                    placeholder=str(base_model.get("model_scope", "")),
                    key=f"workspace_scope_{choice_key}",
                ).strip()
                or str(base_model.get("model_scope", "surface_terrane_proxy"))
            )
            edited["planetprofile_readiness"] = (
                st.text_input(
                    "PlanetProfile readiness",
                    value="" if creating_new else str(base_model.get("planetprofile_readiness", "")),
                    placeholder=str(base_model.get("planetprofile_readiness", "")),
                    key=f"workspace_readiness_{choice_key}",
                ).strip()
                or str(base_model.get("planetprofile_readiness", "mechanically_exportable_not_scientifically_final"))
            )
            edited["composition_interpretation"] = (
                st.text_area(
                    "Composition interpretation",
                    value="" if creating_new else str(base_model.get("composition_interpretation", "")),
                    placeholder=str(base_model.get("composition_interpretation", "")),
                    key=f"workspace_interpretation_{choice_key}",
                ).strip()
                or str(base_model.get("composition_interpretation", "User-defined composition."))
            )
            edited["source_note"] = (
                st.text_area(
                    "Source note",
                    value="" if creating_new else str(base_model.get("source_note", "")),
                    placeholder=str(base_model.get("source_note", "")),
                    key=f"workspace_source_{choice_key}",
                ).strip()
                or str(base_model.get("source_note", "Entered through the Streamlit GUI."))
            )
            edited["literature_proxy"] = st.checkbox(
                "Based on literature values",
                value=bool(base_model.get("literature_proxy", False)),
                key=f"workspace_literature_values_{choice_key}",
                help="Use this when the composition comes from a publication or tabulated literature average.",
            )

    base_oxides = base_model.get("oxides_wt_percent", {})
    if not isinstance(base_oxides, dict):
        base_oxides = {}
    edited["oxides_wt_percent"] = {}
    with oxide_col:
        from planetary_eos_lab.core.database_utils import get_active_oxides, get_source_only_oxides
        active_oxides = get_active_oxides(database)
        source_only_oxides = get_source_only_oxides(database)
        modeled_oxides = [oxide for oxide in OXIDE_ORDER if oxide in active_oxides]

        st.subheader(f"Modeled Oxides for {database}, wt%")
        st.caption(f"These oxides are passed to the active {database} BUILD template.")
        modeled_columns = st.columns(3)
        for index, oxide in enumerate(modeled_oxides):
            with modeled_columns[index % 3]:
                edited["oxides_wt_percent"][oxide] = st.number_input(
                    oxide,
                    value=float(base_oxides.get(oxide, 0.0)),
                    min_value=0.0,
                    step=0.01,
                    format="%.2f",
                    key=f"workspace_oxide_{choice_key}_{oxide}",
                )
        st.subheader(f"Source-Only Oxides for {database}, wt%")
        st.caption(f"Saved in the composition record, plots, and warnings, but not passed to {database} BUILD.")
        source_columns = st.columns(3)
        for index, oxide in enumerate(source_only_oxides):
            with source_columns[index % 3]:
                edited["oxides_wt_percent"][oxide] = st.number_input(
                    oxide,
                    value=float(base_oxides.get(oxide, 0.0)),
                    min_value=0.0,
                    step=0.01,
                    format="%.2f",
                    key=f"workspace_source_oxide_{choice_key}_{oxide}",
                )
        if source_only_oxides:
            st.info(
                f"The {database} database models "
                + ", ".join(modeled_oxides)
                + f". {', '.join(source_only_oxides)} are source-only and require a different database to model."
            )
        with st.expander("Why can't I add other elements here?"):
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
    if validation.errors:
        st.error("Cannot save yet: " + "; ".join(validation.errors))
    if duplicate_project:
        st.error(f"Cannot save yet: another saved model already uses project `{edited_project}`.")
    for warning in validation.warnings:
        st.warning(warning)

    preview_col, guardrail_col = st.columns([1.3, 1])
    with preview_col:
        st.metric("Input oxide total, wt%", f"{raw_total(edited):.2f}")
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
            st.bar_chart({"normalized wt%": {row["oxide"]: round(row["normalized_wt_percent"], 2) for row in plot_rows}})
    with guardrail_col:
        if validation.ok:
            show_scientific_guardrail(edited, database=database)
            omitted = omitted_oxides_for_model(edited, database=database)
            if omitted:
                st.warning(
                    f"Omitted from {database} BUILD: "
                    + ", ".join(f"{item['oxide']}={item['normalized_wt_percent']:.2f} wt%" for item in omitted)
                )
        st.caption(f"Active {database} BUILD components")
        st.code(active_component_text(database), language="text")

    if st.button("Save composition to config", disabled=not validation.ok or duplicate_project):
        updated_config = replace_model_entry(config, source_project, edited)
        write_config(config_path, updated_config)
        st.info("After saving, switch to Run Pipeline and select this saved model in the sidebar.")

    return edited if validation.ok else base_model


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
        components.html(plot_comparisons.composition_plot_svg(plot_models), height=585, scrolling=False)
        try:
            components.html(plot_comparisons.property_plot_svg(plot_models), height=925, scrolling=False)
        except (FileNotFoundError, ValueError) as exc:
            st.info(f"Property comparison plot is unavailable for this selection: {exc}")
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        st.warning(f"Could not render selected comparison plots: {exc}")


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
        "Current included lunar models are surface or terrane proxy smoke tests, "
        "not final lunar mantle EOS models."
    )

    if "workspace_mode" not in st.session_state:
        st.session_state["workspace_mode"] = PIPELINE_MODE
    if "workflow_step_index" not in st.session_state:
        set_workflow_step(0)
    else:
        set_workflow_step(int(st.session_state.get("workflow_step_index", 0)))

    with st.sidebar:
        st.header("Workspace")
        st.caption("Main task")
        for mode in [COMPOSITION_BUILDER_MODE, BATCH_PROCESSING_MODE, PIPELINE_MODE, COMPARISON_MODE]:
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
        if workspace_mode == PIPELINE_MODE:
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
        else:
            st.caption("Create or edit saved models, then switch to Run Pipeline when you are ready.")
        st.divider()

        # Auto-save controls
        show_autosave_controls()

        st.divider()
        st.caption("Local configuration")
        config_input = st.text_input("Config path", value=str(DEFAULT_CONFIG_PATH.relative_to(REPO_ROOT)))

    config_path = resolve_path(config_input, REPO_ROOT)

    if not config_path.exists():
        st.header("Create Local Config" if workspace_mode == COMPOSITION_BUILDER_MODE else "Step 1. Setup & Select Models")
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
    if not st.session_state.get("planetprofile_export_dir"):
        st.session_state["planetprofile_export_dir"] = str(DEFAULT_PLANETPROFILE_EXPORT_DIR)

    export_dir = str(st.session_state.get("planetprofile_export_dir", REPO_ROOT / "outputs" / "planetprofile_export"))

    if workspace_mode == COMPOSITION_BUILDER_MODE:
        composition_workspace(config_path, config, models)
        st.divider()

        with st.expander("Import/Export Compositions"):
            show_import_export_panel(config_path, config)

        st.divider()
        st.subheader("Saved models")
        show_model_catalog(models, database=current_database)
        with st.expander("Delete saved model(s)"):
            delete_model_panel(config_path, config, models)
        return

    if workspace_mode == BATCH_PROCESSING_MODE:
        show_batch_workspace(config_path, config, models)
        return

    if workspace_mode == COMPARISON_MODE:
        show_comparison_workspace(models, config_path)
        return

    if step == "1. Setup & Select Models":
        st.header("Step 1. Setup & Select Models")
        st.write(f"Current working directory: `{Path.cwd()}`")
        st.write(f"Repository root: `{REPO_ROOT}`")
        st.write(f"Resolved config path: `{config_path}`")

        st.subheader("Configuration")
        config_col1, config_col2 = st.columns([1, 1])

        with config_col1:
            st.caption("Perple_X Installation")
            perplex_dir = st.text_input("Perple_X directory", value=str(config.get("perplex_dir", "")))
            st.caption(
                "Path to find BUILD, VERTEX, WERAMI executables and datafiles. "
                "Save when you change machines or Perple_X locations."
            )
            if st.button("Save Perple_X path to config"):
                write_config(config_path, update_perplex_dir(config, perplex_dir))

        with config_col2:
            st.caption("Thermodynamic Database")
            current_database = show_database_selector(config, config_path)

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
        show_selected_model_reviews(models, selected_projects, database=current_database)

        st.subheader("Saved model catalog")
        st.caption(
            "Use this table to compare saved compositions before generating files. "
            "The selected marker only reflects the models selected above."
        )
        show_model_catalog(models, selected_projects, database=current_database)
        with st.expander("Delete saved model(s)"):
            delete_model_panel(config_path, config, models)

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
        if not projects_to_generate:
            st.info("Select at least one saved model to generate.")
        if st.button("Generate selected file(s)", disabled=not projects_to_generate):
            commands = [
                relabel_command(
                    generate_compositions_command(config_path, project),
                    f"Generate files: {project}",
                )
                for project in projects_to_generate
            ]
            run_streamlit_commands(commands)

    elif step == "3. Run Perple_X":
        st.header("Step 3. Run Perple_X")
        st.warning("Perple_X must be installed locally. The included lunar models are still smoke-test surface proxies.")
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
        if not projects_to_run:
            st.info("Select at least one saved model to run.")
        if st.button("Run selected model(s)", disabled=not projects_to_run):
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
            run_streamlit_commands(commands)

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
