"""Model comparison tools for side-by-side analysis."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

from planetary_eos_lab.core.model_schema import OXIDE_ORDER, normalize_composition
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
    tab1, tab2, tab3 = st.tabs(["📊 Composition", "📈 Properties", "✅ Validation"])

    with tab1:
        show_composition_comparison(selected_models)

    with tab2:
        show_properties_comparison(selected_models, config_path)

    with tab3:
        show_validation_comparison(selected_models, config_path)


def show_composition_comparison(models: list[dict[str, Any]]):
    """Display composition comparison as bar chart.

    Args:
        models: List of models to compare
    """
    st.subheader("Composition Comparison")

    # Bar chart
    fig = go.Figure()

    for model in models:
        composition = model.get("oxides_wt_percent", {})
        normalized = normalize_composition(composition)

        fig.add_trace(
            go.Bar(
                name=model["project"],
                x=list(OXIDE_ORDER),
                y=[normalized.get(oxide, 0.0) for oxide in OXIDE_ORDER],
                text=[f"{normalized.get(oxide, 0.0):.1f}" for oxide in OXIDE_ORDER],
                textposition="auto",
            )
        )

    fig.update_layout(
        title="Normalized Composition (wt%)",
        xaxis_title="Oxide",
        yaxis_title="Normalized wt%",
        barmode="group",
        height=500,
        hovermode="x unified",
    )

    st.plotly_chart(fig, use_container_width=True)

    # Difference table (for 2 models)
    if len(models) == 2:
        st.subheader("Oxide Differences")
        base_comp = normalize_composition(models[0].get("oxides_wt_percent", {}))
        comp_comp = normalize_composition(models[1].get("oxides_wt_percent", {}))

        diff_data = [
            {
                "Oxide": oxide,
                models[0]["project"]: f"{base_comp[oxide]:.2f}",
                models[1]["project"]: f"{comp_comp[oxide]:.2f}",
                "Δ (wt%)": f"{comp_comp[oxide] - base_comp[oxide]:+.2f}",
                "Relative Δ (%)": f"{((comp_comp[oxide] - base_comp[oxide]) / base_comp[oxide] * 100 if base_comp[oxide] > 0.01 else 0):+.1f}",
            }
            for oxide in OXIDE_ORDER
        ]

        st.dataframe(diff_data, use_container_width=True, hide_index=True)


def show_properties_comparison(models: list[dict[str, Any]], config_path: Path):
    """Display property profile comparison.

    Args:
        models: List of models to compare
        config_path: Path to config file
    """
    st.subheader("Property Profiles")

    # Check if any models have output
    has_output = any(model_output_paths(m, config_path).planetprofile_table.exists() for m in models)

    if not has_output:
        st.info("No Perple_X output available yet. Run the pipeline first to see property comparisons.")
        return

    # Create 2x2 subplot
    fig = make_subplots(
        rows=2,
        cols=2,
        subplot_titles=("Density", "P-wave Velocity", "S-wave Velocity", "Bulk Modulus"),
        x_title="Pressure (GPa)",
        vertical_spacing=0.12,
        horizontal_spacing=0.1,
    )

    properties = [
        ("rho_kgm3", 1, 1, "kg/m³", 1.0),
        ("vp_kms", 1, 2, "km/s", 1.0),
        ("vs_kms", 2, 1, "km/s", 1.0),
        ("ks_bar", 2, 2, "GPa", 1.0e-4),
    ]

    colors = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728"]

    for idx, model in enumerate(models):
        paths = model_output_paths(model, config_path)
        if not paths.planetprofile_table.exists():
            continue

        color = colors[idx % len(colors)]

        for prop_name, row, col, unit, scale in properties:
            try:
                profile = pressure_profile(paths.planetprofile_table, prop_name, scale)
                if not profile:
                    continue

                pressures = [p for p, _ in profile]
                values = [v for _, v in profile]

                fig.add_trace(
                    go.Scatter(
                        x=pressures,
                        y=values,
                        name=model["project"],
                        mode="lines",
                        line=dict(color=color),
                        showlegend=(row == 1 and col == 1),  # Only show legend once
                        hovertemplate=f"<b>{model['project']}</b><br>"
                        + "P: %{x:.2f} GPa<br>"
                        + f"{prop_name}: %{{y:.2f}} {unit}<extra></extra>",
                    ),
                    row=row,
                    col=col,
                )

            except Exception as e:
                st.warning(f"Could not load {prop_name} for {model['project']}: {e}")

    fig.update_layout(height=700, hovermode="x unified")
    st.plotly_chart(fig, use_container_width=True)


def pressure_profile(tab_path: Path, property_name: str, value_scale: float = 1.0) -> list[tuple[float, float]]:
    """Extract pressure profile for a property from .tab file.

    Args:
        tab_path: Path to .tab file
        property_name: Property to extract
        value_scale: Scale factor for values

    Returns:
        List of (pressure_GPa, value) tuples
    """
    from collections import defaultdict

    from validate_tab import column_indices, read_tab

    tab = read_tab(tab_path)
    indices = column_indices(tab.headers)

    if "p_bar" not in indices or property_name not in indices:
        return []

    # Group by pressure and average
    grouped: dict[float, list[float]] = defaultdict(list)
    p_index = indices["p_bar"]
    value_index = indices[property_name]

    for row in tab.rows:
        pressure = row[p_index]
        value = row[value_index]
        # Filter out bad values
        if abs(pressure) < 1e90 and abs(value) < 1e90:
            grouped[pressure].append(value * value_scale)

    # Convert to list and sort by pressure
    import statistics

    profile = []
    for pressure_bar in sorted(grouped.keys()):
        values = grouped[pressure_bar]
        if values:
            avg_value = statistics.fmean(values)
            pressure_gpa = pressure_bar * 1.0e-4
            profile.append((pressure_gpa, avg_value))

    return profile


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
