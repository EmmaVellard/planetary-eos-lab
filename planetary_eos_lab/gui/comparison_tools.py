"""Model comparison tools for side-by-side analysis."""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

import plot_comparisons
import run_perplex
from planetary_eos_lab.core.validation_summary import (
    model_output_paths,
    read_text_if_exists,
    validation_status,
)


def show_comparison_workspace(models: list[dict[str, Any]], config_path: Path):
    """Render multi-model comparison UI.

    Args:
        models: List of all models
        config_path: Path to config file
    """
    st.header("Model Comparison")
    st.caption("Compare compositions and results from multiple models side-by-side")

    if len(models) < 2:
        st.warning("Need at least 2 models to compare. Create more compositions first.")
        return

    # Select models to compare (2-4)
    all_projects = [m["project"] for m in models]
    selected = st.multiselect(
        "Select models to compare (2-4)",
        options=all_projects,
        default=all_projects[:2] if len(all_projects) >= 2 else all_projects,
        max_selections=4,
        help="Choose which models to compare",
    )

    if len(selected) < 2:
        st.info("👆 Select at least 2 models to compare")
        return

    selected_models = [m for m in models if m["project"] in selected]

    # Comparison type tabs
    tab1, tab2, tab3 = st.tabs(["Composition", "Properties", "Validation"])

    with tab1:
        show_composition_comparison(selected, config_path)

    with tab2:
        show_properties_comparison(selected, config_path)

    with tab3:
        show_validation_comparison(selected_models, config_path)


def selected_plot_models(config_path: Path, projects: list[str]) -> list[plot_comparisons.PlotModel]:
    config = run_perplex.load_config(config_path)
    return plot_comparisons.selected_plot_models(config, projects)


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


def composition_difference_rows(models: list[plot_comparisons.PlotModel]) -> list[dict[str, str]]:
    if len(models) != 2:
        return []
    compositions = [plot_comparisons.load_normalized_composition(model.composition_file) for model in models]
    is_component = any(plot_comparisons.is_component_composition(model.composition_file) for model in models)
    keys = plot_comparisons.composition_keys(compositions, use_oxide_order=not is_component)
    rows: list[dict[str, str]] = []
    for key in keys:
        base_value = compositions[0].get(key, 0.0)
        comparison_value = compositions[1].get(key, 0.0)
        absolute_delta = comparison_value - base_value
        relative_delta = absolute_delta / base_value * 100.0 if abs(base_value) > 0.01 else 0.0
        rows.append(
            {
                "Component" if is_component else "Oxide": key,
                models[0].label: f"{base_value:.2f}",
                models[1].label: f"{comparison_value:.2f}",
                "Delta, wt%": f"{absolute_delta:+.2f}",
                f"Relative delta vs {models[0].label}, %": f"{relative_delta:+.1f}",
            }
        )
    return rows


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


def show_composition_comparison(projects: list[str], config_path: Path):
    """Display composition comparison as bar chart.

    Args:
        projects: Project names to compare
        config_path: Path to config file
    """
    st.subheader("Composition Comparison")

    try:
        plot_models = selected_plot_models(config_path, projects)
        st.plotly_chart(composition_comparison_figure(plot_models), use_container_width=True)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        st.warning(f"Could not render composition comparison: {exc}")
        return

    # Difference table (for 2 models)
    if len(plot_models) == 2:
        st.subheader("Composition Differences")
        st.dataframe(composition_difference_rows(plot_models), use_container_width=True, hide_index=True)
        st.caption(
            "Relative delta is the percent change from the first selected model to the second: "
            "(second - first) / first × 100. The wt% delta is the direct subtraction in normalized wt%."
        )


def show_properties_comparison(projects: list[str], config_path: Path):
    """Display property profile comparison.

    Args:
        projects: Project names to compare
        config_path: Path to config file
    """
    st.subheader("Property Profiles")

    try:
        plot_models = selected_plot_models(config_path, projects)
        st.plotly_chart(property_comparison_figure(plot_models), use_container_width=True)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        st.info(f"Property comparison plot is unavailable for this selection: {exc}")
        return


def show_validation_comparison(models: list[dict[str, Any]], config_path: Path):
    """Display validation status comparison table.

    Args:
        models: List of models to compare
        config_path: Path to config file
    """
    st.subheader("Validation Status")

    comparison_data = []

    for model in models:
        paths = model_output_paths(model, config_path)
        report = read_text_if_exists(paths.validation_report)
        status = validation_status(report)

        # Status emoji
        status_emoji = {"pass": "✅", "fail": "❌", "missing": "⏳"}.get(status, "❓")

        comparison_data.append(
            {
                "Project": model["project"],
                "Status": f"{status_emoji} {status}",
                "Tab file": "✅" if paths.planetprofile_table.exists() else "❌",
                "Build log": "✅" if paths.build_log.exists() else "❌",
                "VERTEX log": "✅" if paths.vertex_log.exists() else "❌",
                "WERAMI log": "✅" if paths.werami_log.exists() else "❌",
                "Scientific status": model.get("scientific_status", "unknown"),
                "PP readiness": model.get("planetprofile_readiness", "unknown"),
            }
        )

    st.dataframe(comparison_data, use_container_width=True, hide_index=True)

    # Summary counts
    st.divider()
    col1, col2, col3 = st.columns(3)

    passed = sum(1 for d in comparison_data if "pass" in d["Status"])
    failed = sum(1 for d in comparison_data if "fail" in d["Status"])
    pending = sum(1 for d in comparison_data if "missing" in d["Status"])

    col1.metric("✅ Passed", passed)
    col2.metric("❌ Failed", failed)
    col3.metric("⏳ Pending", pending)

    # Show validation reports in expanders
    if st.checkbox("Show detailed validation reports"):
        for model in models:
            paths = model_output_paths(model, config_path)
            report = read_text_if_exists(paths.validation_report)

            if report:
                with st.expander(f"📄 {model['project']} validation report"):
                    st.code(report, language="text")
