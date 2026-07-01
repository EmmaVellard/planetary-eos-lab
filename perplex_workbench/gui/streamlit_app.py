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

from perplex_workbench.core.config_io import (
    DEFAULT_CONFIG_PATH,
    EXAMPLE_CONFIG_PATH,
    copy_example_config,
    delete_model_entry,
    list_model_entries,
    load_config_json,
    replace_model_entry,
    resolve_path,
    save_config_json,
    update_perplex_dir,
)
from perplex_workbench.gui.autosave import show_autosave_controls
from perplex_workbench.gui.batch_processor import show_batch_workspace
from perplex_workbench.gui.comparison_tools import show_comparison_workspace
from perplex_workbench.gui.database_selector import (
    get_current_database,
    show_database_selector,
)
from perplex_workbench.gui.import_export import show_import_export_panel
from perplex_workbench.gui.phase_diagram import show_phase_diagram_panel
from perplex_workbench.gui.validation_enhanced import show_enhanced_validation
from perplex_workbench.core.model_schema import (
    ACTIVE_BUILD_COMPONENTS,
    OXIDE_ORDER,
    SOURCE_ONLY_OXIDES,
    composition_plot_rows,
    new_model_template,
    omitted_oxides_for_model,
    oxide_table_rows,
    raw_total,
    scientific_guardrail_text,
    use_as_final_moon_mantle_eos,
    validate_model_entry,
)
from perplex_workbench.core.pipeline_runner import (
    PipelineCommand,
    export_planetprofile_command,
    full_pipeline_command,
    generate_compositions_command,
)
from perplex_workbench.core.validation_summary import (
    comparison_plot_paths,
    export_manifest_path,
    export_manifest_table_rows,
    model_output_paths,
    read_export_manifest,
    read_text_if_exists,
    validation_status,
)


st.set_page_config(page_title="Perple_X Workbench", layout="wide")

COMPOSITION_BUILDER_MODE = "Build Composition"
PIPELINE_MODE = "Run Pipeline"
BATCH_PROCESSING_MODE = "Batch Processing"
COMPARISON_MODE = "Compare Models"

PIPELINE_STEPS = [
    "1. Setup & Select Model",
    "2. Review",
    "3. Generate Files",
    "4. Run Perple_X",
    "5. Validate / Export",
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
        section[data-testid="stSidebar"] div.stButton > button {
            justify-content: flex-start;
            border-radius: 7px;
            min-height: 2.35rem;
            transition: background-color 120ms ease, border-color 120ms ease, color 120ms ease;
        }
        section[data-testid="stSidebar"] div.stButton > button:hover {
            border-color: #d84b5b;
            background: rgba(216, 75, 91, 0.08);
            color: #30283a;
        }
        section[data-testid="stSidebar"] div.stButton > button[kind="primary"]:hover {
            background: #c43d50;
            border-color: #c43d50;
            color: #ffffff;
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


def compact_model_overview_rows(models: list[dict[str, Any]], selected_project: str | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for model in models:
        project = str(model.get("project", ""))
        validation = validate_model_entry(model)
        try:
            total = round(raw_total(model), 2)
        except (TypeError, ValueError):
            total = None
        try:
            omitted = ", ".join(str(item["oxide"]) for item in omitted_oxides_for_model(model)) or "none"
        except (TypeError, ValueError):
            omitted = "unknown"
        rows.append(
            {
                "selected": "yes" if project == selected_project else "",
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


def detailed_model_overview_rows(models: list[dict[str, Any]], selected_project: str | None = None) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for model in models:
        project = str(model.get("project", ""))
        validation = validate_model_entry(model)
        try:
            total = round(raw_total(model), 2)
        except (TypeError, ValueError):
            total = None
        try:
            omitted = ", ".join(str(item["oxide"]) for item in omitted_oxides_for_model(model)) or "none"
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
            "selected for run": "yes" if project == selected_project else "",
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


def show_model_catalog(models: list[dict[str, Any]], selected_project: str | None = None) -> None:
    st.dataframe(
        compact_model_overview_rows(models, selected_project),
        width="stretch",
        hide_index=True,
        column_config={
            "input total wt%": st.column_config.NumberColumn(format="%.2f"),
        },
    )
    with st.expander("Detailed metadata and oxide values"):
        st.dataframe(
            detailed_model_overview_rows(models, selected_project),
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


def delete_model_panel(
    config_path: Path,
    config: dict[str, Any],
    models: list[dict[str, Any]],
    selected_project: str,
) -> None:
    st.subheader("Delete Saved Model")
    st.caption(
        "This removes a model block from `configs/models.json` only. "
        "Generated composition files, Perple_X work folders, and exported tables are left untouched."
    )
    if len(models) <= 1:
        st.warning("At least one saved model must remain in the config.")
        return

    project_options = [str(model.get("project", "")) for model in models]
    default_index = project_options.index(selected_project) if selected_project in project_options else 0
    project_to_delete = st.selectbox(
        "Saved model to delete",
        options=project_options,
        index=default_index,
        key="delete_model_project",
        format_func=lambda project: model_label(next(model for model in models if model.get("project") == project)),
    )
    if st.button("Delete saved model", type="secondary"):
        st.session_state["delete_model_dialog_project"] = project_to_delete

    pending_delete = st.session_state.get("delete_model_dialog_project")
    if isinstance(pending_delete, str) and pending_delete:
        confirm_delete_model_dialog(config_path, config, pending_delete)


def set_workflow_step(index: int) -> None:
    bounded = max(0, min(index, len(PIPELINE_STEPS) - 1))
    st.session_state["workflow_step_index"] = bounded
    st.session_state["workflow_step_choice"] = PIPELINE_STEPS[bounded]


def set_workspace_mode(mode: str) -> None:
    st.session_state["workspace_mode"] = mode


def run_streamlit_command(command: PipelineCommand) -> None:
    st.caption(command.label)
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
        st.error(f"Could not start command: {exc}")
        return

    assert process.stdout is not None
    for line in process.stdout:
        output_lines.append(line)
        output_box.code("".join(output_lines), language="text")
    returncode = process.wait()
    output_box.code("".join(output_lines), language="text")
    if returncode == 0:
        st.success("Command completed successfully.")
    else:
        st.error(f"Command failed with return code {returncode}.")


def editable_model_form(config_path: Path, config: dict[str, Any], model: dict[str, Any]) -> None:
    database = get_current_database(config)
    validation = validate_model_entry(model)
    if validation.errors:
        st.error("Current model has validation errors: " + "; ".join(validation.errors))
    for warning in validation.warnings:
        st.warning(warning)

    rows = oxide_table_rows(model, database=database)
    show_oxide_table(rows, database=database)
    omitted = omitted_oxides_for_model(model)
    if omitted:
        st.warning(
            "Omitted from default BUILD: "
            + ", ".join(f"{item['oxide']}={item['normalized_wt_percent']:.2f} wt%" for item in omitted)
        )

    st.caption("Default active BUILD components")
    st.code(" ".join(component for _, component in ACTIVE_BUILD_COMPONENTS), language="text")

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
        from perplex_workbench.core.database_utils import get_active_oxides, get_source_only_oxides
        active_oxides = get_active_oxides(database)
        source_only_oxides = get_source_only_oxides(database)
        modeled_oxides = [oxide for oxide in OXIDE_ORDER if oxide in active_oxides]

        st.subheader("Modeled Oxides, wt%")
        st.caption(f"These oxides are passed to the {database} BUILD template.")
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
        st.subheader("Source-Only Oxides, wt%")
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
            omitted = omitted_oxides_for_model(edited)
            if omitted:
                st.warning(
                    "Omitted from default BUILD: "
                    + ", ".join(f"{item['oxide']}={item['normalized_wt_percent']:.2f} wt%" for item in omitted)
                )
        st.caption("Default active BUILD components")
        st.code(" ".join(component for _, component in ACTIVE_BUILD_COMPONENTS), language="text")

    if st.button("Save composition to config", disabled=not validation.ok or duplicate_project):
        updated_config = replace_model_entry(config, source_project, edited)
        write_config(config_path, updated_config)
        st.info("After saving, switch to Run Pipeline and select this saved model in the sidebar.")

    return edited if validation.ok else base_model


def show_outputs(config_path: Path, models: list[dict[str, Any]], export_dir: str) -> None:
    for model in models:
        project = str(model.get("project", ""))
        if not project:
            continue
        paths = model_output_paths(model, config_path)
        report = read_text_if_exists(paths.validation_report)
        status = validation_status(report)
        with st.expander(f"{project}: validation {status}"):
            if status == "pass":
                st.success("Validation status: PASS")
            elif status == "fail":
                st.error("Validation status: FAIL")
            else:
                st.info("Validation report is not available yet.")
            if report:
                st.code(report, language="text")
            omissions = read_text_if_exists(paths.oxide_omissions)
            if omissions:
                st.warning(omissions)

            output_rows = [
                ("raw WERAMI table", paths.raw_werami_table),
                ("PlanetProfile table", paths.planetprofile_table),
                ("native PlanetProfile table", paths.native_planetprofile_table),
                ("build log", paths.build_log),
                ("vertex log", paths.vertex_log),
                ("werami log", paths.werami_log),
            ]
            st.dataframe(
                [
                    {"artifact": label, "path": str(path), "exists": path.exists()}
                    for label, path in output_rows
                ],
                width="stretch",
                hide_index=True,
            )

    st.subheader("Plots")
    for label, path in comparison_plot_paths(config_path).items():
        st.write(f"{label}: `{path}`")
        if path.exists():
            st.image(str(path))

    manifest_path = export_manifest_path(config_path, export_dir)
    st.subheader("Export manifest")
    st.write(f"`{manifest_path}`")
    manifest = read_export_manifest(manifest_path)
    if manifest:
        st.warning("Export success does not imply scientific readiness.")
        st.caption(
            "PlanetProfile does not need this manifest to read a table. It is a provenance receipt "
            "for humans and scripts, so exported smoke-test tables are not confused with final EOS models."
        )
        rows = export_manifest_table_rows(manifest)
        if rows:
            st.dataframe(rows, width="stretch", hide_index=True)
        with st.expander("Raw JSON manifest"):
            st.json(manifest)


def main() -> None:
    inject_styles()
    st.title("Perple_X Workbench")
    st.warning(
        "Current included lunar models are surface or terrane proxy smoke tests, "
        "not final lunar mantle EOS models."
    )

    if "workspace_mode" not in st.session_state:
        st.session_state["workspace_mode"] = PIPELINE_MODE
    if "workflow_step_index" not in st.session_state:
        set_workflow_step(0)

    with st.sidebar:
        st.header("Workspace")
        st.caption("Main task")
        for mode in [PIPELINE_MODE, COMPOSITION_BUILDER_MODE, BATCH_PROCESSING_MODE, COMPARISON_MODE]:
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
            st.caption("Pipeline steps")
            for index, pipeline_step in enumerate(PIPELINE_STEPS):
                st.button(
                    pipeline_step,
                    key=f"pipeline_step_{index}",
                    type="primary" if step_index == index else "secondary",
                    on_click=set_workflow_step,
                    args=(index,),
                    width="stretch",
                )
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
            st.caption("Create or edit a saved model, then switch to Run Pipeline when you are ready.")
        st.divider()

        # Auto-save controls
        show_autosave_controls()

        st.divider()
        st.caption("Local configuration")
        config_input = st.text_input("Config path", value=str(DEFAULT_CONFIG_PATH.relative_to(REPO_ROOT)))

    config_path = resolve_path(config_input, REPO_ROOT)

    if not config_path.exists():
        st.header("Create Local Config" if workspace_mode == COMPOSITION_BUILDER_MODE else "Step 1. Setup & Select Model")
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

    with st.sidebar:
        st.caption("Saved model used by review, generate, run, and export steps")
        selected_project = st.selectbox(
            "Selected saved model",
            options=[str(model.get("project", "")) for model in models],
            format_func=lambda project: model_label(next(model for model in models if model.get("project") == project)),
            help=(
                "This is the saved model in configs/models.json that the later pipeline buttons use. "
                "If you create or edit a model in the Composition Builder, save it first, then select it here."
            ),
        )
        export_dir = st.text_input(
            "PlanetProfile export directory",
            value=str(REPO_ROOT / "outputs" / "planetprofile_export"),
        )

    selected_model = next(model for model in models if model.get("project") == selected_project)

    if workspace_mode == COMPOSITION_BUILDER_MODE:
        composition_workspace(config_path, config, models)
        st.divider()

        # Import/Export panel
        with st.expander("📁 Import/Export Compositions"):
            show_import_export_panel(config_path, config)

        st.divider()
        st.subheader("Saved models")
        show_model_catalog(models, selected_project)
        with st.expander("Delete a saved model"):
            delete_model_panel(config_path, config, models, selected_project)
        return

    if workspace_mode == BATCH_PROCESSING_MODE:
        show_batch_workspace(config_path, config, models)
        return

    if workspace_mode == COMPARISON_MODE:
        show_comparison_workspace(models, config_path)
        return

    if step == "1. Setup & Select Model":
        st.header("Step 1. Setup & Select Model")
        st.write(f"Current working directory: `{Path.cwd()}`")
        st.write(f"Repository root: `{REPO_ROOT}`")
        st.write(f"Resolved config path: `{config_path}`")
        st.subheader("Saved model selected for the pipeline")
        st.success(f"The next steps will use `{selected_project}`.")
        st.caption(
            "Use the sidebar selector to switch between saved models. "
            "To create or edit a source composition, switch the sidebar main task to Build Composition."
        )
        show_scientific_guardrail(selected_model)

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
        st.subheader("Saved model catalog")
        st.caption(
            "Use this table to compare saved compositions before running the pipeline. "
            "The selected model is the one used by Review, Generate, Run, and Export."
        )
        show_model_catalog(models, selected_project)
        with st.expander("Delete a saved model"):
            delete_model_panel(config_path, config, models, selected_project)

    elif step == "2. Review":
        database = get_current_database(config)
        st.header("Step 2. Review")
        st.subheader(selected_project)
        show_scientific_guardrail(selected_model, database=database)
        st.metric("Input oxide total, wt%", f"{raw_total(selected_model):.2f}")
        review_rows = oxide_table_rows(selected_model, database=database)
        st.dataframe(rounded_oxide_rows(review_rows, database=database), width="stretch", hide_index=True)
        st.subheader("Default BUILD Components")
        st.code(" ".join(component for _, component in ACTIVE_BUILD_COMPONENTS), language="text")
        omitted = omitted_oxides_for_model(selected_model)
        if omitted:
            st.warning(
                "These oxides are present in the composition record but omitted from default BUILD: "
                + ", ".join(str(item["oxide"]) for item in omitted)
            )
        st.info("Next step: generate composition files. This writes generated artifacts from the saved config.")

    elif step == "3. Generate Files":
        st.header("Step 3. Generate Files")
        st.write("This step runs `make_compositions.py` and writes generated files under `compositions/`.")
        st.subheader("Generate selected saved model")
        st.caption(f"Only writes generated composition files for `{selected_project}`.")
        if st.button("Generate selected composition"):
            run_streamlit_command(generate_compositions_command(config_path, selected_project))
        st.divider()
        st.subheader("Generate all saved models")
        st.caption("Writes generated composition files for every model listed in `configs/models.json`.")
        if st.button("Generate all compositions"):
            run_streamlit_command(generate_compositions_command(config_path))

    elif step == "4. Run Perple_X":
        st.header("Step 4. Run Perple_X")
        st.warning("Perple_X must be installed locally. The included lunar models are still smoke-test surface proxies.")
        st.subheader("Run selected saved model")
        st.caption(f"Runs BUILD/VERTEX/WERAMI/validation only for `{selected_project}`.")
        if st.button("Run selected model"):
            run_streamlit_command(full_pipeline_command(config_path, project=selected_project))
        st.divider()
        st.subheader("Run all saved models")
        st.caption("Runs the full pipeline for every model listed in `configs/models.json`.")
        if st.button("Run all models"):
            run_streamlit_command(full_pipeline_command(config_path))
        st.divider()
        st.subheader("Run all saved models and export")
        st.caption("Runs all models, validates them, then copies PlanetProfile-format tables to the export directory.")
        if st.button("Run all and export"):
            run_streamlit_command(
                full_pipeline_command(
                    config_path,
                    export_planetprofile=True,
                    export_dir=export_dir,
                )
            )

    elif step == "5. Validate / Export":
        st.header("Step 5. Validate / Export")

        # Tabs for different views
        tab1, tab2, tab3 = st.tabs(["📊 Validation & Output", "📈 Phase Diagram", "📁 Export"])

        with tab1:
            show_outputs(config_path, models, export_dir)

        with tab2:
            show_phase_diagram_panel(models, selected_project, config_path)

        with tab3:
            st.subheader("PlanetProfile Export")
            st.warning("Export success does not imply scientific readiness.")
            st.caption(
                "The export manifest is not required by PlanetProfile, but it is strongly useful as a readable "
                "record of what was exported and which scientific caveats apply."
            )
            st.subheader("Export selected saved model")
            if st.button("Export selected model"):
                run_streamlit_command(
                    export_planetprofile_command(
                        config_path,
                        project=selected_project,
                        export_dir=export_dir,
                    )
                )
            st.divider()
            st.subheader("Export all saved models")
            if st.button("Export all models"):
                run_streamlit_command(export_planetprofile_command(config_path, export_dir=export_dir))



if __name__ == "__main__":
    main()
