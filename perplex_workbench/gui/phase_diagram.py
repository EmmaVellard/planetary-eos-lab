"""Phase diagram visualization with Plotly."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import plotly.graph_objects as go
import streamlit as st

from perplex_workbench.core.phase_parser import get_pt_grid_from_tab, parse_vertex_log
from perplex_workbench.core.validation_summary import model_output_paths


def plot_phase_diagram_interactive(model: dict[str, Any], output_dir: Path):
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

    # Create figure
    fig = go.Figure()

    # Show P-T coverage as scatter
    try:
        from validate_tab import column_indices, read_tab

        tab = read_tab(tab_path)
        indices = column_indices(tab.headers)

        p_index = indices["p_bar"]
        t_index = indices["t_k"]

        # Extract all P-T points
        p_points = []
        t_points = []
        rho_points = []

        rho_index = indices.get("rho_kgm3")

        for row in tab.rows:
            p = row[p_index]
            t = row[t_index]
            if abs(p) < 1e90 and abs(t) < 1e90:
                p_points.append(p * 1e-4)  # Convert to GPa
                t_points.append(t)
                if rho_index is not None:
                    rho = row[rho_index]
                    rho_points.append(rho if abs(rho) < 1e90 else None)

        # Create contour plot for density
        if rho_points and st.checkbox("Show density contours", value=True):
            fig.add_trace(
                go.Scatter(
                    x=t_points,
                    y=p_points,
                    mode="markers",
                    marker=dict(
                        size=8,
                        color=rho_points,
                        colorscale="Viridis",
                        showscale=True,
                        colorbar=dict(title="ρ (kg/m³)"),
                    ),
                    name="Density",
                    hovertemplate="<b>P-T Point</b><br>"
                    + "T: %{x:.0f} K<br>"
                    + "P: %{y:.2f} GPa<br>"
                    + "ρ: %{marker.color:.1f} kg/m³<extra></extra>",
                )
            )
        else:
            # Just show grid points
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
        title=f"P-T Coverage: {project}",
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
    col3.metric("Grid points", len(p_points))

    st.info(
        "ℹ️ **Note**: Full phase diagrams with phase boundaries require additional VERTEX configuration. "
        "This plot shows the P-T coverage and property distribution from WERAMI output."
    )


def show_phase_diagram_panel(models: list[dict[str, Any]], selected_project: str, config_path: Path):
    """Render phase diagram panel in GUI.

    Args:
        models: List of all models
        selected_project: Currently selected project
        config_path: Path to config file
    """
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
            ["Density", "P-wave velocity", "S-wave velocity", "None (grid only)"],
            horizontal=True,
            label_visibility="collapsed",
        )

    # Plot
    plot_phase_diagram_interactive(selected_model, output_dir)

    # Additional property plots if requested
    if prop_choice != "None (grid only)" and prop_choice != "Density":
        st.caption(f"**{prop_choice} visualization**")
        st.info("Additional property overlays coming in future updates")
