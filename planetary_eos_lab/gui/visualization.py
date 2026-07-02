"""Visualization helpers for GUI result display."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import streamlit as st


def show_validation_results(validation_report: Optional[str], omissions: Optional[str]) -> None:
    """Display validation results with appropriate styling.

    Args:
        validation_report: Validation report text
        omissions: Oxide omissions text
    """
    if not validation_report:
        st.info("No validation report available yet. Run Perple_X first.")
        return

    # Check validation status
    if "STATUS: PASS" in validation_report:
        st.success("✓ Validation PASSED")
        with st.expander("View validation report"):
            st.code(validation_report, language="text")
    elif "STATUS: FAIL" in validation_report:
        st.error("✗ Validation FAILED")
        st.code(validation_report, language="text")
    else:
        st.warning("Validation status unknown")
        st.code(validation_report, language="text")

    # Show oxide omissions as warning
    if omissions and omissions.strip():
        st.warning("Oxide Omissions")
        st.text(omissions)


def show_output_files(output_dir: Path, project: str) -> None:
    """Display table of output files with existence status.

    Args:
        output_dir: Output directory path
        project: Project name
    """
    files_to_check = [
        ("Raw WERAMI table", output_dir / f"{project}_raw_werami.tab"),
        ("PlanetProfile table", output_dir / f"{project}_planetprofile.tab"),
        ("Native PP table", output_dir / f"{project}_planetprofile_native.tab"),
        ("Validation report", output_dir / "validation_report.txt"),
        ("BUILD log", output_dir / "build.log"),
        ("VERTEX log", output_dir / "vertex.log"),
        ("WERAMI log", output_dir / "werami.log"),
        ("Perple_X .dat", output_dir / "work" / f"{project}.dat"),
    ]

    rows = []
    for label, path in files_to_check:
        exists = path.exists()
        size = f"{path.stat().st_size:,} bytes" if exists else "—"
        rows.append({"File": label, "Path": str(path.relative_to(output_dir.parent)), "Exists": "✓" if exists else "✗", "Size": size})

    st.dataframe(rows, use_container_width=True, hide_index=True)


def show_composition_comparison(models: list[dict[str, Any]], selected_project: Optional[str] = None) -> None:
    """Display composition comparison across models.

    Args:
        models: List of model dictionaries
        selected_project: Currently selected project (highlighted)
    """
    if not models:
        st.info("No models to compare")
        return

    st.subheader("Composition Comparison")

    # Extract oxide data
    oxides = ["SiO2", "TiO2", "Al2O3", "FeO", "MgO", "CaO", "Na2O", "K2O", "P2O5"]
    chart_data = {}

    for model in models:
        project = model.get("project", "unknown")
        composition = model.get("oxides_wt_percent", {})

        if isinstance(composition, dict):
            for oxide in oxides:
                if oxide not in chart_data:
                    chart_data[oxide] = {}
                chart_data[oxide][project] = composition.get(oxide, 0.0)

    # Show bar chart for each major oxide
    major_oxides = ["SiO2", "Al2O3", "FeO", "MgO", "CaO"]
    for oxide in major_oxides:
        if oxide in chart_data and chart_data[oxide]:
            st.caption(f"{oxide} (wt%)")
            st.bar_chart(chart_data[oxide], height=150)


def show_pt_coverage(output_dir: Path, project: str) -> None:
    """Display P-T coverage information from output table.

    Args:
        output_dir: Output directory
        project: Project name
    """
    tab_file = output_dir / f"{project}_planetprofile.tab"

    if not tab_file.exists():
        st.info("Run Perple_X to see P-T coverage")
        return

    try:
        with open(tab_file) as f:
            lines = f.readlines()

        # Parse header for P-T info
        p_values = []
        t_values = []

        for line in lines:
            if line.strip() and not line.startswith("|"):
                parts = line.split()
                if len(parts) >= 2:
                    try:
                        t_values.append(float(parts[0]))
                        p_values.append(float(parts[1]))
                    except (ValueError, IndexError):
                        continue

        if p_values and t_values:
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Min P", f"{min(p_values):.0f} bar")
            with col2:
                st.metric("Max P", f"{max(p_values):.0f} bar")
            with col3:
                st.metric("Min T", f"{min(t_values):.0f} K")
            with col4:
                st.metric("Max T", f"{max(t_values):.0f} K")

            st.caption(f"Grid size: {len(set(p_values))} × {len(set(t_values))} points")

    except Exception as e:
        st.warning(f"Could not parse P-T coverage: {e}")


def show_quick_stats(output_dir: Path, project: str) -> None:
    """Display quick statistics from output table.

    Args:
        output_dir: Output directory
        project: Project name
    """
    tab_file = output_dir / f"{project}_planetprofile.tab"

    if not tab_file.exists():
        return

    try:
        import statistics

        with open(tab_file) as f:
            lines = f.readlines()

        # Parse data columns
        rho_values = []
        vp_values = []
        vs_values = []

        for line in lines:
            if line.strip() and not line.startswith("|"):
                parts = line.split()
                if len(parts) >= 5:
                    try:
                        rho_values.append(float(parts[2]))
                        vp_values.append(float(parts[3]))
                        vs_values.append(float(parts[4]))
                    except (ValueError, IndexError):
                        continue

        if rho_values:
            st.subheader("Property Statistics")
            col1, col2, col3 = st.columns(3)

            with col1:
                st.metric("Mean ρ", f"{statistics.mean(rho_values):.0f} kg/m³")
                st.caption(f"Range: {min(rho_values):.0f}–{max(rho_values):.0f}")

            with col2:
                st.metric("Mean Vp", f"{statistics.mean(vp_values):.2f} km/s")
                st.caption(f"Range: {min(vp_values):.2f}–{max(vp_values):.2f}")

            with col3:
                st.metric("Mean Vs", f"{statistics.mean(vs_values):.2f} km/s")
                st.caption(f"Range: {min(vs_values):.2f}–{max(vs_values):.2f}")

    except Exception as e:
        st.warning(f"Could not compute statistics: {e}")
