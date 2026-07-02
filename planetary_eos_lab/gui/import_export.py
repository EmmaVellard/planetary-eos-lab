"""Composition import/export functionality for CSV and Excel files."""
from __future__ import annotations

import json
from copy import deepcopy
from io import BytesIO, StringIO
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from planetary_eos_lab.core.config_io import list_model_entries, save_config_json
from planetary_eos_lab.core.model_schema import OXIDE_ORDER, new_model_template


def import_composition_from_csv(file_content: str | bytes) -> dict[str, float]:
    """Parse CSV and extract composition.

    Supports two formats:
    1. oxide,wt_percent columns (one row per oxide)
    2. Single row with oxide names as column headers

    Args:
        file_content: CSV file content as string or bytes

    Returns:
        Dictionary mapping oxide name to wt%

    Raises:
        ValueError: If CSV format is invalid
    """
    if isinstance(file_content, bytes):
        df = pd.read_csv(BytesIO(file_content))
    else:
        df = pd.read_csv(StringIO(file_content))

    # Format 1: oxide,wt_percent columns
    if "oxide" in df.columns and "wt_percent" in df.columns:
        composition = {
            str(row["oxide"]): float(row["wt_percent"]) for _, row in df.iterrows() if str(row["oxide"]) in OXIDE_ORDER
        }
    # Format 2: Oxide names as columns
    else:
        if df.empty:
            raise ValueError("CSV file is empty")

        composition = {}
        for oxide in OXIDE_ORDER:
            if oxide in df.columns:
                try:
                    composition[oxide] = float(df[oxide].iloc[0])
                except (ValueError, IndexError, KeyError):
                    composition[oxide] = 0.0

    # Fill missing oxides with 0
    return {oxide: composition.get(oxide, 0.0) for oxide in OXIDE_ORDER}


def export_composition_to_csv(model: dict[str, Any]) -> str:
    """Export composition as CSV string.

    Args:
        model: Model configuration dictionary

    Returns:
        CSV string
    """
    composition = model.get("oxides_wt_percent", {})

    df = pd.DataFrame([{"oxide": oxide, "wt_percent": composition.get(oxide, 0.0)} for oxide in OXIDE_ORDER])

    return df.to_csv(index=False)


def export_composition_to_excel(model: dict[str, Any]) -> bytes:
    """Export composition as Excel bytes.

    Args:
        model: Model configuration dictionary

    Returns:
        Excel file bytes
    """
    composition = model.get("oxides_wt_percent", {})

    df = pd.DataFrame([{"oxide": oxide, "wt_percent": composition.get(oxide, 0.0)} for oxide in OXIDE_ORDER])

    buffer = BytesIO()
    df.to_excel(buffer, index=False, engine="openpyxl")
    buffer.seek(0)
    return buffer.read()


def model_definitions_export_filename(selected_projects: list[str]) -> str:
    """Return a readable filename for exported model definitions."""
    if len(selected_projects) == 1:
        return f"{selected_projects[0]}_model_definition.json"
    return "planetary_eos_lab_model_definitions.json"


def export_model_definitions_to_json(models: list[dict[str, Any]], selected_projects: list[str]) -> str:
    """Export selected saved model definitions as a portable JSON document."""
    selected = [deepcopy(model) for model in models if str(model.get("project", "")) in selected_projects]
    payload = {
        "schema_version": 1,
        "description": (
            "Planetary EOS Lab saved model definitions exported from configs/models.json. "
            "This file contains composition and model metadata, not generated Perple_X output tables."
        ),
        "model_count": len(selected),
        "models": selected,
    }
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def show_import_export_panel(config_path: Path, config: dict[str, Any]):
    """Render import/export UI panel in Streamlit.

    Args:
        config_path: Path to config file
        config: Configuration dictionary
    """
    st.subheader("Import Composition")
    st.caption("Upload a CSV or Excel file with oxide concentrations")

    uploaded_file = st.file_uploader(
        "Upload CSV or Excel file",
        type=["csv", "xlsx"],
        help="File should have 'oxide' and 'wt_percent' columns, or oxide names as column headers",
    )

    if uploaded_file:
        try:
            content = uploaded_file.read()
            if uploaded_file.name.endswith(".xlsx"):
                # Convert Excel to CSV for common processing
                df = pd.read_excel(BytesIO(content), engine="openpyxl")
                content = df.to_csv(index=False).encode()

            composition = import_composition_from_csv(content)

            st.success("✅ Composition imported successfully")
            st.dataframe(
                pd.DataFrame([{"Oxide": oxide, "wt%": value} for oxide, value in composition.items()]),
                use_container_width=True,
                hide_index=True,
            )

            project_name = st.text_input(
                "Project name for imported composition",
                value=Path(uploaded_file.name).stem.replace(" ", "_"),
                help="This will be the project identifier in your config",
            )

            if st.button("💾 Save imported composition to config", type="primary"):
                # Create new model from template
                new_model = new_model_template(project_name)
                new_model["oxides_wt_percent"] = composition
                new_model["source_note"] = f"Imported from {uploaded_file.name} via GUI"

                # Add to config
                if "models" not in config:
                    config["models"] = []
                config["models"].append(new_model)

                save_config_json(config_path, config)
                st.success(f"✅ Added {project_name} to config")
                st.info("Switch to 'Build Composition' mode to edit metadata, or 'Run Pipeline' to use this model.")
                st.rerun()

        except Exception as exc:
            st.error(f"❌ Import failed: {exc}")
            st.caption(
                "Expected format: Either (1) 'oxide,wt_percent' columns with one row per oxide, "
                "or (2) a single row with oxide names as column headers."
            )

    st.divider()
    st.subheader("Export Composition")
    st.caption("Download a saved composition as CSV or Excel")

    models = list_model_entries(config)
    if not models:
        st.warning("No models available to export. Create a composition first.")
        return

    export_project = st.selectbox("Composition to export", [m["project"] for m in models])
    export_model = next(m for m in models if m["project"] == export_project)

    export_format = st.radio("Export format", ["CSV", "Excel"], horizontal=True)

    col1, col2 = st.columns([1, 1])

    with col1:
        if export_format == "CSV":
            csv_data = export_composition_to_csv(export_model)
            st.download_button(
                "📥 Download CSV",
                data=csv_data,
                file_name=f"{export_project}_composition.csv",
                mime="text/csv",
                use_container_width=True,
            )
        else:
            excel_data = export_composition_to_excel(export_model)
            st.download_button(
                "📥 Download Excel",
                data=excel_data,
                file_name=f"{export_project}_composition.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )

    with col2:
        # Preview
        with st.expander("Preview composition"):
            composition = export_model.get("oxides_wt_percent", {})
            st.dataframe(
                pd.DataFrame([{"Oxide": oxide, "wt%": composition.get(oxide, 0.0)} for oxide in OXIDE_ORDER]),
                use_container_width=True,
                hide_index=True,
            )


def bulk_import_compositions_from_csv(file_content: bytes, config_path: Path, config: dict[str, Any]) -> int:
    """Import multiple compositions from a multi-row CSV.

    CSV should have format: project,SiO2,TiO2,Al2O3,FeO,MgO,CaO,Na2O,K2O,P2O5
    Each row represents one composition.

    Args:
        file_content: CSV file bytes
        config_path: Path to config file
        config: Configuration dictionary

    Returns:
        Number of compositions imported
    """
    df = pd.read_csv(BytesIO(file_content))

    if "project" not in df.columns:
        raise ValueError("CSV must have a 'project' column with project names")

    count = 0
    for _, row in df.iterrows():
        project = str(row["project"]).strip()
        if not project:
            continue

        composition = {}
        for oxide in OXIDE_ORDER:
            if oxide in df.columns:
                try:
                    composition[oxide] = float(row[oxide])
                except (ValueError, TypeError):
                    composition[oxide] = 0.0
            else:
                composition[oxide] = 0.0

        # Create new model
        new_model = new_model_template(project)
        new_model["oxides_wt_percent"] = composition
        new_model["source_note"] = "Bulk imported via GUI CSV upload"

        if "models" not in config:
            config["models"] = []
        config["models"].append(new_model)
        count += 1

    save_config_json(config_path, config)
    return count
