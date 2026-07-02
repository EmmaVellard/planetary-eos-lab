"""Phase diagram visualization with Plotly."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import plotly.graph_objects as go
import streamlit as st

from perplex_workbench.core.phase_parser import get_pt_grid_from_tab, parse_vertex_log
from perplex_workbench.core.validation_summary import model_output_paths


PROPERTY_OPTIONS = {
    "Density": {
        "canonical": "rho_kgm3",
        "label": "Density",
        "unit": "kg/m3",
        "colorbar": "rho (kg/m3)",
        "colorscale": "Viridis",
    },
    "P-wave velocity": {
        "canonical": "vp_kms",
        "label": "P-wave velocity",
        "unit": "km/s",
        "colorbar": "Vp (km/s)",
        "colorscale": "Plasma",
    },
    "S-wave velocity": {
        "canonical": "vs_kms",
        "label": "S-wave velocity",
        "unit": "km/s",
        "colorbar": "Vs (km/s)",
        "colorscale": "Cividis",
    },
}
GRID_ONLY_OPTION = "None (grid only)"
HEATMAP_DISPLAY = "Heatmap"
GRID_POINT_DISPLAY = "Grid points"
PHASE_MODEL_SELECTOR_KEY = "phase_diagram_project"


def property_points_from_tab(tab_path: Path, property_choice: str) -> tuple[list[float], list[float], list[float], dict[str, str]]:
    """Read P-T-property points from a PlanetProfile table."""
    from validate_tab import column_indices, read_tab

    property_config = PROPERTY_OPTIONS[property_choice]
    tab = read_tab(tab_path)
    indices = column_indices(tab.headers)
    p_index = indices["p_bar"]
    t_index = indices["t_k"]
    property_index = indices[property_config["canonical"]]

    t_points: list[float] = []
    p_points: list[float] = []
    property_values: list[float] = []
    for row in tab.rows:
        pressure = row[p_index]
        temperature = row[t_index]
        value = row[property_index]
        if abs(pressure) < 1e90 and abs(temperature) < 1e90 and abs(value) < 1e90:
            p_points.append(pressure * 1e-4)
            t_points.append(temperature)
            property_values.append(value)

    return t_points, p_points, property_values, property_config


def property_grid_from_tab(
    tab_path: Path,
    property_choice: str,
) -> tuple[list[float], list[float], list[list[float | None]], int, dict[str, str]]:
    """Read gridded P-T-property values from a PlanetProfile table."""
    from validate_tab import column_indices, read_tab

    property_config = PROPERTY_OPTIONS[property_choice]
    tab = read_tab(tab_path)
    indices = column_indices(tab.headers)
    p_index = indices["p_bar"]
    t_index = indices["t_k"]
    property_index = indices[property_config["canonical"]]

    values_by_point: dict[tuple[float, float], float] = {}
    for row in tab.rows:
        pressure = row[p_index]
        temperature = row[t_index]
        value = row[property_index]
        if abs(pressure) < 1e90 and abs(temperature) < 1e90 and abs(value) < 1e90:
            values_by_point[(temperature, pressure * 1e-4)] = value

    temperatures = sorted({temperature for temperature, _ in values_by_point})
    pressures = sorted({pressure for _, pressure in values_by_point})
    z_values = [
        [values_by_point.get((temperature, pressure)) for temperature in temperatures]
        for pressure in pressures
    ]

    return temperatures, pressures, z_values, len(values_by_point), property_config


def grid_points_from_tab(tab_path: Path) -> tuple[list[float], list[float]]:
    """Read P-T grid points from a PlanetProfile table."""
    from validate_tab import column_indices, read_tab

    tab = read_tab(tab_path)
    indices = column_indices(tab.headers)
    p_index = indices["p_bar"]
    t_index = indices["t_k"]

    t_points: list[float] = []
    p_points: list[float] = []
    for row in tab.rows:
        pressure = row[p_index]
        temperature = row[t_index]
        if abs(pressure) < 1e90 and abs(temperature) < 1e90:
            p_points.append(pressure * 1e-4)
            t_points.append(temperature)

    return t_points, p_points


def plot_phase_diagram_interactive(
    model: dict[str, Any],
    output_dir: Path,
    property_choice: str = "Density",
    display_mode: str = HEATMAP_DISPLAY,
):
    """Create interactive P-T phase diagram with Plotly.

    Note: Phase diagrams require structured phase data from VERTEX.
    This implementation shows the P-T grid coverage and property contours
    as a fallback when phase info is unavailable.

    Args:
        model: Model configuration
        output_dir: Output directory path
    """
    project = model.get("project", "unknown")

    # Try to parse VERTEX log first
    vertex_log = output_dir / "vertex.log"
    phase_fields = []

    if vertex_log.exists():
        phase_fields = parse_vertex_log(vertex_log)

    # Fallback: show P-T coverage with property contours
    tab_path = output_dir / f"{project}_planetprofile.tab"

    if not tab_path.exists():
        st.warning("⚠️ No output file found. Run Perple_X first to generate phase diagram.")
        return

    # Get P-T grid
    pressures_bar, temperatures_k = get_pt_grid_from_tab(tab_path)

    if not pressures_bar or not temperatures_k:
        st.error("❌ Could not extract P-T grid from output file")
        return

    fig = go.Figure()

    point_count = 0
    try:
        if property_choice in PROPERTY_OPTIONS:
            if display_mode == HEATMAP_DISPLAY:
                temperatures, pressures, z_values, point_count, property_config = property_grid_from_tab(
                    tab_path,
                    property_choice,
                )
                if not point_count:
                    st.warning(f"No finite values found for {property_choice}; showing P-T grid only.")
                    t_points, p_points = grid_points_from_tab(tab_path)
                    property_choice = GRID_ONLY_OPTION
                else:
                    fig.add_trace(
                        go.Heatmap(
                            x=temperatures,
                            y=pressures,
                            z=z_values,
                            colorscale=property_config["colorscale"],
                            colorbar=dict(title=property_config["colorbar"]),
                            name=property_config["label"],
                            hovertemplate="<b>P-T cell</b><br>"
                            + "T: %{x:.0f} K<br>"
                            + "P: %{y:.2f} GPa<br>"
                            + f"{property_config['label']}: "
                            + f"%{{z:.3g}} {property_config['unit']}<extra></extra>",
                        )
                    )
            else:
                t_points, p_points, property_values, property_config = property_points_from_tab(
                    tab_path,
                    property_choice,
                )
                point_count = len(property_values)
                if not property_values:
                    st.warning(f"No finite values found for {property_choice}; showing P-T grid only.")
                    t_points, p_points = grid_points_from_tab(tab_path)
                    property_choice = GRID_ONLY_OPTION
        else:
            t_points, p_points = grid_points_from_tab(tab_path)
            point_count = len(p_points)

        if property_choice in PROPERTY_OPTIONS and display_mode != HEATMAP_DISPLAY:
            fig.add_trace(
                go.Scatter(
                    x=t_points,
                    y=p_points,
                    mode="markers",
                    marker=dict(
                        size=8,
                        color=property_values,
                        colorscale=property_config["colorscale"],
                        showscale=True,
                        colorbar=dict(title=property_config["colorbar"]),
                    ),
                    name=property_config["label"],
                    hovertemplate="<b>P-T Point</b><br>"
                    + "T: %{x:.0f} K<br>"
                    + "P: %{y:.2f} GPa<br>"
                    + f"{property_config['label']}: "
                    + f"%{{marker.color:.3g}} {property_config['unit']}<extra></extra>",
                )
            )
        else:
            if property_choice == GRID_ONLY_OPTION:
                fig.add_trace(
                    go.Scatter(
                        x=t_points,
                        y=p_points,
                        mode="markers",
                        marker=dict(size=6, color="blue", opacity=0.6),
                        name="P-T Grid",
                        hovertemplate="T: %{x:.0f} K<br>P: %{y:.2f} GPa<extra></extra>",
                    )
                )

    except Exception as e:
        st.error(f"❌ Error reading output file: {e}")
        return

    # Layout
    fig.update_layout(
        title=f"P-T Coverage: {project}" if property_choice == GRID_ONLY_OPTION else f"{property_choice}: {project}",
        xaxis_title="Temperature (K)",
        yaxis_title="Pressure (GPa)",
        hovermode="closest",
        height=600,
    )

    # Reverse Y axis (higher pressure at bottom)
    fig.update_yaxes(autorange="reversed")

    st.plotly_chart(fig, use_container_width=True)

    # Summary info
    col1, col2, col3 = st.columns(3)
    col1.metric("T range", f"{min(temperatures_k):.0f}–{max(temperatures_k):.0f} K")
    col2.metric("P range", f"{min(pressures_bar)*1e-4:.2f}–{max(pressures_bar)*1e-4:.2f} GPa")
    col3.metric("Grid points", point_count)

    st.info(
        "Full phase diagrams with phase boundaries require additional VERTEX configuration. "
        "This plot shows the P-T grid and property distribution from WERAMI output."
    )


def show_phase_diagram_panel(models: list[dict[str, Any]], selected_project: str | None, config_path: Path):
    """Render phase diagram panel in GUI.

    Args:
        models: List of all models
        selected_project: Currently selected project
        config_path: Path to config file
    """
    project_options = [str(model.get("project", "")) for model in models if model.get("project")]
    if not project_options:
        st.info("No saved models are available to plot.")
        return
    selected_project = selected_project if selected_project in project_options else None
    stored_project = st.session_state.get(PHASE_MODEL_SELECTOR_KEY)
    if stored_project not in project_options:
        st.session_state.pop(PHASE_MODEL_SELECTOR_KEY, None)
        if selected_project:
            st.session_state[PHASE_MODEL_SELECTOR_KEY] = selected_project

    selectbox_kwargs: dict[str, Any] = {
        "label": "Saved model to plot",
        "options": project_options,
        "placeholder": "Choose a saved model",
        "format_func": lambda project: f"{project}",
        "key": PHASE_MODEL_SELECTOR_KEY,
    }
    if PHASE_MODEL_SELECTOR_KEY not in st.session_state:
        selectbox_kwargs["index"] = None
    selected_project = st.selectbox(**selectbox_kwargs)
    if not selected_project or selected_project not in project_options:
        st.info("Select a saved model to display a phase/property plot.")
        return

    st.subheader(f"Phase Diagram: {selected_project}")

    selected_model = next((m for m in models if m["project"] == selected_project), None)

    if not selected_model:
        st.error("Model not found")
        return

    paths = model_output_paths(selected_model, config_path)
    output_dir = paths.output_dir

    if not output_dir.exists():
        st.warning("⚠️ Output directory not found. Run the pipeline first.")
        return

    # Options
    with st.expander("⚙️ Diagram options"):
        st.caption("**Property to visualize**")
        prop_choice = st.radio(
            "Property",
            [*PROPERTY_OPTIONS.keys(), GRID_ONLY_OPTION],
            horizontal=True,
            label_visibility="collapsed",
        )
        display_mode = st.radio(
            "Display",
            [HEATMAP_DISPLAY, GRID_POINT_DISPLAY],
            horizontal=True,
            help="Heatmap shows gridded property values; grid points show the raw sampled WERAMI rows.",
        )

    plot_phase_diagram_interactive(
        selected_model,
        output_dir,
        property_choice=prop_choice,
        display_mode=display_mode,
    )
