"""Enhanced validation with actionable feedback and suggestions."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import streamlit as st

from planetary_eos_lab.core.database_utils import get_active_oxides
from planetary_eos_lab.core.model_schema import validate_model_entry


@dataclass
class ValidationIssue:
    """Validation issue with severity and suggested fix."""

    severity: str  # "error", "warning", "info"
    message: str
    suggestion: str | None = None


def enhanced_validate_model(model: dict[str, Any], database: str = "stx21") -> list[ValidationIssue]:
    """Validate model with detailed actionable feedback.

    Args:
        model: Model configuration dictionary
        database: Database name (default: "stx21")

    Returns:
        List of validation issues
    """
    issues = []

    # Check project name
    project = model.get("project", "").strip()
    if not project:
        issues.append(
            ValidationIssue(
                severity="error",
                message="Missing project name",
                suggestion="Enter a unique project identifier (e.g., 'lunar_mantle_v1', 'bse_candidate')",
            )
        )

    # Check composition total
    composition = model.get("oxides_wt_percent", {})
    if not isinstance(composition, dict):
        issues.append(
            ValidationIssue(
                severity="error",
                message="Invalid composition format",
                suggestion="Composition must be a dictionary of oxide: wt% pairs",
            )
        )
        composition = {}

    total = sum(float(v) for v in composition.values() if isinstance(v, (int, float)))

    if total < 95.0:
        issues.append(
            ValidationIssue(
                severity="error",
                message=f"Composition total is only {total:.1f} wt%",
                suggestion=f"Add {100.0 - total:.1f} wt% to major oxides (e.g., SiO2 or MgO) to reach ~100 wt%",
            )
        )
    elif total > 105.0:
        issues.append(
            ValidationIssue(
                severity="error",
                message=f"Composition total exceeds 105 wt% ({total:.1f})",
                suggestion="Reduce oxide values to reach ~100 wt%. Check for data entry errors.",
            )
        )
    elif not (99.0 <= total <= 101.0):
        issues.append(
            ValidationIssue(
                severity="warning",
                message=f"Composition total is {total:.2f} wt% (will be normalized to 100)",
                suggestion="This is acceptable but consider adjusting values to sum to exactly 100 wt%",
            )
        )

    # Check for database compatibility
    active_oxides = get_active_oxides(database)

    significant_inactive = []
    for oxide, value in composition.items():
        if isinstance(value, (int, float)) and value > 0.1 and oxide not in active_oxides:
            significant_inactive.append(f"{oxide}={value:.2f} wt%")

    if significant_inactive:
        if database == "stx21":
            suggestion = (
                "Consider switching to hp633 if TiO2 or K2O are important, or accept that "
                "source-only oxides will be omitted from BUILD calculations."
            )
        else:
            suggestion = (
                "Use a custom thermodynamic database and BUILD template if these oxides must "
                "be modeled, or accept that they will be omitted from BUILD calculations."
            )
        issues.append(
            ValidationIssue(
                severity="warning",
                message=f"Database '{database}' does not model: {', '.join(significant_inactive)}",
                suggestion=suggestion,
            )
        )

    # Check for missing metadata
    if not model.get("description"):
        issues.append(
            ValidationIssue(
                severity="info",
                message="Missing description",
                suggestion="Add a brief description to help identify this composition later",
            )
        )

    if not model.get("planetprofile_filename"):
        issues.append(
            ValidationIssue(
                severity="info",
                message="Missing PlanetProfile filename",
                suggestion=f"Suggest: {project}_PerpleX.tab" if project else "Provide output filename for PlanetProfile",
            )
        )

    # Check for negative values
    for oxide, value in composition.items():
        if isinstance(value, (int, float)) and value < 0:
            issues.append(
                ValidationIssue(
                    severity="error",
                    message=f"Negative value for {oxide}: {value:.2f} wt%",
                    suggestion="Oxide concentrations must be non-negative",
                )
            )

    return issues


def show_enhanced_validation(model: dict[str, Any], database: str = "stx21") -> bool:
    """Display validation with actionable feedback in Streamlit.

    Args:
        model: Model to validate
        database: Database name

    Returns:
        True if validation passes (no errors), False otherwise
    """
    issues = enhanced_validate_model(model, database)

    errors = [i for i in issues if i.severity == "error"]
    warnings = [i for i in issues if i.severity == "warning"]
    infos = [i for i in issues if i.severity == "info"]

    if errors:
        st.error(f"❌ {len(errors)} error(s) must be fixed before saving")
        for issue in errors:
            with st.container():
                st.markdown(f"**{issue.message}**")
                if issue.suggestion:
                    st.caption(f"💡 {issue.suggestion}")

    if warnings:
        st.warning(f"⚠️ {len(warnings)} warning(s)")
        for issue in warnings:
            with st.expander(f"⚠️ {issue.message}"):
                if issue.suggestion:
                    st.info(issue.suggestion)

    if infos:
        with st.expander(f"ℹ️ {len(infos)} optional improvement(s)"):
            for issue in infos:
                st.markdown(f"- {issue.message}")
                if issue.suggestion:
                    st.caption(f"💡 {issue.suggestion}")

    if not errors and not warnings and not infos:
        st.success("✅ Validation passed with no issues")

    return len(errors) == 0


def show_basic_validation_status(model: dict[str, Any]) -> bool:
    """Show simple validation status without detailed feedback.

    Args:
        model: Model to validate

    Returns:
        True if validation passes
    """
    validation = validate_model_entry(model)

    if validation.errors:
        st.error("❌ " + "; ".join(validation.errors))

    for warning in validation.warnings:
        st.warning("⚠️ " + warning)

    if validation.ok:
        st.success("✅ Validation passed")

    return validation.ok
